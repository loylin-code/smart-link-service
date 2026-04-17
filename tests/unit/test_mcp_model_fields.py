"""Tests for MCPServer model fields"""
import pytest
from models.application import MCPServer, ResourceStatus


class TestMCPServerFields:
    """Tests for MCPServer model field presence"""
    
    def test_mcp_server_has_last_connected_at_field(self) -> None:
        """MCPServer should have last_connected_at field"""
        assert hasattr(MCPServer, 'last_connected_at')
        from sqlalchemy import DateTime
        column = MCPServer.__table__.columns.get('last_connected_at')
        assert column is not None
        assert isinstance(column.type, DateTime)
    
    def test_mcp_server_has_last_error_field(self) -> None:
        """MCPServer should have last_error field"""
        assert hasattr(MCPServer, 'last_error')
        from sqlalchemy import Text
        column = MCPServer.__table__.columns.get('last_error')
        assert column is not None
        assert isinstance(column.type, Text)
    
    def test_mcp_server_has_prompts_field(self) -> None:
        """MCPServer should have prompts field for MCP Prompts"""
        assert hasattr(MCPServer, 'prompts')
        from sqlalchemy import JSON
        column = MCPServer.__table__.columns.get('prompts')
        assert column is not None
        assert isinstance(column.type, JSON)
    
    def test_mcp_server_field_defaults(self) -> None:
        """MCPServer prompts should default to empty list callable"""
        prompts_column = MCPServer.__table__.columns.get('prompts')
        assert prompts_column is not None
        # SQLAlchemy stores the callable (list) wrapped in CallableColumnDefault
        # Check that the callable is the list function by name
        assert prompts_column.default.arg.__name__ == 'list'
