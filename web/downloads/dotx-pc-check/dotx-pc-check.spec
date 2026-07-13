# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['pccheck', 'pccheck.engine', 'pccheck.models', 'pccheck.report.text_report']
hiddenimports += collect_submodules('pccheck')


a = Analysis(
    ['C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check\\gui_app.py'],
    pathex=['C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check'],
    binaries=[],
    datas=[('C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check\\assets', 'assets'), ('C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check\\pccheck\\data\\traces.jsonl', 'pccheck/data'), ('C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check\\pccheck\\data\\cheat_domains.txt', 'pccheck/data')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='dotx-pc-check',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check\\assets\\version_info.txt',
    icon=['C:\\Users\\Administrator\\Projects\\fivem-pc-check\\web\\downloads\\dotx-pc-check\\assets\\dotx.ico'],
)
