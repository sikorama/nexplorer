# PyInstaller spec, shared by the Linux and Windows builds.
# Run from the repository root: pyinstaller packaging/nexplorer.spec
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "nexplorer" / "locales"), "nexplorer/locales"),
        (str(root / "nexplorer" / "ui" / "svg"), "nexplorer/ui/svg"),
    ],
    hiddenimports=["send2trash"],  # imported lazily, at call time
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="nexplorer",
    console=False,
    icon=str(root / "packaging" / "icon.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="nexplorer")
