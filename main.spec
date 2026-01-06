from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --- CONFIG ---
ENTRY_POINT = 'src/phytospatial/main.py'
APP_NAME = 'phytospatial'

hidden_imports = []
hidden_imports += collect_submodules('geopandas')
hidden_imports += collect_submodules('fiona')
hidden_imports += collect_submodules('rasterio')
hidden_imports += collect_submodules('shapely')
hidden_imports += collect_submodules('sklearn')

datas = [ ('images/phytospatial.png', 'images') ]

a = Analysis(
    [ENTRY_POINT],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # NOTE: Set to False when GUI is built
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
