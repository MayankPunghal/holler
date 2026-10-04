"""Command line.

    holler               open Holler: first time the setup wizard; if it is running the settings window;
                         otherwise start it in the background (the terminal can be closed)
    holler run           run in this terminal (what start-with-Windows uses)
    holler setup         setup wizard        holler settings   settings window
    holler start / stop / restart / status   background control
    holler autostart on|off|status           start with the computer
    holler suggest [--add]   terms you say often that your vocabulary lacks
    holler doctor        check microphone, model, hotkey, pill
    holler import FOLDER|--pack NAME merge keywords/replacements from an older install
    holler export-model FOLDER   copy the downloaded model out, named for re-hosting
    holler bench record|run   compare speech models on your own voice
    holler keys          show key names      holler where      show the data folder
"""
import argparse
import os
import sys

from . import __version__, config, process
from .paths import data_dir, log_error

OVERRIDES = [  # command-line overrides for `run`; anything left out uses the saved settings
    ("--key", "key", str), ("--hold-ms", "hold_ms", int), ("--teach-key", "teach_key", str),
    ("--engine", "engine", str), ("--model", "model", str), ("--beam", "beam", int), ("--unload-after", "unload_after", float),
    ("--lang", "lang", str), ("--paste", "paste", str), ("--ui", "ui", str), ("--device", "device", str),
]


def build_parser():
    ap = argparse.ArgumentParser(prog="holler", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"holler {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    run = sub.add_parser("run", help="run in this terminal (until you close it)")
    for flag, dest, typ in OVERRIDES:
        run.add_argument(flag, dest=dest, type=typ, default=None)
    run.add_argument("--no-overlay", action="store_true")
    run.add_argument("--no-tray", action="store_true")
    run.add_argument("--no-sound", action="store_true")
    run.add_argument("--no-wizard", action="store_true", help="don't open the setup wizard on first run")
    run.add_argument("--download-only", action="store_true", help="download the model and exit")
    sub.add_parser("setup", help="setup wizard").add_argument("--text", action="store_true", help="no window")
    sub.add_parser("settings", help="settings window")
    sub.add_parser("doctor", help="check that everything works").add_argument(
        "--pill", action="store_true", help="also play the status pill through all its states")
    for n, h in (("start", "start in the background"), ("stop", "stop the background instance"),
                 ("restart", "restart the background instance"), ("status", "is it running?"),
                 ("keys", "print the name of each key you press"),
                 ("where", "print the data folder")):
        sub.add_parser(n, help=h)
    sub.add_parser("supervise", help="run in the background and restart automatically if it crashes")
    imp = sub.add_parser("import", help="merge keywords/replacements from a folder (older install) or a starter pack")
    imp.add_argument("folder", nargs="?", default=None)
    imp.add_argument("--pack", default=None, help="a bundled starter pack, e.g. web (see: holler packs)")
    sub.add_parser("packs", help="list the bundled starter vocabulary packs")
    ty = sub.add_parser("try", help="show what Holler would paste for a sentence, no microphone needed")
    ty.add_argument("text", nargs="+")
    sg = sub.add_parser("suggest", help="find terms you dictate often that are missing from your vocabulary")
    sg.add_argument("--add", action="store_true", help="add the suggestions to your vocabulary")
    ex = sub.add_parser("export-model", help="copy a downloaded model to FOLDER, named for re-hosting as a mirror")
    ex.add_argument("folder")
    ex.add_argument("--model", default=None, help="default: the model in your settings")
    ex.add_argument("--all", action="store_true", help="export every downloaded catalogue model")
    bn = sub.add_parser("bench", help="compare speech models on your own voice (record, then run)")
    bn.add_argument("action", choices=["record", "run"])
    bn.add_argument("--set", dest="kind", choices=["english", "hinglish"], default="english", help="which sentences to use")
    bn.add_argument("folder", nargs="?", default=None, help="clips folder (default: bench-set in the data folder)")
    bn.add_argument("--models", default=None, help="comma-separated, e.g. small.en,base.en,parakeet:nemo-parakeet-tdt-0.6b-v3. Suffix @hi / @en sets the language, +hing adds the Roman-Hinglish prompt: small@en+hing")
    bn.add_argument("--engine", default="whisper")
    bn.add_argument("--no-hotwords", action="store_true", help="do not give Whisper your vocabulary")
    bn.add_argument("--raw", action="store_true", help="score the raw transcript (skip vocabulary fixes and cleanup)")
    a = sub.add_parser("autostart", help="start with the computer")
    a.add_argument("state", choices=["on", "off", "status"])
    return ap


def cmd_run(ns) -> int:
    cfg = config.settings({d: getattr(ns, d) for _, d, _ in OVERRIDES})
    if ns.no_overlay:
        cfg.overlay = False
    if ns.no_sound:
        cfg.sound = False
    if not cfg.setup_done and not ns.no_wizard and not ns.download_only:
        from .ui.wizard import run_wizard
        if not run_wizard(launch=False):
            return 1
        cfg = config.settings({d: getattr(ns, d) for _, d, _ in OVERRIDES})
    if not ns.download_only and not os.environ.get("HOLLER_SUPERVISED") and not process.claim():
        print("Holler is already running (stop it with: holler stop).")
        return 1
    from .app import App
    try:
        import faulthandler                  # a hard crash (native library) leaves a trace in crash.log
        faulthandler.enable(open(os.path.join(data_dir(), "crash.log"), "a"))
    except (OSError, RuntimeError, ValueError):
        pass
    try:
        App(cfg, download_only=ns.download_only, tray=not ns.no_tray).run()
    except ValueError as e:                  # bad key name
        sys.exit(str(e))
    except KeyboardInterrupt:
        pass
    except Exception:
        log_error("fatal")
        raise
    return 0


def cmd_open() -> int:
    """Bare `holler`: the one command to remember."""
    if not config.load()["setup_done"]:
        from .ui.wizard import run_wizard
        return 0 if run_wizard(launch=True) else 1
    if process.running_pid():
        from .ui.settings import run_settings
        return run_settings()
    process.start_background()
    print("Holler is running in the background (look for its icon in the system tray).\n"
          "You can close this window. Run `py -m holler` again, or click the tray icon, to open Settings.")
    return 0


def cmd_keys():
    from pynput import keyboard
    from .keys import key_name

    def show(k):
        print("key:", key_name(k), flush=True)
        return k != keyboard.Key.esc
    print("Press keys to see their names (Esc quits). Join with +, e.g. ctrl+win", flush=True)
    with keyboard.Listener(on_press=show) as lst:
        lst.join()


def main(argv=None) -> int:
    ns = build_parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    cmd = ns.cmd or "open"
    if cmd == "open":
        return cmd_open()
    if cmd == "run":
        return cmd_run(ns)
    if cmd == "supervise":
        return process.supervise()
    if cmd == "setup":
        if ns.text:
            from .ui.textsetup import run_text_setup
            return run_text_setup()
        from .ui.wizard import run_wizard
        return 0 if run_wizard() else 1
    if cmd == "settings":
        from .ui.settings import run_settings
        return run_settings()
    if cmd == "start":
        print("Started." if process.start_background() else "Already running.")
    elif cmd == "stop":
        print("Stopped." if process.stop() else "Not running.")
    elif cmd == "restart":
        process.restart_background()
        print("Restarted.")
    elif cmd == "status":
        pid = process.running_pid()
        print(f"Running (pid {pid})." if pid else "Not running.")
        print("Starts with the computer:", "yes" if process.autostart_enabled() else "no")
    elif cmd == "autostart":
        if ns.state == "status":
            print("on" if process.autostart_enabled() else "off")
        else:
            print("OK" if process.set_autostart(ns.state == "on") else "Could not change it on this system.")
    elif cmd == "import":
        import os
        from .paths import PACKAGE_DATA
        from .vocab import Vocab
        folder = ns.folder
        if ns.pack:
            folder = os.path.join(PACKAGE_DATA, "packs", ns.pack)
            if not os.path.isdir(folder):
                print(f"No pack called {ns.pack!r}. See: holler packs")
                return 1
        if not folder:
            print("Give a folder to import, or --pack NAME (see: holler packs).")
            return 1
        if not os.path.isdir(folder):
            print(f"Folder not found: {folder}")
            return 1
        k, r = Vocab(data_dir(), PACKAGE_DATA).import_from(folder)
        print(f"Imported {k} keyword(s) and {r} correction(s).")
    elif cmd == "try":
        from .cleanup import clean
        from .paths import PACKAGE_DATA
        from .spoken import apply_commands, smart_format
        from .vocab import Vocab
        c = config.settings()
        t = Vocab(data_dir(), PACKAGE_DATA).apply(" ".join(ns.text))
        t = clean(t) if c.cleanup else t
        t = apply_commands(t) if c.spoken_commands else t
        print(smart_format(t) if c.smart_format else t)
    elif cmd == "suggest":
        import os
        from .paths import PACKAGE_DATA
        from .suggest import suggest
        from .vocab import Vocab
        v = Vocab(data_dir(), PACKAGE_DATA)
        found = suggest(os.path.join(data_dir(), "dictation_log.tsv"), v.keyword_list())
        if not found:
            print("Nothing to suggest yet. Dictate more (the history log must be on) and try again.")
        for term, n in found:
            print(f"  {term}  ({n}x)")
        if found and ns.add:
            added = sum(v.add_keyword(t) for t, _ in found)
            print(f"Added {added} term(s).")
        elif found:
            print("Add them with: holler suggest --add")
    elif cmd == "packs":
        import os
        from .paths import PACKAGE_DATA
        root = os.path.join(PACKAGE_DATA, "packs")
        for n in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            print(" ", n)
        print("Add one with: holler import --pack NAME")
    elif cmd == "export-model":
        import os
        from . import models
        names = [n for n in models.MODELS if models.is_downloaded(n)] if ns.all else [ns.model or config.load()["model"]]
        if not names:
            print("No catalogue models are downloaded yet.")
            return 1
        os.makedirs(ns.folder, exist_ok=True)
        for name in names:
            if name not in models.MODELS or not models.is_downloaded(name):
                print(f"{name}: not a downloaded catalogue model, skipped.")
                continue
            for f in models.export(name, ns.folder):
                print(f)
    elif cmd == "bench":
        from . import bench
        folder = ns.folder or bench.default_folder(ns.kind)
        if ns.action == "record":
            return bench.record(folder, config.load()["device"], bench.HINGLISH_PROMPTS if ns.kind == "hinglish" else None)
        names = [m.strip() for m in (ns.models or config.load()["model"]).split(",") if m.strip()]
        results = bench.run(folder, names, engine=ns.engine, hotwords=not ns.no_hotwords, pipeline=not ns.raw)
        print("\n" + bench.table(results))
        for r in results:
            for w in r["worst"][:2]:
                print(f"  [{r['model']}] {w['clip']}: expected \"{w['expected']}\"  got \"{w['got']}\"")
        print("\nSaved:", bench.save_results(folder, results))
    elif cmd == "doctor":
        from .doctor import run_doctor
        rc = run_doctor()
        if ns.pill:
            from .overlay import demo
            print("\nShowing the pill now: look at the bottom of your screen (open another app first).")
            demo()
        return rc
    elif cmd == "keys":
        cmd_keys()
    elif cmd == "where":
        print(data_dir())
    return 0


def main_gui() -> int:
    """Entry point without a console window (`holler-gui`): run in the background with the tray icon."""
    return main(["supervise"])
