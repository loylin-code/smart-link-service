"""Tests for MCPServer model fields"""
import pytest
from models.application import MCPServer, ResourceStatus

class TestMCPServerFields:
    def test_mcp_server_has_last_connected_at_field(self):
        assert hasattr(MCPServer, 'last_connected_at')
        from sqlalchemy import DateTime
        column = MCPServer.__table__.columns.get('last_connected_at')
        assert column is not None
        assert isinstance(column.type, DateTime)
    
    def test_mcp_server_has_last_error_field(self):
        assert hasattr(MCPServer, 'last_error')
        from sqlalchemy import Text
        column = MCPServer.__table__.columns.get('last_error')
        assert column is not None
        assert isinstance(column.type, Text)
    
    def test_mcp_server_has_prompts_field(self):
        assert hasattr(MCPServer, 'prompts')
        from sqlalchemy import JSON
        column = MCPServer.__table__.columns.get('prompts')
        assert column is not None
        assert isinstance(column.type, JSON)
    
    def test_mcp_server_field_defaults(self):
        prompts_column = MCPServer.__table__.columns.get('prompts')
        # SQLAlchemy wraps callable defaults in CallableColumnDefault, arg holds the function
        default_arg = prompts_column.default.arg
        # Check if it's the list callable by checking the function name
        assert hasattr(default_arg, '__name__') and default_arg.__name__ == 'list'
