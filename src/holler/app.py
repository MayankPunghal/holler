"""The dictation controller: hotkey state machine, record -> transcribe -> clean -> paste, and learning."""
import os
import sys
import threading
import time

from . import audio as A
from .cleanup import clean
from .suggest import auto_add
from .spoken import apply_commands, smart_format
from . import models
from .engines import make_engine
from .keys import GROUPS, Combo, key_id, K, physically_down
from .output import beep, copy_selection, paste
from .overlay import make_overlay
from .paths import PACKAGE_DATA, data_dir, log_error
from .vocab import Vocab, align


class App:
    def __init__(self, cfg, download_only=False, tray=False):
        self.cfg = cfg
        self.home = data_dir()
        self.talk = Combo(cfg.key)
        self.teach_combo = Combo(cfg.teach_key)
        self.hold_s = max(0, cfg.hold_ms) / 1000.0
        self.vocab = Vocab(self.home, PACKAGE_DATA)
        self.extra_terms = [k.strip() for k in (cfg.extra_keywords or "").split(",") if k.strip()]
        self.overlay = make_overlay(cfg.overlay, cfg.key, cfg.ui, log=log_error)
        self.busy = threading.Lock()         # one transcription at a time
        self.st = threading.Lock()           # guards pending/down
        self.held = set()                    # keys physically held right now
        self.held_t = {}                     # when each held key went down
        self.down = False                    # recording
        self.pending = False                 # chord held, waiting out the hold delay
        self.timer = None
        self.listener = None
        self.synth = False                   # True while WE are sending keystrokes (ignore them)
        self.engine = None
        self.rec = None
        self.recent = []                     # recent dictations, newest last (for learning a correction)
        self.paused = False
        self.teach_timer = None
        self.n_dictations = 0
        self.tray = tray
        self.download_only = download_only

    # ------------------------------------------------------------------ startup
    def boot(self):
        a = self.cfg
        try:
            self.overlay.set("loading")
            self.engine = make_engine(a.engine, a.model, a.beam, a.initial_prompt)
            if self.download_only:
                print("Model ready.", flush=True)
                os._exit(0)
            self.rec = A.Recorder(lambda lv: self.overlay.set("listening", lv), pre_s=A.PRE_ROLL_S + self.hold_s, device=a.device)
            self.overlay.set("ready")
            if a.auto_vocab:
                threading.Thread(target=self._auto_vocab, daemon=True).start()
            hold = f" for {a.hold_ms} ms" if self.hold_s else ""
            from . import __version__
            print(f"Holler {__version__}. Ready ({a.engine} {a.model}). Hold [{a.key}]{hold} and speak; release to paste. "
                  f"Esc cancels. Learn a fix: [{a.teach_key}].", flush=True)
        except Exception:
            log_error("startup")
            self.overlay.set("error")
            print("Startup failed - see errors.log in", self.home, flush=True)
            if a.engine == "whisper" and not models.is_downloaded(a.model):
                print(models.manual_instructions(a.model), flush=True)

    # ------------------------------------------------------------------ dictation
    def _prune_held(self):
        """Forget keys that are no longer down. A missed key-up (Win+L, sleep, the lock screen) must never leave
        a 'ghost' key that makes Holler ignore the dictation chord. Windows is asked directly; a key it can't
        answer for is dropped after 3 seconds unless it is a modifier."""
        now = time.time()
        mods = set().union(*GROUPS.values())
        for k in list(self.held):
            state = physically_down(k)
            if state is False or (state is None and k not in mods and now - self.held_t.get(k, now) > 3):
                self.held.discard(k)
                self.held_t.pop(k, None)

    def _wait_released(self, timeout=1.5):
        """Don't send Ctrl+V while a chord key (e.g. Win) is still physically down: Win+V is clipboard history."""
        t0 = time.time()
        while time.time() - t0 < timeout and (self._prune_held() or True) and any(self.talk.includes(k) or self.teach_combo.includes(k) for k in self.held):
            time.sleep(0.02)

    def finish(self):
        a = self.cfg
        try:
            time.sleep(A.TAIL_S)
            raw_audio = self.rec.stop()
            if len(raw_audio) < A.TARGET_SR * A.MIN_SECONDS:      # accidental tap
                self.overlay.set("hide")
                return
            audio = A.prepare(raw_audio)
            if audio is None:                                      # held the key but the mic gave silence
                self.overlay.set("nomic")
                return
            self.overlay.set("transcribing")
            self.vocab.refresh_if_changed()
            keywords = (self.vocab.prompt_terms(350) or []) + self.extra_terms or None
            if len(audio) < A.TARGET_SR * 2.5:
                keywords = None                    # on short clips a glossary skews the words ("First line" -> "FirstLine")
            with self.busy:
                raw, lang = self.engine(audio, a.lang, keywords)
            text = self.vocab.apply(raw)
            if a.cleanup:
                text = clean(text)
            if a.spoken_commands:
                text = apply_commands(text)
            if a.smart_format:
                text = smart_format(text)
            if not text:
                self.overlay.set("empty")
                return
            print(f"[{lang}] {raw}" + ("" if text == raw else f"  =>  {text}"), flush=True)
            self.recent = (self.recent + [text])[-10:]
            if a.log:
                try:
                    with open(os.path.join(self.home, "dictation_log.tsv"), "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{raw}\t{text}\n")
                except OSError:
                    pass
            self.n_dictations += 1
            if a.auto_vocab and self.n_dictations % 20 == 0:
                threading.Thread(target=self._auto_vocab, daemon=True).start()
            self._wait_released()
            self.synth = True
            out = text + " " if (a.trailing_space and not a.enter) else text
            try:
                paste(out, a.paste, a.enter)
                time.sleep(0.1)
            finally:
                self.synth = False
            self.overlay.set("done")
            if a.sound:
                beep("stop")
        except Exception:
            log_error("transcribe/paste")
            self.overlay.set("error")

    def _auto_vocab(self):
        try:
            for t in auto_add(os.path.join(self.home, "dictation_log.tsv"), self.vocab):
                print("Auto-vocabulary: added", t, flush=True)
        except Exception:
            log_error("auto-vocab")

    def _match_edit(self, sel):
        """Find which recent dictation the copied text is a corrected version of. The copy may be a whole
        (wrapped) line holding several dictations, or just a fragment of one. Returns (dictated, corrected)."""
        for dictated in reversed(self.recent):
            if len(sel.split()) < len(dictated.split()):
                part = align(sel, dictated)                # the piece of the dictation the fragment covers
                if self.vocab.learn_preview(part, sel):
                    return part, sel
            else:
                part = align(dictated, sel)                # the piece of the line that is this dictation
                if self.vocab.learn_preview(dictated, part):
                    return dictated, part
        return None

    def teach(self):
        try:
            if not self.recent:
                self.overlay.set("nomatch")
                return
            self._wait_released()
            self.synth = True
            try:
                sel = copy_selection(whole_line=True).strip()
            finally:
                self.synth = False
            if not sel:
                print("Teach: couldn't copy any text (select the corrected words and try again).", flush=True)
                self.overlay.set("nomatch")
                return
            found = self._match_edit(sel)
            if not found:
                print(f"Teach: '{sel[:80]}' doesn't look like a corrected version of a recent dictation.", flush=True)
                self.overlay.set("nomatch")
                return
            dictated, corrected = found
            msgs = self.vocab.learn_from_edit(dictated, corrected)
            if not msgs:
                self.overlay.set("nothing")
            else:
                for m in msgs:
                    print("Teach:", m, flush=True)
                self.recent = [corrected if d == dictated else d for d in self.recent]
                self.overlay.set("learned")
        except Exception:
            log_error("teach")
            self.overlay.set("error")

    # ------------------------------------------------------------------ hotkey state machine
    def _arm(self):
        """Hold time reached: start recording (audio from just before the key press is included)."""
        with self.st:
            if not self.pending or self.rec is None:
                return
            self.pending, self.down = False, True
            self.rec.start()
        self.overlay.set("listening", 0.0)
        if self.cfg.sound:
            beep("start")
        eng = self.engine
        if eng is not None and eng.m is None:             # was unloaded while idle: reload during speech
            threading.Thread(target=eng.ensure, daemon=True).start()

    def _cancel_pending(self):
        with self.st:
            t, self.pending, self.timer = self.timer, False, None
        if t:
            t.cancel()

    def _start_teach_timer(self):
        def fire():
            if self.teach_combo.complete(self.held) and not self.down:
                self.teach()
        t = threading.Timer(max(self.hold_s, 0.3), fire)
        t.daemon = True
        self.teach_timer = t
        t.start()

    def _filter(self, msg, data):
        """Windows hook filter: ignore keystrokes injected by software (Holler's own paste, other tools), so they
        can never start a dictation or leave a 'ghost' held key. Nothing is sent or suppressed."""
        return not (data.flags & 0x10)                     # LLKHF_INJECTED

    def _interrupt_recording(self):
        """A different chord was completed while recording: drop the recording."""
        with self.st:
            was_down, self.down = self.down, False
        self._cancel_pending()
        if was_down:
            self.rec.discard()
            self.overlay.set("hide")

    def on_press(self, key):
        if self.synth or getattr(key, "vk", None) in (0, 0xFF):
            return
        kid = key_id(key)
        if not kid:
            return
        if kid == K.esc:
            with self.st:
                was_down, self.down = self.down, False
            self._cancel_pending()
            if was_down:
                self.rec.discard()
                self.overlay.set("cancelled")
            return
        self._prune_held()
        was_talk, was_teach = self.talk.complete(self.held), self.teach_combo.complete(self.held)
        self.held.add(kid)
        self.held_t.setdefault(kid, time.time())
        if self.teach_combo.complete(self.held) and not was_teach:
            self._interrupt_recording()
            if self.teach_combo.modifier_only:            # hold it briefly, like the dictation chord
                self._start_teach_timer()
            else:
                threading.Thread(target=self.teach, daemon=True).start()
            return
        if self.talk.complete(self.held) and not was_talk:
            extra = [getattr(k, "name", k) for k in self.held if not self.talk.includes(k)]
            if extra or self.rec is None or self.paused:
                if extra:
                    print(f"Ignored {self.talk}: other keys are held: {extra}", flush=True)
                return                                    # extra keys held: this is some other shortcut
            with self.st:
                if self.down or self.pending:
                    return
                self.pending = True
                if self.hold_s > 0:
                    self.timer = threading.Timer(self.hold_s, self._arm)
                    self.timer.daemon = True
                    self.timer.start()
            if self.hold_s <= 0:
                self._arm()
        elif self.pending and not self.talk.includes(kid):
            self._cancel_pending()                        # a shortcut (Ctrl+Shift+T ...): not a dictation
        elif self.down and not self.talk.includes(kid):
            self._interrupt_recording()                   # another key while recording: a shortcut, not speech
            self.overlay.set("cancelled")

    def on_release(self, key):
        if self.synth or getattr(key, "vk", None) in (0, 0xFF):
            return
        kid = key_id(key)
        was_talk = self.talk.complete(self.held)
        self.held.discard(kid)
        self.held_t.pop(kid, None)
        if self.teach_timer and not self.teach_combo.complete(self.held):
            self.teach_timer.cancel()
        if was_talk and not self.talk.complete(self.held):
            if self.pending:
                self._cancel_pending()                    # a tap: ignore
                return
            with self.st:
                if not self.down:
                    return
                self.down = False
            threading.Thread(target=self.finish, daemon=True).start()

    def _start_listener(self):
        """(Re)create the global keyboard hook. Windows silently drops a hook after sleep, a lock screen or a slow
        callback, so Holler renews it instead of trusting it forever."""
        from pynput import keyboard
        old, self.listener = self.listener, None
        if old is not None:
            try:
                old.stop()
            except Exception:
                pass
        self.held.clear()
        self.held_t.clear()
        kw = {}
        if sys.platform == "win32":
            # Ignore keystrokes that software injects (Holler's own paste, other tools): only real
            # key presses can start a dictation, and injected events can never leave a 'ghost' held key.
            kw["win32_event_filter"] = self._filter
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release, **kw)
        self.listener.start()

    def watchdog(self):
        """Auto-stop at the recording limit; free the model's memory when idle; keep the keyboard hook and the
        microphone alive (they die silently after sleep/resume)."""
        last_tick, last_renew = time.time(), time.time()
        while True:
            time.sleep(0.5)
            now = time.time()
            woke = now - last_tick > 8                     # the computer slept: hook and microphone are suspect
            last_tick = now
            rec, eng = self.rec, self.engine
            idle = not self.down and not self.pending and not self.busy.locked()
            try:
                if woke:                                   # start clean after sleep, whatever state we were in
                    self._interrupt_recording()
                    self._start_listener()
                    last_renew = now
                    if rec is not None:
                        rec.reopen()
                    print("Woke from sleep: keyboard hook and microphone renewed.", flush=True)
                    continue
                self._prune_held()
                if idle and self.listener is not None and (
                        not self.listener.is_alive() or now - last_renew > 900):
                    self._start_listener()
                    last_renew = now
                if idle and rec is not None and not rec.healthy():
                    rec.reopen()
                    print("Microphone reopened.", flush=True)
            except Exception:
                log_error("watchdog")
            if self.down and rec is not None and time.time() - rec.t0 > A.MAX_SECONDS:
                with self.st:
                    self.down = False
                threading.Thread(target=self.finish, daemon=True).start()
            if (self.cfg.unload_after and eng is not None and eng.m is not None and not self.down
                    and not self.busy.locked() and time.time() - eng.last_used > self.cfg.unload_after * 60):
                eng.unload()

    def run(self):
        threading.Thread(target=self.boot, daemon=True).start()
        self._start_listener()
        threading.Thread(target=self.watchdog, daemon=True).start()
        if self.tray:
            from .tray import start_tray
            self.tray = start_tray(self)
        self.overlay.run()      # blocks until the process is closed
