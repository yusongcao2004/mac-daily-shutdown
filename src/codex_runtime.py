"""Select an installed Codex runtime and expose actionable process errors."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


class CodexCompatibilityError(RuntimeError):
    """A client-level failure that also prevents the report generation step."""


def runtime_version(binary):
    try:
        result = subprocess.run([str(binary), '--version'], capture_output=True,
                                text=True, timeout=10)
        match = re.search(r'codex-cli\s+(\d+)\.(\d+)\.(\d+)', result.stdout)
        if result.returncode == 0 and match:
            return tuple(int(part) for part in match.groups())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def resolve_codex(configured='auto', candidates=None):
    """Respect explicit paths; auto picks the newest usable local installation."""
    if configured and configured != 'auto':
        binary = Path(configured).expanduser()
        if runtime_version(binary) is None:
            raise RuntimeError('配置的 Codex CLI 无法运行，请检查 codex_binary 路径。')
        return str(binary)
    if candidates is None:
        candidates = [base/app/'Contents/Resources/codex'
            for base in (Path('/Applications'), Path.home()/'Applications')
            for app in ('ChatGPT.app', 'Codex.app')]
        candidates += [Path('/opt/homebrew/bin/codex'), Path('/usr/local/bin/codex')]
        on_path = shutil.which('codex')
        if on_path:
            candidates.append(Path(on_path))
    choices = []
    seen = set()
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if not path.is_file() or not os.access(path, os.X_OK):
            continue
        canonical = path.resolve()
        if canonical in seen:
            continue
        seen.add(canonical)
        version = runtime_version(path)
        if version is not None:
            choices.append((version, str(path)))
    if not choices:
        raise RuntimeError('未找到可运行的 Codex CLI。请安装或更新 Codex，并检查本地配置。')
    # Stable max keeps the first candidate when versions tie.
    return max(choices, key=lambda choice: choice[0])[1]


def process_error(binary, exit_code, log):
    """Only inspect process-level JSON errors, never tool payloads or mail text."""
    reason = ''
    if log and Path(log).is_file():
        with Path(log).open('rb') as stream:
            stream.seek(max(0, Path(log).stat().st_size - 65536))
            tail = stream.read().decode('utf-8', errors='replace')
        for line in tail.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') == 'turn.failed':
                reason = event.get('error', {}).get('message', '')
            elif event.get('type') == 'error':
                reason = event.get('message', '')
        for _ in range(3):
            try:
                nested = json.loads(reason)
            except (ValueError, TypeError):
                break
            if not isinstance(nested, dict):
                break
            reason = nested.get('error', nested)
            reason = reason.get('message', '') if isinstance(reason, dict) else str(reason)
    name = Path(binary).name
    logfile = Path(log).name if log else '进程日志'
    if 'requires a newer version of Codex' in reason:
        match = re.search(r"'([^']+)' model", reason)
        model = match.group(1) if match else '当前模型'
        return CodexCompatibilityError(
            f'Codex CLI 版本过旧，不支持 {model}。请更新 Codex 或把 codex_binary 设为 auto。日志：{logfile}')
    if name == 'codex':
        if 'usage limit' in reason.lower() or 'quota' in reason.lower():
            return RuntimeError(f'Codex 使用额度暂不可用，请查看账号额度后重试。日志：{logfile}')
        if 'unauthorized' in reason.lower() or 'authentication' in reason.lower():
            return RuntimeError(f'Codex 登录验证失败，请重新登录后重试。日志：{logfile}')
        return RuntimeError(f'Codex 生成失败（退出码 {exit_code}）。详细原因见本次运行目录的 {logfile}。')
    return RuntimeError(f'{name} 运行失败（退出码 {exit_code}）。日志：{logfile}')
