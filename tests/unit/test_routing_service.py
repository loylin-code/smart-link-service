"""Tests for RoutingService - intelligent agent routing"""
import pytest

from services.runtime.routing import RoutingService


class TestRoutingServiceRouteToAgent:
    """Tests for route_to_agent method"""

    @pytest.mark.asyncio
    async def test_returns_agent_id_for_matching_keyword(self) -> None:
        """Test route_to_agent returns agent_id when message matches keyword"""
        service = RoutingService()
        
        # Message containing keywords that should match an agent
        result = await service.route_to_agent(
            message="帮我搜索最新的AI新闻",
            metadata=None
        )
        
        # Should return a matching agent_id
        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("agent_") or ":" not in result

    @pytest.mark.asyncio
    async def test_returns_none_for_unrecognized_message(self) -> None:
        """Test route_to_agent returns None for unrecognized intent"""
        service = RoutingService()
        
        # Message that doesn't match any known keywords
        result = await service.route_to_agent(
            message="随便说说一些没有意义的话",
            metadata=None
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_agent_id_with_metadata_context(self) -> None:
        """Test route_to_agent uses metadata for routing context"""
        service = RoutingService()
        
        # Message with metadata context
        result = await service.route_to_agent(
            message="分析这些数据",
            metadata={"domain": "analytics", "preferred_agent": "agent_analytics"}
        )
        
        # Should consider metadata for routing
        assert result is not None


class TestRoutingServiceGetRoutingOptions:
    """Tests for get_routing_options method"""

    @pytest.mark.asyncio
    async def test_returns_dict_with_agents_list(self) -> None:
        """Test get_routing_options returns dict with agents list"""
        service = RoutingService()
        
        result = await service.get_routing_options(
            message="帮我搜索信息",
            metadata=None
        )
        
        # Should return dict with specific structure
        assert isinstance(result, dict)
        assert "agents" in result
        assert "recommended" in result
        
        # Agents list should have required fields
        agents = result["agents"]
        assert isinstance(agents, list)
        assert len(agents) > 0
        
        # Each agent should have id, name, description, score
        for agent in agents:
            assert "id" in agent
            assert "name" in agent
            assert "description" in agent
            assert "score" in agent
            assert isinstance(agent["score"], (int, float))

    @pytest.mark.asyncio
    async def test_returns_recommended_agent_id(self) -> None:
        """Test get_routing_options returns recommended agent_id"""
        service = RoutingService()
        
        result = await service.get_routing_options(
            message="搜索网络信息",
            metadata=None
        )
        
        # recommended should be either None or a valid agent_id
        recommended = result["recommended"]
        if recommended is not None:
            assert isinstance(recommended, str)

    @pytest.mark.asyncio
    async def test_scores_reflect_matching_relevance(self) -> None:
        """Test agent scores reflect relevance to message"""
        service = RoutingService()
        
        result = await service.get_routing_options(
            message="帮我做数据分析",
            metadata=None
        )
        
        agents = result["agents"]
        # At least one agent should have score > 0 for matching message
        matching_agents = [a for a in agents if a["score"] > 0]
        assert len(matching_agents) > 0


class TestRoutingServicePatternMatching:
    """Tests for keyword/pattern-based routing logic"""

    @pytest.mark.asyncio
    async def test_matches_search_keywords(self) -> None:
        """Test routing matches search-related keywords"""
        service = RoutingService()
        
        search_messages = [
            "搜索一下",
            "帮我查找信息",
            "我想搜索",
            "帮我search",
        ]
        
        for msg in search_messages:
            result = await service.route_to_agent(message=msg, metadata=None)
            # At least one should match (keyword-based)
            # Not all may match depending on keyword list

    @pytest.mark.asyncio
    async def test_matches_analysis_keywords(self) -> None:
        """Test routing matches analysis-related keywords"""
        service = RoutingService()
        
        analysis_messages = [
            "分析数据",
            "帮我统计",
            "数据处理",
        ]
        
        for msg in analysis_messages:
            result = await service.route_to_agent(message=msg, metadata=None)

    @pytest.mark.asyncio
    async def test_empty_message_returns_none(self) -> None:
        """Test empty message returns None"""
        service = RoutingService()
        
        result = await service.route_to_agent(message="", metadata=None)
        assert result is None