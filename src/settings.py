"""Local configuration and private runtime paths; no credentials in this project."""
import json
import os
from pathlib import Path

APP_HOME = Path(os.environ.get('DAILY_SHUTDOWN_HOME',
    str(Path.home() / 'Library/Application Support/DailyShutdown'))).expanduser().resolve()
CONFIG_PATH = APP_HOME / 'config.json'
CONFIG = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}

def configured_path(key, default):
    return Path(CONFIG.get(key, str(default))).expanduser().resolve()

OPENCLAW_HOME = configured_path('openclaw_home', Path.home() / '.openclaw')
CODEX_HOME_PATH = configured_path('codex_home', Path.home() / '.codex')
