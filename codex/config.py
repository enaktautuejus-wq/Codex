from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path


@dataclass
class Config:
    base_url: str
    api_key: str
    model: str
    workspace: str
    max_tokens: int | None = None
    temperature: float = 0.15
    stream: bool = True

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ValueError("Base URL harus diawali http:// atau https://.")
    return value


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()


def config_path() -> Path:
    return codex_home() / "config.json"


def has_saved_config() -> bool:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return all(str(data.get(k, "")).strip() for k in ("base_url", "api_key", "model"))
    except (OSError, ValueError, TypeError):
        return False


def load_saved_config(workspace: str) -> Config | None:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        base = normalize_base_url(str(data["base_url"]))
        key = str(data["api_key"]).strip()
        model = str(data["model"]).strip()
        if not key or not model:
            return None
        temperature = float(data.get("temperature", 0.15))
        temperature = max(0.0, min(1.0, temperature))
        stream = bool(data.get("stream", True))
        return Config(base, key, model, workspace, max_tokens=None, temperature=temperature, stream=stream)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def save_config(config: Config) -> None:
    home = codex_home()
    home.mkdir(parents=True, exist_ok=True)
    path = config_path()
    data = {"base_url": config.base_url, "api_key": config.api_key, "model": config.model,
            "temperature": config.temperature, "stream": config.stream}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def update_api_key(api_key: str) -> None:
    path = config_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["api_key"] = api_key.strip()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_workspace() -> str:
    return os.path.abspath(os.environ.get("CODEX_WORKSPACE", os.getcwd()))
