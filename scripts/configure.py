#!/usr/bin/env python3
"""Create local config for one explicitly chosen self-owned WeChat account."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from settings import APP_HOME, CONFIG_PATH, OPENCLAW_HOME

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', required=True, help='Existing OpenClaw Weixin account ID')
    parser.add_argument('--approve', action='store_true', help='Authorize activity/file excerpts to Codex/ChatGPT Image and reports to your own WeChat')
    args = parser.parse_args()
    if '/' in args.account or '\\' in args.account or args.account in ('.', '..'):
        parser.error('Invalid account ID')
    if CONFIG_PATH.exists():
        parser.error('Local config already exists; edit it locally instead of overwriting it.')
    account = json.loads((OPENCLAW_HOME/f'openclaw-weixin/accounts/{args.account}.json').read_text())
    target = account.get('userId')
    if not target:
        parser.error('Account has no self userId.')
    cfg = json.loads((Path(__file__).resolve().parents[1]/'config.example.json').read_text())
    cfg.update(wechat_account=args.account, wechat_target=target, approved=args.approve)
    os.umask(0o077)
    APP_HOME.mkdir(parents=True, exist_ok=True)
    os.chmod(APP_HOME, 0o700)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    print(f'Local configuration saved: {CONFIG_PATH}; approved={args.approve}')

if __name__ == '__main__':
    main()
