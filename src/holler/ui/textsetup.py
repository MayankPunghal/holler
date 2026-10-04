"""Setup without a window (SSH, no Tk): a few questions in the terminal."""
from .. import config, models, process


def run_text_setup() -> int:
    cfg = config.load()
    print("Holler setup\n")
    print("Models:")
    names = list(models.MODELS)
    for i, n in enumerate(names, 1):
        mb, ram, note = models.MODELS[n]
        print(f"  {i}. {n:10} {mb:>5} MB download, ~{ram} MB RAM - {note}")
    pick = input(f"Model [{names.index(cfg['model']) + 1}]: ").strip()
    if pick.isdigit() and 1 <= int(pick) <= len(names):
        cfg["model"] = names[int(pick) - 1]
    key = input(f"Hold which key/chord to dictate? [{cfg['key']}]: ").strip()
    if key:
        cfg["key"] = key
    try:
        from ..keys import Combo
        Combo(cfg["key"])
    except ValueError as e:
        print(e)
        return 1
    if not models.is_downloaded(cfg["model"]):
        print(f"Downloading {cfg['model']} ...")
        models.download(cfg["model"], lambda f, t: print(f"\r  {f * 100:3.0f}%  {t}   ", end="", flush=True))
        print()
    cfg["setup_done"] = True
    config.save(cfg)
    if input("Start with the computer? [Y/n]: ").strip().lower() != "n":
        process.set_autostart(True)
    print("Done. Run: holler start")
    return 0
