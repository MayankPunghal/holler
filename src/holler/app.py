"""The dictation controller: hotkey state machine, record -> transcribe -> clean -> paste, and learning."""
import os
import threading
import time

from . import audio as A
from .cleanup import clean
from . import models
from .engine import WhisperEngine
from .keys import Combo, key_id, K
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
        self.down = False                    # recording
        self.pending = False                 # chord held, waiting out the hold delay
        self.timer = None
        self.synth = False                   # True while WE are sending keystrokes (ignore them)
        self.engine = None
        self.rec = None
        self.last = ""                       # last text pasted (for learning)
        self.paused = False
        self.teach_timer = None
        self.tray = tray
        self.download_only = download_only

    # ------------------------------------------------------------------ startup
    def boot(self):
        a = self.cfg
        try:
            self.overlay.set("loading")
            self.engine = WhisperEngine(a.model, a.beam)
            if self.download_only:
                print("Model ready.", flush=True)
                os._exit(0)
            self.rec = A.Recorder(lambda lv: self.overlay.set("listening", lv), pre_s=A.PRE_ROLL_S + self.hold_s, device=a.device)
            self.overlay.set("ready")
            hold = f" for {a.hold_ms} ms" if self.hold_s else ""
            print(f"Ready (whisper {a.model}). Hold [{a.key}]{hold} and speak; release to paste. "
                  f"Esc cancels. Learn a fix: [{a.teach_key}].", flush=True)
        except Exception:
            log_error("startup")
            self.overlay.set("error")
            print("Startup failed - see errors.log in", self.home, flush=True)
            if not models.is_downloaded(a.model):
                print(models.manual_instructions(a.model), flush=True)

    # ------------------------------------------------------------------ dictation
    def _wait_released(self, timeout=1.5):
        """Don't send Ctrl+V while a chord key (e.g. Win) is still physically down: Win+V is clipboard history."""
        t0 = time.time()
        while time.time() - t0 < timeout and any(self.talk.includes(k) or self.teach_combo.includes(k) for k in self.held):
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
            text = self.vocab.apply(raw)
            if a.cleanup:
                text = clean(text)
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
            self._wait_released()
            self.synth = True
            try:
                paste(text + " " if (a.trailing_space and not a.enter) else text, a.paste, a.enter)
                time.sleep(0.1)
            finally:
                self.synth = False
            self.overlay.set("done")
            if a.sound:
                beep("stop")
        except Exception:
            log_error("transcribe/paste")
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

    def on_press(self, key):
        if self.synth:
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
        self.held.add(kid)
        if self.teach_combo.complete(self.held) and not was_teach:
            if not self.down:
                self._cancel_pending()
                if self.teach_combo.modifier_only:        # hold it briefly, like the dictation chord
                    self._start_teach_timer()
                else:
                    threading.Thread(target=self.teach, daemon=True).start()
            return
        if self.talk.complete(self.held) and not was_talk:
            if any(not self.talk.includes(k) for k in self.held) or self.rec is None or self.paused:
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
            self._cancel_pending()                        # a shortcut (Ctrl+Win+Left ...): not a dictation

    def on_release(self, key):
        if self.synth:
            return
        kid = key_id(key)
        was_talk = self.talk.complete(self.held)
        self.held.discard(kid)
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

    def watchdog(self):
        """Auto-stop at the recording limit; free the model's memory when idle."""
        while True:
            time.sleep(0.5)
            rec, eng = self.rec, self.engine
            if self.down and rec is not None and time.time() - rec.t0 > A.MAX_SECONDS:
                with self.st:
                    self.down = False
                threading.Thread(target=self.finish, daemon=True).start()
            if (self.cfg.unload_after and eng is not None and eng.m is not None and not self.down
                    and not self.busy.locked() and time.time() - eng.last_used > self.cfg.unload_after * 60):
                eng.unload()

    def run(self):
        from pynput import keyboard
        threading.Thread(target=self.boot, daemon=True).start()
        threading.Thread(target=self.watchdog, daemon=True).start()
        keyboard.Listener(on_press=self.on_press, on_release=self.on_release).start()
        if self.tray:
            from .tray import start_tray
            self.tray = start_tray(self)
        self.overlay.run()      # blocks until the process is closed
