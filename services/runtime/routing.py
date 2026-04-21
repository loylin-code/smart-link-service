"""
RoutingService - Intelligent agent routing service

Routes user messages to appropriate agents based on keyword/pattern matching.
Designed to support future extension via PlanAgent for LLM-based routing.
"""


# Keyword-based routing rules (simple pattern matching)
ROUTING_KEYWORDS: dict[str, list[str]] = {
    "agent_search": ["搜索", "查找", "search", "检索", "查询", "找"],
    "agent_analytics": ["分析", "统计", "数据", "analytics", "analyze", "处理"],
    "agent_assistant": ["帮助", "助手", "assistant", "帮我", "hello", "你好"],
}

# Agent descriptions for routing options display
AGENT_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "agent_search": {
        "name": "搜索助手",
        "description": "网络搜索和信息检索Agent",
    },
    "agent_analytics": {
        "name": "数据分析",
        "description": "数据分析和统计处理Agent",
    },
    "agent_assistant": {
        "name": "通用助手",
        "description": "通用对话和帮助Agent",
    },
}


class RoutingService:
    """Intelligent routing service for agent selection
    
    Routes messages to appropriate agents based on keyword matching.
    Supports future extension to use PlanAgent for LLM-based routing.
    
    Flow:
        1. Get available agents list
        2. Recognize intent via keyword matching
        3. Return recommended agent_id
    """

    async def route_to_agent(
        self,
        message: str,
        metadata: dict[str, object] | None = None
    ) -> str | None:
        """Route to appropriate agent based on message content
        
        Args:
            message: User message to route
            metadata: Additional context (e.g., domain, preferred_agent)
            
        Returns:
            agent_id if matching agent found, None otherwise
        """
        # Empty message returns None
        if not message or not message.strip():
            return None
        
        message_lower = message.lower()
        
        # Check metadata for preferred agent
        if metadata and "preferred_agent" in metadata:
            preferred = metadata["preferred_agent"]
            if isinstance(preferred, str) and preferred in AGENT_DESCRIPTIONS:
                return preferred
        
        # Keyword matching - find best match
        best_agent: str | None = None
        best_score: int = 0
        
        for agent_id, keywords in ROUTING_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in message_lower:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_agent = agent_id
        
        return best_agent

    async def get_routing_options(
        self,
        message: str,
        metadata: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Get routing options for frontend display
        
        Args:
            message: User message
            metadata: Additional context
            
        Returns:
            Dict with:
                - agents: List of agents with id, name, description, score
                - recommended: Recommended agent_id or None
        """
        # Calculate scores for all agents
        agents_list: list[dict[str, int | str]] = []
        message_lower = message.lower() if message else ""
        
        for agent_id, info in AGENT_DESCRIPTIONS.items():
            score = 0
            if agent_id in ROUTING_KEYWORDS:
                for keyword in ROUTING_KEYWORDS[agent_id]:
                    if keyword.lower() in message_lower:
                        score += 1
            
            agents_list.append({
                "id": agent_id,
                "name": info["name"],
                "description": info["description"],
                "score": score,
            })
        
        # Sort by score descending
        agents_list.sort(key=lambda x: x["score"], reverse=True)
        
        # Get recommended agent
        recommended = await self.route_to_agent(message, metadata)
        
        return {
            "agents": agents_list,
            "recommended": recommended,
        }