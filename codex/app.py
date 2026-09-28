from __future__ import annotations
import os
from .api import post_json
from .config import Config, has_saved_config, save_config
from .ui import setup, verify, choose_workspace, run_ui
from .tools import ToolRegistry
from .agent import Agent
from .project import ProjectIndex


def main():
    first_run = not has_saved_config()
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

    if first_run:
        verify(config, verification)
        save_config(config)
        print("Konfigurasi tersimpan di ~/.codex/config.json")

    # Choose the actual project/work directory only after first-run setup.
    workspace = choose_workspace()
    config.workspace = workspace
    os.chdir(workspace)

    registry = ToolRegistry(workspace)
    registry.config = config
    print("Menganalisis isi folder proyek...", flush=True)
    index = registry.project.scan()
    print(f"Analisis selesai: {index['files']} file, {index['directories']} folder.")
    agent = Agent(config, registry)
    run_ui(agent, config, registry)
