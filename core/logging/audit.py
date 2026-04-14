"""
Audit logging for sensitive operations
"""
import logging
from typing import Optional, Dict, Any

from core.logging import get_logger

# Lazy initialization of audit logger
_audit_logger: Optional[logging.Logger] = None


def _get_audit_logger() -> logging.Logger:
    """Get or create audit logger (lazy initialization)"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = get_logger('audit', file_name='audit.log', level='INFO')
    return _audit_logger


class AuditLogger:
    """
    Audit trail logger for sensitive operations.
    
    Audit events:
    - user.login/user.logout
    - agent.create/agent.update/agent.delete
    - api_key.create/api_key.delete
    - mcp_server.connect/mcp_server.disconnect
    - permission.grant/permission.revoke
    """
    
    @staticmethod
    def log(
        action: str,
        resource_type: str,
        resource_id: str,
        request_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Log audit event.
        
        Args:
            action: Action type (e.g., 'agent.create')
            resource_type: Resource type (e.g., 'Agent')
            resource_id: Resource identifier
            request_id: Request ID for correlation
            tenant_id: Tenant identifier
            user_id: User identifier
            changes: Dict of changes made
            ip_address: Client IP address
            user_agent: Client user agent
        """
        
        _get_audit_logger().info(
            f"{action} - {resource_type}:{resource_id}",
            extra={
                'request_id': request_id,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'action': action,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'changes': changes or {},
                'ip_address': ip_address,
                'user_agent': user_agent,
            }
        )
    
    @staticmethod
    def log_login(request_id: str, user_id: str, tenant_id: Optional[str] = None, 
                  ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log user login"""
        AuditLogger.log(
            action='user.login',
            resource_type='User',
            resource_id=user_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @staticmethod
    def log_logout(request_id: str, user_id: str, tenant_id: Optional[str] = None):
        """Log user logout"""
        AuditLogger.log(
            action='user.logout',
            resource_type='User',
            resource_id=user_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    
    @staticmethod
    def log_agent_create(request_id: str, agent_id: str, name: str, 
                         tenant_id: Optional[str] = None, user_id: Optional[str] = None,
                         changes: Optional[Dict[str, Any]] = None):
        """Log agent creation"""
        AuditLogger.log(
            action='agent.create',
            resource_type='Agent',
            resource_id=agent_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            changes={'name': name, **(changes or {})},
        )
    
    @staticmethod
    def log_agent_delete(request_id: str, agent_id: str,
                          tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log agent deletion"""
        AuditLogger.log(
            action='agent.delete',
            resource_type='Agent',
            resource_id=agent_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    
    @staticmethod
    def log_mcp_connect(request_id: str, server_name: str,
                         tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log MCP server connection"""
        AuditLogger.log(
            action='mcp_server.connect',
            resource_type='MCPServer',
            resource_id=server_name,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    
    @staticmethod
    def log_mcp_disconnect(request_id: str, server_name: str,
                            tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log MCP server disconnection"""
        AuditLogger.log(
            action='mcp_server.disconnect',
            resource_type='MCPServer',
            resource_id=server_name,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )