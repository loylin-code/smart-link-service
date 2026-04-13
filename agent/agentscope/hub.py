"""AgentHub - Central message coordination for multi-agent conversations."""
from typing import List, Any, Optional

from agentscope.pipeline import MsgHub
from agentscope.message import Msg


class AgentHub:
    """
    Central hub for managing multi-agent conversation state.
    Implements singleton pattern to ensure single shared state.
    Wraps AgentScope MsgHub for message coordination.
    """
    
    _instance: Optional["AgentHub"] = None
    
    def __init__(self) -> None:
        """Initialize AgentHub with empty state."""
        self.hub: Any = None
        self._msghub: Optional[MsgHub] = None
        self.participants: List[Any] = []
        self.message_history: List[Any] = []
    
    @classmethod
    def get_instance(cls) -> "AgentHub":
        """Get the singleton instance of AgentHub."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
    
    async def initialize(self, agents: List[Any]) -> None:
        """
        Initialize the hub with participant agents.
        
        Args:
            agents: List of agent instances to participate in conversation
        """
        self.participants = agents
        self.message_history = []
    
    async def initialize_with_msghub(
        self,
        participants: List[Any],
        announcement: Any
    ) -> None:
        """
        Initialize the hub with AgentScope MsgHub.
        
        Args:
            participants: List of agent instances to participate in conversation
            announcement: Initial announcement message
        """
        self.participants = participants
        self._msghub = MsgHub(
            participants=participants,
            announcement=announcement
        )
        self.message_history = []
    
    async def broadcast(self, msg: Msg) -> None:
        """
        Broadcast a message to all participants.
        
        Args:
            msg: Message to broadcast
        """
        if self._msghub is not None:
            await self._msghub.broadcast(msg)
    
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
    
    def add_participant(self, agent: Any) -> None:
        """
        Add a participant to the hub.
        
        Args:
            agent: Agent instance to add
        """
        if agent not in self.participants:
            self.participants.append(agent)
    
    def remove_participant(self, agent: Any) -> None:
        """
        Remove a participant from the hub.
        
        Args:
            agent: Agent instance to remove
        """
        if agent in self.participants:
            self.participants.remove(agent)
