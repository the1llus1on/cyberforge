from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parents[1]
migrations = collect_data_files(
    "cyberforge.persistence.migrations", include_py_files=True
)
a = Analysis(
    [str(root / "src/cyberforge/__main__.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=migrations,
    hiddenimports=collect_submodules("cyberforge.persistence.migrations")
    + ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "alembic.ddl.sqlite"],
    excludes=["tkinter"],
)
archive = PYZ(a.pure)
exe = EXE(
    archive,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CyberForge",
    console=False,
    upx=False,
    uac_admin=False,
)
bundle = COLLECT(exe, a.binaries, a.datas, name="CyberForge", upx=False)
