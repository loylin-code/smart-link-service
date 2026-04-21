"""Tests for Execution model"""
import pytest
from datetime import datetime
from models.execution import Execution, ExecutionStatus


class TestExecutionStatus:
    """Tests for ExecutionStatus enum"""
    
    def test_execution_status_pending(self) -> None:
        """ExecutionStatus.PENDING should equal 'pending'"""
        assert ExecutionStatus.PENDING.value == "pending"
    
    def test_execution_status_running(self) -> None:
        """ExecutionStatus.RUNNING should equal 'running'"""
        assert ExecutionStatus.RUNNING.value == "running"
    
    def test_execution_status_completed(self) -> None:
        """ExecutionStatus.COMPLETED should equal 'completed'"""
        assert ExecutionStatus.COMPLETED.value == "completed"
    
    def test_execution_status_cancelled(self) -> None:
        """ExecutionStatus.CANCELLED should equal 'cancelled'"""
        assert ExecutionStatus.CANCELLED.value == "cancelled"
    
    def test_execution_status_failed(self) -> None:
        """ExecutionStatus.FAILED should equal 'failed'"""
        assert ExecutionStatus.FAILED.value == "failed"


class TestExecutionModel:
    """Tests for Execution model"""
    
    def test_execution_status_enum_exists(self) -> None:
        """ExecutionStatus enum should be importable"""
        assert ExecutionStatus is not None
    
    def test_execution_class_exists(self) -> None:
        """Execution class should be importable"""
        assert Execution is not None
    
    def test_execution_has_required_columns(self) -> None:
        """Execution should have all required columns"""
        columns = Execution.__table__.columns
        assert 'id' in columns
        assert 'agent_id' in columns
        assert 'conversation_id' in columns
        assert 'status' in columns
        assert 'input_data' in columns
        assert 'output_data' in columns
        assert 'prompt_tokens' in columns
        assert 'completion_tokens' in columns
        assert 'total_tokens' in columns
        assert 'created_at' in columns
        assert 'started_at' in columns
        assert 'completed_at' in columns
        assert 'updated_at' in columns
        assert 'metadata' in columns
        assert 'error_message' in columns
        assert 'error_code' in columns
    
    def test_execution_id_is_primary_key(self) -> None:
        """Execution id should be primary key"""
        id_column = Execution.__table__.columns.get('id')
        assert id_column is not None
        assert id_column.primary_key is True
    
    def test_execution_agent_id_not_nullable(self) -> None:
        """Execution agent_id should not be nullable"""
        agent_id_column = Execution.__table__.columns.get('agent_id')
        assert agent_id_column is not None
        assert agent_id_column.nullable is False
    
    def test_execution_status_default_pending(self) -> None:
        """Execution status should default to PENDING"""
        status_column = Execution.__table__.columns.get('status')
        assert status_column is not None
        assert status_column.default.arg == ExecutionStatus.PENDING
    
    def test_execution_token_defaults_zero(self) -> None:
        """Execution token fields should default to 0"""
        prompt_tokens_column = Execution.__table__.columns.get('prompt_tokens')
        completion_tokens_column = Execution.__table__.columns.get('completion_tokens')
        total_tokens_column = Execution.__table__.columns.get('total_tokens')
        
        assert prompt_tokens_column is not None
        assert completion_tokens_column is not None
        assert total_tokens_column is not None
        
        assert prompt_tokens_column.default.arg == 0
        assert completion_tokens_column.default.arg == 0
        assert total_tokens_column.default.arg == 0
    
    def test_execution_error_fields_nullable(self) -> None:
        """Execution error_message and error_code should be nullable"""
        error_message_column = Execution.__table__.columns.get('error_message')
        error_code_column = Execution.__table__.columns.get('error_code')
        
        assert error_message_column is not None
        assert error_code_column is not None
        
        assert error_message_column.nullable is True
        assert error_code_column.nullable is True
    
    def test_execution_metadata_is_json(self) -> None:
        """Execution metadata should be JSON type"""
        from sqlalchemy import JSON
        metadata_column = Execution.__table__.columns.get('metadata')
        assert metadata_column is not None
        assert isinstance(metadata_column.type, JSON)
    
    def test_execution_input_output_is_json(self) -> None:
        """Execution input_data and output_data should be JSON type"""
        from sqlalchemy import JSON
        input_column = Execution.__table__.columns.get('input_data')
        output_column = Execution.__table__.columns.get('output_data')
        
        assert input_column is not None
        assert output_column is not None
        
        assert isinstance(input_column.type, JSON)
        assert isinstance(output_column.type, JSON)
