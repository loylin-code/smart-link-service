"""
Logging module unit tests
"""
import pytest
import logging
import json
import os
import shutil
import gc

from core.logging import get_logger
from core.logging.formatter import StructuredFormatter
from core.logging.audit import AuditLogger, _get_audit_logger


def _close_all_log_handlers():
    """Close all log handlers to release file locks on Windows"""
    # Close audit logger
    import core.logging.audit as audit_module
    if audit_module._audit_logger is not None:
        for handler in audit_module._audit_logger.handlers:
            handler.close()
        audit_module._audit_logger.handlers.clear()
        audit_module._audit_logger = None
    
    # Close all other loggers
    for name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(name)
        if logger and hasattr(logger, 'handlers'):
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()
    
    # Force garbage collection to release file handles
    gc.collect()


def _cleanup_logs_directory():
    """Clean up logs directory with proper handler cleanup"""
    _close_all_log_handlers()
    if os.path.exists('logs'):
        shutil.rmtree('logs')


class TestStructuredFormatter:
    """Test StructuredFormatter JSON output"""

    def test_formatter_outputs_json(self):
        """Formatter should output valid JSON"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        # Should be valid JSON
        data = json.loads(output)
        assert 'timestamp' in data
        assert 'level' in data
        assert data['level'] == 'INFO'
        assert 'message' in data
        assert data['message'] == 'Test message'

    def test_formatter_includes_extra_fields(self):
        """Formatter should include extra fields from record"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )

        # Add extra fields
        record.request_id = 'req_123'
        record.path = '/smart-link-service/api/v1/test'
        record.method = 'GET'

        output = formatter.format(record)
        data = json.loads(output)

        assert data['request_id'] == 'req_123'
        assert data['path'] == '/smart-link-service/api/v1/test'
        assert data['method'] == 'GET'

    def test_formatter_handles_exception(self):
        """Formatter should handle exception info"""
        formatter = StructuredFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name='test',
                level=logging.ERROR,
                pathname='test.py',
                lineno=1,
                msg='Error occurred',
                args=(),
                exc_info=exc_info
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert 'error_type' in data
            assert data['error_type'] == 'ValueError'
            assert 'error_message' in data
            assert 'Test error' in data['error_message']
            assert 'stack_trace' in data

    def test_formatter_includes_logger_name(self):
        """Formatter should include logger name"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name='gateway.middleware.logging',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test',
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert 'logger' in data
        assert data['logger'] == 'gateway.middleware.logging'

    def test_formatter_timestamp_format(self):
        """Formatter should use ISO 8601 format with Z suffix"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test',
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert 'timestamp' in data
        # Should end with Z (UTC)
        assert data['timestamp'].endswith('Z')
        # Should be ISO format
        assert 'T' in data['timestamp']


class TestGetLogger:
    """Test get_logger helper"""

    @pytest.fixture(autouse=True)
    def cleanup_logs(self):
        """Clean up logs directory before and after tests"""
        # Clean before
        _cleanup_logs_directory()
        yield
        # Clean after
        _cleanup_logs_directory()

    def test_get_logger_returns_logger(self):
        """get_logger should return a Logger instance"""
        logger = get_logger('test_logger')
        assert isinstance(logger, logging.Logger)

    def test_get_logger_has_handlers(self):
        """get_logger should configure handlers"""
        logger = get_logger('test_logger')
        assert len(logger.handlers) > 0

    def test_get_logger_sets_level(self):
        """get_logger should set correct log level"""
        logger = get_logger('test_logger', level='DEBUG')
        assert logger.level == logging.DEBUG

    def test_get_logger_creates_log_directory(self):
        """get_logger should create log directory if not exists"""
        logger = get_logger('test_logger')

        # logs directory should be created
        assert os.path.exists('logs')

    def test_get_logger_creates_app_log_file(self):
        """get_logger should create app.log file"""
        logger = get_logger('test_logger')
        logger.info("Test message")

        # app.log should exist
        assert os.path.exists('logs/app.log')

    def test_get_logger_creates_custom_file(self):
        """get_logger should create custom log file"""
        logger = get_logger('test_logger', file_name='custom.log')
        logger.info("Test message")

        # custom.log should exist
        assert os.path.exists('logs/custom.log')

    def test_get_logger_clears_existing_handlers(self):
        """get_logger should clear existing handlers to avoid duplicates"""
        logger = logging.getLogger('test_duplicate')
        logger.addHandler(logging.StreamHandler())

        # Call get_logger should clear and add new handlers
        logger = get_logger('test_duplicate')
        # Should have exactly stdout + file handlers (2)
        assert len(logger.handlers) == 2


class TestAuditLogger:
    """Test AuditLogger"""

    @pytest.fixture(autouse=True)
    def cleanup_logs(self):
        """Clean up logs directory before and after tests"""
        _cleanup_logs_directory()
        yield
        _cleanup_logs_directory()

    def test_audit_logger_exists(self):
        """AuditLogger should be importable"""
        from core.logging.audit import AuditLogger
        assert AuditLogger is not None

    def test_audit_logger_log_method_exists(self):
        """AuditLogger.log should be callable"""
        assert callable(AuditLogger.log)

    def test_audit_logger_helper_methods_exist(self):
        """AuditLogger should have helper methods"""
        assert callable(AuditLogger.log_login)
        assert callable(AuditLogger.log_logout)
        assert callable(AuditLogger.log_agent_create)
        assert callable(AuditLogger.log_agent_delete)
        assert callable(AuditLogger.log_mcp_connect)
        assert callable(AuditLogger.log_mcp_disconnect)

    def test_audit_logger_creates_separate_file(self):
        """AuditLogger should log to separate audit.log file"""
        AuditLogger.log(
            action='test.action',
            resource_type='Test',
            resource_id='test_123',
            request_id='req_test'
        )

        # audit.log should exist in logs directory
        assert os.path.exists('logs/audit.log')

    def test_audit_log_content_is_json(self):
        """Audit log entries should be valid JSON"""
        AuditLogger.log(
            action='test.action',
            resource_type='Test',
            resource_id='test_123',
            request_id='req_test'
        )

        # Read and parse log file
        with open('logs/audit.log', 'r', encoding='utf-8') as f:
            content = f.read()

        # Should be valid JSON
        data = json.loads(content.strip())
        assert data['action'] == 'test.action'
        assert data['resource_type'] == 'Test'
        assert data['resource_id'] == 'test_123'


class TestLoggingMiddleware:
    """Test LoggingMiddleware behavior"""

    def test_loggingmiddleware_excludes_paths(self):
        """LoggingMiddleware should exclude certain paths"""
        from gateway.middleware.logging import LoggingMiddleware

        middleware = LoggingMiddleware(None)
        assert '/health' in middleware.EXCLUDE_PATHS
        assert '/metrics' in middleware.EXCLUDE_PATHS

    def test_loggingmiddleware_excludes_docs_paths(self):
        """LoggingMiddleware should exclude docs and openapi paths"""
        from gateway.middleware.logging import LoggingMiddleware

        middleware = LoggingMiddleware(None)
        assert '/docs' in middleware.EXCLUDE_PATHS
        assert '/openapi.json' in middleware.EXCLUDE_PATHS


class TestLoggingConfig:
    """Test logging configuration in settings"""

    def test_settings_has_log_level(self):
        """Settings should have LOG_LEVEL"""
        from core.config import settings
        assert hasattr(settings, 'LOG_LEVEL')
        assert settings.LOG_LEVEL in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    def test_settings_has_log_dir(self):
        """Settings should have LOG_DIR"""
        from core.config import settings
        assert hasattr(settings, 'LOG_DIR')

    def test_settings_has_log_stdout(self):
        """Settings should have LOG_STDOUT"""
        from core.config import settings
        assert hasattr(settings, 'LOG_STDOUT')

    def test_settings_has_log_file(self):
        """Settings should have LOG_FILE"""
        from core.config import settings
        assert hasattr(settings, 'LOG_FILE')

    def test_settings_has_log_max_size(self):
        """Settings should have LOG_MAX_SIZE"""
        from core.config import settings
        assert hasattr(settings, 'LOG_MAX_SIZE')

    def test_settings_has_log_backup_count(self):
        """Settings should have LOG_BACKUP_COUNT"""
        from core.config import settings
        assert hasattr(settings, 'LOG_BACKUP_COUNT')