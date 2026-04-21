"""
Channel adapters for multi-channel message handling
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import Request, Response, WebSocket

from core.config import settings
from core.time_utils import now_utc8


class ChannelType(str, Enum):
    """Channel types"""
    WEB = "web"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"
    WECOM = "wecom"
    API = "api"
    MOBILE = "mobile"


class MessageType(str, Enum):
    """Message types"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    CARD = "card"
    EVENT = "event"
    AUDIO = "audio"
    VIDEO = "video"


class Attachment(BaseModel):
    """Attachment information"""
    type: str
    url: Optional[str] = None
    content: Optional[bytes] = None
    name: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None


class StandardMessage(BaseModel):
    """
    Standardized message format
    All channels convert to this unified format
    """
    # Channel info
    channel_id: str
    channel_type: ChannelType
    
    # User info
    user_id: str
    tenant_id: str
    
    # Conversation info
    conversation_id: str
    session_key: Optional[str] = None
    
    # Message content
    message_type: MessageType = MessageType.TEXT
    content: str
    attachments: List[Attachment] = Field(default_factory=list)
    
    # Metadata
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Raw data for debugging
    raw_data: Optional[Dict[str, Any]] = None


class ChannelAdapter(ABC):
    """
    Base class for channel adapters
    Implements the Adapter pattern for multi-channel support
    """
    
    channel_type: ChannelType
    
    @abstractmethod
    async def parse_message(self, raw_data: Dict[str, Any]) -> StandardMessage:
        """Parse raw message to standard format"""
        pass
    
    @abstractmethod
    async def send_message(self, message: StandardMessage) -> bool:
        """Send message to channel"""
        pass
    
    @abstractmethod
    async def validate_signature(self, request: Request) -> bool:
        """Validate request signature"""
        pass
    
    async def handle_webhook(self, request: Request) -> Response:
        """Handle webhook callback"""
        pass


class WebChannelAdapter(ChannelAdapter):
    """
    Web frontend WebSocket channel adapter
    """
    
    channel_type = ChannelType.WEB
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_key: str):
        """Establish WebSocket connection"""
        await websocket.accept()
        self.connections[session_key] = websocket
    
    async def disconnect(self, session_key: str):
        """Disconnect WebSocket"""
        if session_key in self.connections:
            del self.connections[session_key]
    
    async def parse_message(self, raw_data: Dict[str, Any]) -> StandardMessage:
        """Parse WebSocket message"""
        return StandardMessage(
            channel_id=f"web:{self.tenant_id}",
            channel_type=ChannelType.WEB,
            user_id=raw_data.get("user_id", ""),
            tenant_id=self.tenant_id,
            conversation_id=raw_data.get("conversation_id", ""),
            session_key=raw_data.get("session_key"),
            message_type=raw_data.get("type", MessageType.TEXT),
            content=raw_data.get("content", ""),
            timestamp=now_utc8(),
            metadata={
                "client_info": raw_data.get("client_info", {}),
                "app_id": raw_data.get("app_id")
            },
            raw_data=raw_data
        )
    
    async def send_message(self, message: StandardMessage) -> bool:
        """Send message via WebSocket"""
        session_key = message.session_key
        if session_key not in self.connections:
            return False
        
        websocket = self.connections[session_key]
        try:
            await websocket.send_json({
                "type": "response",
                "data": {
                    "content": message.content,
                    "attachments": [a.model_dump() for a in message.attachments]
                },
                "timestamp": message.timestamp.isoformat()
            })
            return True
        except Exception:
            await self.disconnect(session_key)
            return False
    
    async def send_stream(self, session_key: str, chunk: str, done: bool = False):
        """Send streaming response"""
        if session_key not in self.connections:
            return
        
        websocket = self.connections[session_key]
        await websocket.send_json({
            "type": "stream",
            "data": {
                "delta": chunk,
                "done": done
            }
        })
    
    async def validate_signature(self, request: Request) -> bool:
        """WebSocket uses JWT, no signature validation"""
        return True


class DingTalkChannelAdapter(ChannelAdapter):
    """
    DingTalk robot channel adapter
    """
    
    channel_type = ChannelType.DINGTALK
    
    def __init__(self, app_key: str, app_secret: str, tenant_id: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.tenant_id = tenant_id
    
    async def parse_message(self, raw_data: Dict[str, Any]) -> StandardMessage:
        """Parse DingTalk message"""
        msgtype = raw_data.get("msgtype", "text")
        content = ""
        attachments = []
        
        if msgtype == "text":
            content = raw_data.get("text", {}).get("content", "")
        elif msgtype == "picture":
            attachments.append(Attachment(
                type="image",
                url=raw_data.get("content", {}).get("downloadCode", "")
            ))
        
        return StandardMessage(
            channel_id=f"dingtalk:{self.app_key}",
            channel_type=ChannelType.DINGTALK,
            user_id=raw_data.get("senderId", ""),
            tenant_id=self.tenant_id,
            conversation_id=raw_data.get("conversationId", ""),
            message_type=msgtype,
            content=content,
            attachments=attachments,
            timestamp=datetime.fromtimestamp(raw_data.get("createAt", 0) / 1000),
            metadata={
                "msg_id": raw_data.get("msgId"),
                "sender_nick": raw_data.get("senderNick"),
                "is_in_at_list": raw_data.get("isInAtList", False)
            },
            raw_data=raw_data
        )
    
    async def send_message(self, message: StandardMessage) -> bool:
        """Send DingTalk message"""
        import httpx
        
        token = await self._get_access_token()
        url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
        
        payload = {
            "msgtype": "text",
            "text": {"content": message.content},
            "at": {"atUserIds": [message.user_id]}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            return response.status_code == 200
    
    async def validate_signature(self, request: Request) -> bool:
        """Validate DingTalk signature"""
        import hashlib
        import hmac
        import time
        
        timestamp = request.headers.get("timestamp", "")
        sign = request.headers.get("sign", "")
        
        if not timestamp or not sign:
            return False
        
        # Prevent replay attacks
        if abs(time.time() - int(timestamp) / 1000) > 300:
            return False
        
        # Calculate signature
        string_to_sign = f"{timestamp}\n{self.app_secret}"
        hmac_code = hmac.new(
            self.app_secret.encode(),
            string_to_sign.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        import base64
        expected_sign = base64.b64encode(hmac_code).decode()
        return sign == expected_sign
    
    async def _get_access_token(self) -> str:
        """Get DingTalk access token"""
        # TODO: Implement token retrieval
        return ""


class FeishuChannelAdapter(ChannelAdapter):
    """
    Feishu (Lark) robot channel adapter
    """
    
    channel_type = ChannelType.FEISHU
    
    def __init__(self, app_id: str, app_secret: str, tenant_id: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_id = tenant_id
    
    async def parse_message(self, raw_data: Dict[str, Any]) -> StandardMessage:
        """Parse Feishu message"""
        event = raw_data.get("event", {})
        message = event.get("message", {})
        
        return StandardMessage(
            channel_id=f"feishu:{self.app_id}",
            channel_type=ChannelType.FEISHU,
            user_id=event.get("sender", {}).get("sender_id", {}).get("user_id", ""),
            tenant_id=self.tenant_id,
            conversation_id=message.get("chat_id", ""),
            message_type=message.get("message_type", MessageType.TEXT),
            content=self._extract_content(message),
            timestamp=datetime.fromtimestamp(message.get("create_time", 0) / 1000),
            metadata={
                "message_id": message.get("message_id")
            },
            raw_data=raw_data
        )
    
    def _extract_content(self, message: Dict) -> str:
        """Extract text content from message"""
        import json
        content = message.get("content", "{}")
        try:
            data = json.loads(content)
            return data.get("text", "")
        except:
            return ""
    
    async def send_message(self, message: StandardMessage) -> bool:
        """Send Feishu message"""
        # TODO: Implement
        return True
    
    async def validate_signature(self, request: Request) -> bool:
        """Validate Feishu signature"""
        # TODO: Implement
        return True


class APIChannelAdapter(ChannelAdapter):
    """
    Open API channel adapter
    """
    
    channel_type = ChannelType.API
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
    
    async def parse_message(self, raw_data: Dict[str, Any]) -> StandardMessage:
        """Parse API request"""
        return StandardMessage(
            channel_id=f"api:{self.tenant_id}",
            channel_type=ChannelType.API,
            user_id=raw_data.get("user_id", "api_user"),
            tenant_id=self.tenant_id,
            conversation_id=raw_data.get("conversation_id", ""),
            message_type=raw_data.get("message_type", MessageType.TEXT),
            content=raw_data.get("content", ""),
            timestamp=now_utc8(),
            metadata={
                "request_id": raw_data.get("request_id"),
                "api_version": raw_data.get("api_version", "v1")
            },
            raw_data=raw_data
        )
    
    async def send_message(self, message: StandardMessage) -> bool:
        """API uses response, not push"""
        return True
    
    async def validate_signature(self, request: Request) -> bool:
        """API uses API key authentication"""
        return True


class ChannelRegistry:
    """Registry for channel adapters"""
    
    def __init__(self):
        self._adapters: Dict[str, ChannelAdapter] = {}
    
    def register(self, adapter: ChannelAdapter):
        """Register a channel adapter"""
        self._adapters[adapter.channel_type.value] = adapter
    
    def get(self, channel_type: str) -> Optional[ChannelAdapter]:
        """Get adapter by channel type"""
        return self._adapters.get(channel_type)
    
    def list_channels(self) -> List[str]:
        """List registered channels"""
        return list(self._adapters.keys())


# Global channel registry
channel_registry = ChannelRegistry()