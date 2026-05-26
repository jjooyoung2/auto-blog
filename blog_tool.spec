# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# google-genai 관련 숨겨진 데이터/모듈 수집
google_genai_datas = collect_data_files('google.genai')
google_genai_datas += collect_data_files('google.ai.generativelanguage_v1beta')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Flask 템플릿·정적 파일 번들
        ('templates', 'templates'),
        ('static', 'static'),
        # google-genai 데이터 파일
        *google_genai_datas,
    ],
    hiddenimports=[
        # Flask 관련
        'flask',
        'flask.templating',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'dotenv',
        'undetected_chromedriver',
        # Google GenAI
        'google.genai',
        'google.genai.types',
        'google.ai.generativelanguage_v1beta',
        'google.api_core',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.auth.credentials',
        'google.protobuf',
        # Selenium
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.command',
        'selenium.webdriver.remote.remote_connection',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.common.action_chains',
        'selenium.webdriver.common.desired_capabilities',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        # webdriver-manager
        'webdriver_manager',
        'webdriver_manager.chrome',
        # 기타
        'pyperclip',
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'PyQt5',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='blog_tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='blog_tool',
)
