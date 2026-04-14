"""AgentDesignService 单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestAgentDesignService:
    """AgentDesignService 测试类"""

    def _create_mock_agent(self):
        """创建 mock agent 对象"""
        mock_agent = MagicMock()
        mock_agent.id = "agent_123"
        mock_agent.page_schema = {
            "id": "schema_123",
            "version": "1.0.0",
            "root": {
                "id": "root_1",
                "type": "container",
                "name": "Root Container",
                "props": {},
                "children": []
            },
            "styles": [],
            "scripts": []
        }
        mock_agent.mcp_servers = []
        mock_agent.skills = []
        mock_agent.tools = []
        mock_agent.llm_config = {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7
        }
        return mock_agent

    def _create_mock_db(self, mock_agent=None):
        """创建 mock 数据库会话"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=mock_agent)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        return mock_db

    @pytest.mark.asyncio
    async def test_get_schema_returns_pageschema(self):
        """测试 get_schema 返回 PageSchema 对象"""
        from services.agent_design_service import AgentDesignService
        from services.agent_service import AgentService
        from schemas.agent_design import PageSchema

        # Create mock agent with page_schema
        mock_agent = self._create_mock_agent()
        mock_db = self._create_mock_db(mock_agent)

        # Patch AgentService.get_agent_by_id to return our mock agent
        with patch.object(AgentService, 'get_agent_by_id', new_callable=AsyncMock, return_value=mock_agent):
            # Call the service method
            result = await AgentDesignService.get_schema(mock_db, "agent_123")

            # Verify result is PageSchema instance
            assert result is not None
            assert isinstance(result, PageSchema)
            assert result.id == "schema_123"
            assert result.version == "1.0.0"
            assert result.root.id == "root_1"
            assert result.root.type == "container"

    @pytest.mark.asyncio
    async def test_update_schema_replaces_full_schema(self):
        """测试 update_schema 替换完整 schema"""
        from services.agent_design_service import AgentDesignService
        from services.agent_service import AgentService
        from schemas.agent_design import PageSchema, ComponentNode

        # Create mock agent
        mock_agent = self._create_mock_agent()
        mock_db = self._create_mock_db(mock_agent)

        # Create new schema to update with
        new_schema = PageSchema(
            id="schema_new",
            version="2.0.0",
            root=ComponentNode(
                id="root_new",
                type="layout",
                name="New Root",
                props={"flex": True},
                children=[]
            ),
            styles=[],
            scripts=[]
        )

        # Patch AgentService.get_agent_by_id to return our mock agent
        with patch.object(AgentService, 'get_agent_by_id', new_callable=AsyncMock, return_value=mock_agent):
            # Call the service method
            result = await AgentDesignService.update_schema(mock_db, "agent_123", new_schema)

            # Verify schema was replaced
            assert result is True
            # Verify page_schema was set to the new schema dict
            assert mock_agent.page_schema == new_schema.model_dump(by_alias=True)
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_component_to_parent(self):
        """测试 add_component 添加到父节点"""
        from services.agent_design_service import AgentDesignService
        from services.agent_service import AgentService
        from schemas.agent_design import ComponentNode, ComponentAddRequest

        # Create mock agent with schema
        mock_agent = self._create_mock_agent()
        mock_db = self._create_mock_db(mock_agent)

        # Create component to add
        new_component = ComponentNode(
            id="comp_new",
            type="button",
            name="Test Button",
            props={"label": "Click me"},
            children=[]
        )

        # Create request with parent_id
        request = ComponentAddRequest(
            parent_id="root_1",
            component=new_component
        )

        # Patch AgentService.get_agent_by_id
        with patch.object(AgentService, 'get_agent_by_id', new_callable=AsyncMock, return_value=mock_agent):
            # Call the service method
            result = await AgentDesignService.add_component(mock_db, "agent_123", request)

            # Verify component was added
            assert result is True
            # Verify flush was called to save changes
            mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_update_component_updates_props(self):
        """测试 update_component 更新属性"""
        from services.agent_design_service import AgentDesignService
        from services.agent_service import AgentService
        from schemas.agent_design import ComponentNode, ComponentUpdateRequest

        # Create mock agent with schema containing a component
        mock_agent = self._create_mock_agent()
        mock_agent.page_schema["root"]["props"] = {"initial": True}
        mock_db = self._create_mock_db(mock_agent)

        # Create update request with new props
        update_request = ComponentUpdateRequest(
            props={"updated": True, "color": "blue"},
            position={"x": 100, "y": 200}
        )

        # Patch AgentService.get_agent_by_id
        with patch.object(AgentService, 'get_agent_by_id', new_callable=AsyncMock, return_value=mock_agent):
            # Call the service method
            result = await AgentDesignService.update_component(
                mock_db,
                "agent_123",
                "root_1",
                update_request
            )

            # Verify props were updated
            assert result is True
            mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_validate_design_returns_result(self):
        """测试 validate_design 返回 ValidationResult"""
        from services.agent_design_service import AgentDesignService
        from services.agent_service import AgentService
        from schemas.agent_design import ValidationResult

        # Create mock agent with valid schema
        mock_agent = self._create_mock_agent()
        mock_db = self._create_mock_db(mock_agent)

        # Patch AgentService.get_agent_by_id
        with patch.object(AgentService, 'get_agent_by_id', new_callable=AsyncMock, return_value=mock_agent):
            # Call the service method
            result = await AgentDesignService.validate_design(mock_db, "agent_123")

            # Verify result is ValidationResult
            assert result is not None
            assert isinstance(result, ValidationResult)
            assert isinstance(result.valid, bool)
            assert isinstance(result.errors, list)
            assert isinstance(result.warnings, list)

    @pytest.mark.asyncio
    async def test_preview_execution_returns_plan(self):
        """测试 preview_execution 返回执行计划"""
        from services.agent_design_service import AgentDesignService
        from services.agent_service import AgentService

        # Create mock agent with tools
        mock_agent = self._create_mock_agent()
        mock_agent.tools = ["search", "analyze"]
        mock_db = self._create_mock_db(mock_agent)

        # Patch AgentService.get_agent_by_id
        with patch.object(AgentService, 'get_agent_by_id', new_callable=AsyncMock, return_value=mock_agent):
            # Call the service method with input data
            input_data = {"query": "test query", "limit": 10}
            result = await AgentDesignService.preview_execution(
                mock_db,
                "agent_123",
                input_data,
                mock_mode=True
            )

            # Verify result has expected structure
            assert result is not None
            assert "preview_id" in result
            assert "execution_plan" in result
            assert "estimated_tokens" in result
            assert isinstance(result["preview_id"], str)
            assert isinstance(result["execution_plan"], dict)
            assert isinstance(result["estimated_tokens"], int)
