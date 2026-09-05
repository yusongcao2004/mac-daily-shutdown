#!/usr/bin/env python3
"""Build only. Does not install, read activity, send messages, or shut down."""
import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'build/日报后关机.app')
    args = parser.parse_args()
    app = args.output.resolve()
    if app.exists():
        raise SystemExit('Output already exists; choose a new --output path.')
    executable = app/'Contents/MacOS/DailyShutdown'
    executable.parent.mkdir(parents=True)
    resources = app/'Contents/Resources/backend'
    resources.mkdir(parents=True)
    for name in ('runner.py', 'settings.py', 'daily_scan.py', 'verify_wechat.mjs', 'mail_brief.py', 'codex_runtime.py'):
        shutil.copy2(ROOT/'src'/name, resources/name)
    info = {
        'CFBundleExecutable': 'DailyShutdown',
        'CFBundleIdentifier': 'local.dailyshutdown.workflow',
        'CFBundleName': '日报后关机',
        'CFBundleDisplayName': '日报后关机',
        'CFBundleVersion': '1', 'CFBundleShortVersionString': '1.0',
        'CFBundlePackageType': 'APPL', 'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
        'PythonExecutable': sys.executable,
        'NSAppleEventsUsageDescription': '仅在用户点击生成日报并关机、微信接口接收且倒计时结束后，请求正常关机。',
    }
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-framework', 'Cocoa',
                    str(ROOT/'src/App.m'), '-o', str(executable)], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    print(app)

if __name__ == '__main__':
    main()
