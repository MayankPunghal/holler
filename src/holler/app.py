"""The dictation controller: hotkey state machine, record -> transcribe -> clean -> paste, and learning."""
import os
import sys
import threading
import time

from . import audio as A
from .cleanup import clean
from .suggest import auto_add
from .spoken import apply_commands, is_undo, smart_format
from . import models
from .engines import make_engine
from .keys import GROUPS, Combo, key_id, K
from difflib import SequenceMatcher

from .output import MASK_VK, backspace, beep, copy_selection, mask_win, paste
from .overlay import make_overlay
from .paths import PACKAGE_DATA, data_dir, log_error
from .vocab import Vocab, align


class App:
    def __init__(self, cfg, download_only=False, tray=False):
        self.cfg = cfg
        self.home = data_dir()
        self.talk = Combo(cfg.key)
        self.teach_combo = Combo(cfg.teach_key)
        self.undo_combo = Combo(cfg.undo_key) if cfg.undo_key else None
        self.hold_s = max(0, cfg.hold_ms) / 1000.0
        self.vocab = Vocab(self.home, PACKAGE_DATA)
        self.extra_terms = [k.strip() for k in (cfg.extra_keywords or "").split(",") if k.strip()]
        self.overlay = make_overlay(cfg.overlay, cfg.key, cfg.ui, log=log_error)
        self.busy = threading.Lock()         # one transcription at a time
        self.st = threading.Lock()           # guards pending/down
        self.held = set()                    # keys physically held right now
        self.down = False                    # recording
        self.pending = False                 # chord held, waiting out the hold delay
        self.timer = None
        self.listener = None
        self.synth = False                   # True while WE are sending keystrokes (ignore them)
        self.engine = None
        self.rec = None
        self.last = ""                       # last text pasted (for learning)
        self.paused = False
        self.teach_timer = None
        self.undo_timer = None
        self.pasted = []                     # (text, time) of recent pastes, newest last, for undo
        self.n_dictations = 0
        self.undone = None                   # (text, time) of the dictation the user just undid
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
            print(f"Ready ({a.engine} {a.model}). Hold [{a.key}]{hold} and speak; release to paste. "
                  f"Esc cancels. Learn a fix: [{a.teach_key}]."
                  + (f" Undo: [{a.undo_key}] or say \"scratch that\"." if a.undo_key else ""), flush=True)
        except Exception:
            log_error("startup")
            self.overlay.set("error")
            print("Startup failed - see errors.log in", self.home, flush=True)
            if a.engine == "whisper" and not models.is_downloaded(a.model):
                print(models.manual_instructions(a.model), flush=True)

    # ------------------------------------------------------------------ dictation
    def _wait_released(self, timeout=1.5):
        """Don't send Ctrl+V while a chord key (e.g. Win) is still physically down: Win+V is clipboard history."""
        t0 = time.time()
        while time.time() - t0 < timeout and any(self.talk.includes(k) or self.teach_combo.includes(k) or (self.undo_combo and self.undo_combo.includes(k)) for k in self.held):
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
            keywords = (self.vocab.prompt_terms() or []) + self.extra_terms or None
            with self.busy:
                raw, lang = self.engine(audio, a.lang, keywords)
            if a.spoken_commands and is_undo(raw):             # "scratch that" on its own: remove the last dictation
                self.undo()
                return
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
            self.last = text
            if a.log:
                try:
                    with open(os.path.join(self.home, "dictation_log.tsv"), "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{raw}\t{text}\n")
                except OSError:
                    pass
            learned = self._auto_learn(text)
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
            if not a.enter:
                self.pasted = (self.pasted + [(out, time.time())])[-10:]
            self.overlay.set("learned" if learned else "done")
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

    def _auto_learn(self, text):
        """Undo, then say it again: the difference between the two takes is a correction worth learning."""
        prev, self.undone = self.undone, None
        if not self.cfg.auto_learn or not prev or time.time() - prev[1] > 60:
            return False
        old = prev[0].strip()
        if old.lower() == text.strip().lower() or SequenceMatcher(None, old.lower(), text.lower()).ratio() < 0.55:
            return False
        try:
            msgs = self.vocab.learn_from_edit(old, text.strip())
        except Exception:
            log_error("auto-learn")
            return False
        for m in msgs or []:
            print("Auto-learn:", m, flush=True)
        return bool(msgs)

    def undo(self):
        """Delete the last pasted dictation (assumes the cursor hasn't moved since)."""
        try:
            while self.pasted and time.time() - self.pasted[-1][1] > 600:
                self.pasted.pop()                         # too old to trust
            if not self.pasted:
                print("Undo: nothing to undo.", flush=True)
                self.overlay.set("noundo")
                return
            text, _ = self.pasted.pop()
            self._wait_released()
            self.synth = True
            try:
                backspace(len(text))
            finally:
                self.synth = False
            self.undone = (text, time.time())
            print(f"Undo: removed {len(text)} characters.", flush=True)
            self.last = self.pasted[-1][0].strip() if self.pasted else ""
            self.overlay.set("undone")
        except Exception:
            log_error("undo")
            self.overlay.set("error")

    def teach(self):
        try:
            if not self.last:
                self.overlay.set("nomatch")
                return
            self._wait_released()
            self.synth = True
            try:
                sel = copy_selection(whole_line=True).strip()
            finally:
                self.synth = False
            sel = align(self.last, sel) if sel else ""
            if not sel:
                self.overlay.set("nomatch")
                return
            msgs = self.vocab.learn_from_edit(self.last, sel)
            if msgs is None:
                print("Teach: that text doesn't look like the last dictation.", flush=True)
                self.overlay.set("nomatch")
            elif not msgs:
                self.overlay.set("nothing")
            else:
                for m in msgs:
                    print("Teach:", m, flush=True)
                self.last = sel
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

    def _start_undo_timer(self):
        def fire():
            if self.undo_combo.complete(self.held) and not self.down:
                self.undo()
        t = threading.Timer(max(self.hold_s, 0.3), fire)
        t.daemon = True
        self.undo_timer = t
        t.start()

    def _mask(self, combo):
        """If the chord holds Win, send a dummy key so releasing Win never opens the Start menu."""
        if sys.platform == "win32" and combo is not None and any(
                k in slot for slot in combo.slots for k in GROUPS["win"]):
            mask_win()

    def _interrupt_recording(self):
        """A different chord was completed while recording: drop the recording."""
        with self.st:
            was_down, self.down = self.down, False
        self._cancel_pending()
        if was_down:
            self.rec.discard()
            self.overlay.set("hide")

    def on_press(self, key):
        if self.synth or getattr(key, "vk", None) == MASK_VK:
            return
        kid = key_id(key)
        if kid == K.esc:
            with self.st:
                was_down, self.down = self.down, False
            self._cancel_pending()
            if was_down:
                self.rec.discard()
                self.overlay.set("cancelled")
            return
        was_talk, was_teach = self.talk.complete(self.held), self.teach_combo.complete(self.held)
        was_undo = bool(self.undo_combo and self.undo_combo.complete(self.held))
        self.held.add(kid)
        if self.undo_timer and self.undo_combo and not self.undo_combo.includes(kid):
            self.undo_timer.cancel()                      # another key joined: a shortcut, not the undo chord
        if self.undo_combo and self.undo_combo.complete(self.held) and not was_undo:
            self._interrupt_recording()
            self._mask(self.undo_combo)
            if self.undo_combo.modifier_only:
                self._start_undo_timer()
            else:
                threading.Thread(target=self.undo, daemon=True).start()
            return
        if self.teach_combo.complete(self.held) and not was_teach:
            self._interrupt_recording()
            self._mask(self.teach_combo)
            if self.teach_combo.modifier_only:            # hold it briefly, like the dictation chord
                self._start_teach_timer()
            else:
                threading.Thread(target=self.teach, daemon=True).start()
            return
        if self.talk.complete(self.held) and not was_talk:
            if any(not self.talk.includes(k) for k in self.held) or self.rec is None or self.paused:
                return                                    # extra keys held: this is some other shortcut
            self._mask(self.talk)
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
            self._cancel_pending()                        # a shortcut (Ctrl+Win+Left ...): not a dictation

    def on_release(self, key):
        if self.synth or getattr(key, "vk", None) == MASK_VK:
            return
        kid = key_id(key)
        was_talk = self.talk.complete(self.held)
        self.held.discard(kid)
        if self.teach_timer and not self.teach_combo.complete(self.held):
            self.teach_timer.cancel()
        if self.undo_timer and not (self.undo_combo and self.undo_combo.complete(self.held)):
            self.undo_timer.cancel()
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
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
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
                if idle and self.listener is not None and (
                        woke or not self.listener.is_alive() or now - last_renew > 900):
                    self._start_listener()
                    last_renew = now
                    if woke:
                        print("Keyboard hook renewed.", flush=True)
                if idle and rec is not None and (woke or not rec.healthy()):
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
