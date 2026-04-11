"""AgentScope multi-agent coordination module."""
# Import hub directly to avoid triggering agent package init chain
from agent.agentscope.hub import AgentHub

__all__ = ["AgentHub"]
