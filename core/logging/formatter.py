"""
Structured JSON log formatter
"""
import json
import logging
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """
    JSON structured log formatter.
    
    Output format:
    {
      "timestamp": "2026-04-14T10:30:00Z",
      "level": "INFO",
      "logger": "...",
      "message": "...",
      "request_id": "...",
      ...
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields from record
        extra_fields = [
            'request_id', 'tenant_id', 'user_id', 
            'path', 'method', 'status', 'duration_ms',
            'trace_id', 'span_id', 'extra',
            'action', 'resource_type', 'resource_id', 'changes',
            'ip_address', 'user_agent',
            'error_type', 'error_message', 'stack_trace',
        ]
        
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
        
        # Add exception info if present
        if record.exc_info:
            log_data['error_type'] = record.exc_info[0].__name__ if record.exc_info[0] else None
            log_data['error_message'] = str(record.exc_info[1]) if record.exc_info[1] else None
            log_data['stack_trace'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)