"""SubAgent Pool - Role-based execution agents"""
from agent.subagents.base import BaseSubAgent, SubAgentCapability, SubAgentResult
from agent.subagents.pool import SubAgentPool
from agent.subagents.research import ResearchAgent
from agent.subagents.code import CodeAgent
from agent.subagents.data import DataAgent
from agent.subagents.doc import DocAgent

__all__ = [
    "BaseSubAgent",
    "SubAgentCapability",
    "SubAgentResult",
    "SubAgentPool",
    "ResearchAgent",
    "CodeAgent",
    "DataAgent",
    "DocAgent",
]