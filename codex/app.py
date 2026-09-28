from __future__ import annotations
import os
from .api import post_json
from .config import Config
from .ui import setup, verify, choose_workspace, run_ui
from .tools import ToolRegistry
from .agent import Agent
from .project import ProjectIndex


def main():
    config = setup()

    def verification():
        post_json(
            config.endpoint,
            config.api_key,
            {
                "model": config.model,
                "messages": [{"role": "user", "content": "Reply exactly OK"}],
                "max_tokens": 8,
                "temperature": 0,
            },
            timeout=30,
        )

    verify(config, verification)

    # Choose the actual project/work directory only after API verification.
    workspace = choose_workspace()
    config.workspace = workspace
    os.chdir(workspace)

    registry = ToolRegistry(workspace)
    registry.config = config
    print("Menganalisis isi folder proyek...", flush=True)
    index = registry.project.scan()
    print(f"Analisis selesai: {index['files']} file, {index['directories']} folder.")
    agent = Agent(config, registry)
    try:
        run_ui(agent, config, registry)
    except KeyboardInterrupt:
        print()
    finally:
        # ui.run_ui normally restores this; repeat defensively so Ctrl+C never
        # leaves Termux in an alternate/raw-looking terminal state.
        print("\033[0m\033[?1049l", end="", flush=True)
