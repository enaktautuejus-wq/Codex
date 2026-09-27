from dataclasses import dataclass
import os

@dataclass
class Config:
    base_url: str
    api_key: str
    model: str
    workspace: str
    max_tokens: int = 2048
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

def load_workspace() -> str:
    return os.path.abspath(os.environ.get("CODEX_WORKSPACE", os.getcwd()))
