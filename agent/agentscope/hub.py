"""AgentHub - Central message coordination for multi-agent conversations."""
from typing import List, Any, Optional


class AgentHub:
    """
    Central hub for managing multi-agent conversation state.
    Implements singleton pattern to ensure single shared state.
    """
    
    _instance: Optional["AgentHub"] = None
    
    def __init__(self) -> None:
        """Initialize AgentHub with empty state."""
        self.hub: Any = None
        self.participants: List[Any] = []
        self.message_history: List[Any] = []
    
    @classmethod
    def get_instance(cls) -> "AgentHub":
        """Get the singleton instance of AgentHub."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self, agents: List[Any]) -> None:
        """
        Initialize the hub with participant agents.
        
        Args:
            agents: List of agent instances to participate in conversation
        """
        self.participants = agents
        self.message_history = []
    
    def get_history(self, limit: Optional[int] = None) -> List[Any]:
        """
        Get message history with optional limit.
        
        Args:
            limit: Maximum number of recent messages to return.
                   If None, returns all history.
        
        Returns:
            List of messages from history
        """
        if limit is None:
            return self.message_history.copy()
        if limit <= 0:
            return []
        return self.message_history[-limit:].copy()
