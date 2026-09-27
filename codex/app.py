from __future__ import annotations
from .api import post_json
from .config import Config
from .ui import setup, verify, run_ui
from .tools import ToolRegistry
from .agent import Agent

def main():
    config = setup()

    def verification():
        post_json(
            config.endpoint,
            config.api_key,
            {
                "model": config.model,
                "messages": [{"role":"user","content":"Reply exactly OK"}],
                "max_tokens": 8,
                "temperature": 0,
            },
            timeout=30,
        )

    verify(config, verification)
    registry = ToolRegistry(config.workspace)
    agent = Agent(config, registry)
    run_ui(agent, config, registry)
