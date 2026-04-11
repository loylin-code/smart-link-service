"""
Agent context management
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class AgentContext:
    """
    Runtime context for agent execution
    Manages state, variables, and execution history
    """
    
    def __init__(self):
        # State storage
        self.state: Dict[str, Any] = {}
        
        # Variables
        self.variables: Dict[str, Any] = {}
        
        # Execution history
        self.history: List[Dict[str, Any]] = []
        
        # Messages (for LLM)
        self.messages: List[Dict[str, str]] = []
        
        # Metadata
        self.metadata: Dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "app_id": None,
            "conversation_id": None
        }
        
        # Tool results
        self.tool_results: Dict[str, Any] = {}
    
    def init(
        self,
        app_config: Dict[str, Any],
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ):
        """
        Initialize context with app configuration
        
        Args:
            app_config: Application configuration
            input_data: Input data from user
            conversation_id: Conversation ID (if continuing)
        """
        self.metadata["start_time"] = datetime.now(timezone.utc)
        self.metadata["app_id"] = app_config.get("id")
        self.metadata["conversation_id"] = conversation_id
        
        # Initialize state from app config
        if "initial_state" in app_config:
            self.state.update(app_config["initial_state"])
        
        # Set input data
        self.variables["input"] = input_data
        
        # Add initial user message
        if "message" in input_data:
            self.messages.append({
                "role": "user",
                "content": input_data["message"]
            })
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state"""
        return self.state.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set value in state"""
        self.state[key] = value
    
    def update(self, node_id: str, result: Any):
        """
        Update context with node execution result
        
        Args:
            node_id: Node identifier
            result: Execution result
        """
        # Store in history
        self.history.append({
            "node_id": node_id,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Update state if result is a dict
        if isinstance(result, dict):
            self.state.update(result)
    
    def add_message(self, role: str, content: str):
        """Add message to conversation"""
        self.messages.append({
            "role": role,
            "content": content
        })
    
    def add_tool_result(self, tool_call_id: str, result: Any):
        """Add tool execution result"""
        self.tool_results[tool_call_id] = result
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get all messages"""
        return self.messages.copy()
    
    def get_final_result(self) -> Dict[str, Any]:
        """
        Get final execution result
        
        Returns:
            Final result dict
        """
        self.metadata["end_time"] = datetime.now(timezone.utc)
        
        # Get last assistant message
        assistant_messages = [
            msg for msg in self.messages 
            if msg["role"] == "assistant"
        ]
        
        content = ""
        if assistant_messages:
            content = assistant_messages[-1]["content"]
        
        return {
            "content": content,
            "state": self.state,
            "history": self.history,
            "metadata": self.metadata
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict"""
        return {
            "state": self.state,
            "variables": self.variables,
            "history": self.history,
            "messages": self.messages,
            "metadata": self.metadata,
            "tool_results": self.tool_results
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentContext":
        """Deserialize context from dict"""
        ctx = cls()
        ctx.state = data.get("state", {})
        ctx.variables = data.get("variables", {})
        ctx.history = data.get("history", [])
        ctx.messages = data.get("messages", [])
        ctx.metadata = data.get("metadata", {})
        ctx.tool_results = data.get("tool_results", {})
        return ctx