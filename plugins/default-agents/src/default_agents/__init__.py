from __future__ import annotations

from namel3ss.ir import IRAgent
from namel3ss.plugins.sdk import PluginSDK


def register_agents(sdk: PluginSDK) -> None:
    agent = IRAgent(name="summarizer", goal="Summarize a short passage.")
    sdk.agents.register_agent(agent)
