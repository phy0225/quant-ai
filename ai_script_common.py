from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any


AI_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "claude": {
        "check_cmd": "claude --version",
        "cmd": "claude --dangerously-skip-permissions --print {model_arg} -",
        "install_hint": "npm install -g @anthropic-ai/claude-code",
    },
    "codex": {
        "check_cmd": "codex --version",
        "cmd": 'codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --cd "{root}" {model_arg} -',
        "install_hint": "npm install -g @openai/codex",
    },
}


def green(s: str) -> str:
    return f"\033[92m{s}\033[0m"


def red(s: str) -> str:
    return f"\033[91m{s}\033[0m"


def yellow(s: str) -> str:
    return f"\033[93m{s}\033[0m"


def cyan(s: str) -> str:
    return f"\033[96m{s}\033[0m"


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def run(
    cmd: str,
    cwd: Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            input=input_text,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"command timeout ({timeout}s): {cmd}"
    except Exception as e:
        return -1, "", f"command exception: {e}"


def resolve_pytest_cmd(backend_dir: Path) -> str:
    local_pytest = backend_dir / ".venv" / "Scripts" / "pytest.exe"
    if local_pytest.exists():
        return ".\\.venv\\Scripts\\pytest"
    return "pytest"


def _shell_quote(value: str) -> str:
    return '"' + str(value).replace('"', '\\"') + '"'


def _default_ai_config_file(root: Path) -> Path | None:
    path = root / ".auto_fix.ai.json"
    return path if path.exists() else None


def load_ai_config(
    *,
    root: Path,
    config_file: Path | None = None,
    provider_override: str | None = None,
    model_override: str | None = None,
    default_timeout: int = 600,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "provider": os.getenv("AUTO_FIX_PROVIDER", "claude"),
        "model": os.getenv("AUTO_FIX_MODEL", "").strip(),
        "timeout": int(os.getenv("AUTO_FIX_AI_TIMEOUT", str(default_timeout))),
        "providers": deepcopy(AI_PROVIDER_PRESETS),
    }

    chosen_file = config_file or _default_ai_config_file(root)
    source_parts: list[str] = []
    if chosen_file:
        data = json.loads(chosen_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"invalid ai config json object: {chosen_file}")
        source_parts.append(str(chosen_file))
        for key in ("provider", "model", "timeout"):
            if key in data:
                cfg[key] = data[key]
        if isinstance(data.get("providers"), dict):
            for name, val in data["providers"].items():
                if not isinstance(val, dict):
                    continue
                cfg["providers"].setdefault(name, {})
                cfg["providers"][name].update(val)

    if provider_override:
        cfg["provider"] = provider_override
        source_parts.append("cli:provider")
    if model_override:
        cfg["model"] = model_override
        source_parts.append("cli:model")

    provider = str(cfg["provider"]).strip()
    if provider not in cfg["providers"]:
        raise ValueError(
            f"unsupported provider: {provider}, choose from {', '.join(sorted(cfg['providers'].keys()))}"
        )
    cfg["provider"] = provider
    cfg["timeout"] = max(30, int(cfg.get("timeout", default_timeout)))
    cfg["config_source"] = ", ".join(source_parts) if source_parts else "env/defaults"
    return cfg


def format_public_ai_config(ai_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": ai_cfg["provider"],
        "model": ai_cfg.get("model", ""),
        "timeout": ai_cfg.get("timeout"),
        "config_source": ai_cfg.get("config_source", "env/defaults"),
    }


def call_ai_code(root: Path, prompt: str, ai_cfg: dict[str, Any]) -> bool:
    provider = ai_cfg["provider"]
    provider_cfg = ai_cfg["providers"][provider]
    run_env = os.environ.copy()
    if provider == "claude":
        # Claude Code 禁止嵌套启动（检测 CLAUDECODE 环境变量）
        # 从子进程环境中移除该变量，允许在 Claude 会话内调用子 claude 进程
        run_env.pop("CLAUDECODE", None)
    if provider == "codex":
        codex_home = (
            Path(run_env.get("CODEX_HOME", "")).expanduser()
            if run_env.get("CODEX_HOME")
            else (root / ".codex_home")
        )
        codex_home.mkdir(parents=True, exist_ok=True)
        run_env["CODEX_HOME"] = str(codex_home)

    model = str(ai_cfg.get("model", "")).strip()
    model_arg = f"--model {_shell_quote(model)}" if model else ""
    cmd = provider_cfg["cmd"].format(root=str(root), model_arg=model_arg).strip()

    print(f"\n  {cyan('->')} calling {provider} ...", flush=True)
    chk_code, _, chk_err = run(provider_cfg["check_cmd"], cwd=root, timeout=10, env=run_env)
    if chk_code != 0:
        print(red(f"  {provider} unavailable, install hint: {provider_cfg.get('install_hint', '')}"))
        if chk_err.strip():
            print(red(f"  {chk_err.strip()[:300]}"))
        return False

    code, out, err = run(
        cmd,
        cwd=root,
        timeout=int(ai_cfg.get("timeout", 600)),
        env=run_env,
        input_text=prompt,
    )
    if code == 0:
        print(green(f"  {provider} finished"))
        if out.strip():
            for line in out.strip().splitlines()[:5]:
                print(f"  {line[:300]}")
        return True

    print(yellow(f"  {provider} non-zero return"))
    if err.strip():
        print(yellow(f"  {err.strip()[:500]}"))
    return True
