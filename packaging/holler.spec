# PyInstaller build of the Windows app:  pyinstaller packaging/holler.spec  (run from the repo root)
# Produces dist/Holler/ with Holler.exe (no console: tray, wizard, settings) and holler-cli.exe (console: every
# `holler ...` command), sharing one _internal folder. A folder build, not one-file: it starts faster and is
# flagged far less often by antivirus software.
import os
import re
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
VERSION = re.search(r'__version__ = "([^"]+)"', open(os.path.join(ROOT, "src", "holler", "__init__.py")).read()).group(1)
NUMS = tuple(int(n) for n in re.findall(r"\d+", VERSION)[:3]) + (0,)
ASSETS = os.path.join(ROOT, "build", "brand")

from holler.brand import write_assets                     # noqa: E402  logo, icon and installer images
write_assets(ASSETS)

datas, binaries, hidden = [], [], []
for pkg in ("holler", "faster_whisper", "ctranslate2", "tokenizers", "onnxruntime", "sv_ttk", "sounddevice",
            "_sounddevice_data", "soxr", "pystray", "pynput", "onnx_asr", "huggingface_hub"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hidden += h
hidden += collect_submodules("holler") + ["pynput.keyboard._win32", "pynput.mouse._win32", "pystray._win32"]

version_file = os.path.join(ROOT, "build", "version_info.txt")
with open(version_file, "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={NUMS}, prodvers={NUMS}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Mayank Punghal'),
      StringStruct('FileDescription', 'Holler - offline push-to-talk dictation'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'Holler'),
      StringStruct('LegalCopyright', 'Copyright (c) Mayank Punghal. MIT licence.'),
      StringStruct('OriginalFilename', 'Holler.exe'),
      StringStruct('ProductName', 'Holler'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["torch", "tensorflow", "matplotlib", "scipy", "pandas", "IPython", "pytest", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = os.path.join(ASSETS, "holler.ico")
common = dict(exclude_binaries=True, debug=False, strip=False, upx=False, icon=icon, version=version_file)
gui = EXE(pyz, a.scripts, [], name="Holler", console=False, **common)
cli = EXE(pyz, a.scripts, [], name="holler-cli", console=True, **common)
COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False, name="Holler")
