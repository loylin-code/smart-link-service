"""SessionMemory adapter tests for AgentScope AsyncSQLAlchemyMemory"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestSessionMemory:
    """SessionMemory adapter test class"""

    @pytest.mark.asyncio
    async def test_init_creates_memory(self):
        """Test that SessionMemory initializes AsyncSQLAlchemyMemory with user_id, session_id"""
        from agent.memory.agentscope_adapter import SessionMemory
        
        mock_db_session = AsyncMock()
        user_id = "user-123"
        session_id = "session-456"
        
        with patch('agent.memory.agentscope_adapter.AsyncSQLAlchemyMemory') as MockAsyncSQLAlchemyMemory:
            memory = SessionMemory(
                db_session=mock_db_session,
                user_id=user_id,
                session_id=session_id
            )
            
            # Verify AsyncSQLAlchemyMemory was initialized with correct params
            MockAsyncSQLAlchemyMemory.assert_called_once()
            call_kwargs = MockAsyncSQLAlchemyMemory.call_args.kwargs
            assert call_kwargs['user_id'] == user_id
            assert call_kwargs['session_id'] == session_id
            assert 'db_session' in call_kwargs
            
            # Verify memory attribute is set
            assert memory._memory is not None

    @pytest.mark.asyncio
    async def test_add_message_stores_msg(self):
        """Test that add_message creates Msg and calls memory.add"""
        from agent.memory.agentscope_adapter import SessionMemory
        from agentscope.message import Msg
        
        mock_db_session = AsyncMock()
        
        with patch('agent.memory.agentscope_adapter.AsyncSQLAlchemyMemory') as MockAsyncSQLAlchemyMemory:
            mock_memory_instance = AsyncMock()
            MockAsyncSQLAlchemyMemory.return_value = mock_memory_instance
            
            memory = SessionMemory(mock_db_session, "user-123", "session-456")
            memory._memory = mock_memory_instance
            
            role = "user"
            content = "Hello, world!"
            name = "test_user"
            
            await memory.add_message(role=role, content=content, name=name)
            
            # Verify memory.add was called
            mock_memory_instance.add.assert_called_once()
            
            # Verify Msg was created with correct params
            call_args = mock_memory_instance.add.call_args.args[0]
            assert isinstance(call_args, Msg)
            assert call_args.role == role
            assert call_args.content == content
            assert call_args.name == name

    @pytest.mark.asyncio
    async def test_get_context_returns_history(self):
        """Test that get_context returns list of Msg objects"""
        from agent.memory.agentscope_adapter import SessionMemory
        from agentscope.message import Msg
        
        mock_db_session = AsyncMock()
        
        with patch('agent.memory.agentscope_adapter.AsyncSQLAlchemyMemory') as MockAsyncSQLAlchemyMemory:
            mock_memory_instance = AsyncMock()
            MockAsyncSQLAlchemyMemory.return_value = mock_memory_instance
            
            # Setup mock get_history to return list of Msg objects
            expected_messages = [
                Msg("user", "Hello", "user"),
                Msg("assistant", "Hi there!", "assistant")
            ]
            mock_memory_instance.get_history = AsyncMock(return_value=expected_messages)
            
            memory = SessionMemory(mock_db_session, "user-123", "session-456")
            memory._memory = mock_memory_instance
            
            result = await memory.get_context()
            
            # Verify get_history was called
            mock_memory_instance.get_history.assert_called_once()
            
            # Verify result is list of Msg objects
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(msg, Msg) for msg in result)

    @pytest.mark.asyncio
    async def test_get_message_count_returns_size(self):
        """Test that get_message_count calls memory.size"""
        from agent.memory.agentscope_adapter import SessionMemory
        
        mock_db_session = AsyncMock()
        expected_count = 5
        
        with patch('agent.memory.agentscope_adapter.AsyncSQLAlchemyMemory') as MockAsyncSQLAlchemyMemory:
            mock_memory_instance = AsyncMock()
            MockAsyncSQLAlchemyMemory.return_value = mock_memory_instance
            
            # Setup mock size property
            type(mock_memory_instance).size = property(lambda self: expected_count)
            
            memory = SessionMemory(mock_db_session, "user-123", "session-456")
            memory._memory = mock_memory_instance
            
            result = await memory.get_message_count()
            
            # Verify size property was accessed
            assert result == expected_count

    @pytest.mark.asyncio
    async def test_clear_session_clears_memory(self):
        """Test that clear_session calls memory.clear"""
        from agent.memory.agentscope_adapter import SessionMemory
        
        mock_db_session = AsyncMock()
        
        with patch('agent.memory.agentscope_adapter.AsyncSQLAlchemyMemory') as MockAsyncSQLAlchemyMemory:
            mock_memory_instance = AsyncMock()
            MockAsyncSQLAlchemyMemory.return_value = mock_memory_instance
            
            memory = SessionMemory(mock_db_session, "user-123", "session-456")
            memory._memory = mock_memory_instance
            
            await memory.clear_session()
            
            # Verify memory.clear was called
            mock_memory_instance.clear.assert_called_once()
