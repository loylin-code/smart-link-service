"""
Conversation REST API
对话管理 HTTP 端点
Aligned with frontend service expectations
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime
import uuid

from core.time_utils import now_utc8
from db.session import get_db
from schemas import ApiResponse, PaginatedData, ConversationCreate, ConversationUpdate, MessageCreate
from models import Conversation, Message, Application, Tenant, TenantStatus


router = APIRouter(tags=["Conversations"])


# ============================================================
# Helper Functions
# ============================================================

def conversation_to_response(conv: Conversation, include_messages: bool = False) -> dict:
    """Convert Conversation model to frontend-expected response format"""
    # 使用预加载的消息数量，避免懒加载触发 async 错误
    message_count = getattr(conv, '_message_count', 0)
    
    response = {
        "id": conv.id,
        "title": conv.title or "新对话",
        "app_id": conv.app_id,
        "user_id": conv.user_id,
        "status": "archived" if conv.is_archived else "active",
        "message_count": message_count,
        "last_message_at": int(conv.updated_at.timestamp() * 1000) if conv.updated_at else None,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "messages": []
    }
    
    if include_messages and conv.messages:
        response["messages"] = [message_to_response(m) for m in conv.messages]
    
    return response


def message_to_response(msg: Message) -> dict:
    """Convert Message model to frontend-expected response format"""
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content.get("text", "") if isinstance(msg.content, dict) else msg.content,
        "prompt_tokens": msg.prompt_tokens,
        "completion_tokens": msg.completion_tokens,
        "total_tokens": msg.total_tokens,
        "components": [],
        "created_at": msg.created_at
    }


# ============================================================
# Conversations API
# ============================================================

@router.get("/", response_model=ApiResponse[PaginatedData[dict]])
async def list_conversations(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    app_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取对话列表"""
    # Get tenant_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    
    query = select(Conversation)
    count_query = select(func.count(Conversation.id))
    
    # For master key, get first active tenant
    if tenant_context and tenant_context.is_master:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            query = query.where(Conversation.tenant_id == tenant.id)
            count_query = count_query.where(Conversation.tenant_id == tenant.id)
    elif tenant_context and tenant_context.tenant_id:
        query = query.where(Conversation.tenant_id == tenant_context.tenant_id)
        count_query = count_query.where(Conversation.tenant_id == tenant_context.tenant_id)
    
    if app_id:
        query = query.where(Conversation.app_id == app_id)
        count_query = count_query.where(Conversation.app_id == app_id)
    
    if user_id:
        query = query.where(Conversation.user_id == user_id)
        count_query = count_query.where(Conversation.user_id == user_id)
    
    if status == "archived":
        query = query.where(Conversation.is_archived == True)
        count_query = count_query.where(Conversation.is_archived == True)
    elif status == "active":
        query = query.where(Conversation.is_archived == False)
        count_query = count_query.where(Conversation.is_archived == False)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    # Batch query message counts for all conversations
    if conversations:
        conv_ids = [c.id for c in conversations]
        msg_count_query = (
            select(Message.conversation_id, func.count(Message.id))
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
        )
        msg_count_result = await db.execute(msg_count_query)
        msg_counts = {row[0]: row[1] for row in msg_count_result.all()}
        
        # Assign message counts to conversations
        for conv in conversations:
            conv._message_count = msg_counts.get(conv.id, 0)
    
    return ApiResponse(
        data=PaginatedData(
            list=[conversation_to_response(c) for c in conversations],
            total=total,
            page=page,
            page_size=page_size
        )
    )


@router.post("/", response_model=ApiResponse[dict])
async def create_conversation(
    data: ConversationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """创建新对话"""
    # Get tenant_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    
    # For master key, get first active tenant
    if tenant_context and tenant_context.is_master:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=400, detail="No active tenant found")
        tenant_id = tenant.id
    elif tenant_context and tenant_context.tenant_id:
        tenant_id = tenant_context.tenant_id
    else:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    conversation = Conversation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title=data.title or "新对话",
        app_id=data.app_id,
        user_id=data.user_id,
        is_archived=False
    )
    
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    return ApiResponse(data=conversation_to_response(conversation))


@router.get("/{conversation_id}", response_model=ApiResponse[dict])
async def get_conversation(
    conversation_id: str,
    include_messages: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """获取对话详情"""
    query = select(Conversation).where(Conversation.id == conversation_id)
    
    if include_messages:
        from sqlalchemy.orm import selectinload
        query = query.options(selectinload(Conversation.messages))
    
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return ApiResponse(data=conversation_to_response(conversation, include_messages))


@router.put("/{conversation_id}", response_model=ApiResponse[dict])
async def update_conversation(
    conversation_id: str,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新对话（重命名/归档）"""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if data.title:
        conversation.title = data.title
    
    if data.status == "archived":
        conversation.is_archived = True
    elif data.status == "active":
        conversation.is_archived = False
    
    await db.commit()
    await db.refresh(conversation)
    
    return ApiResponse(data=conversation_to_response(conversation))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除对话"""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    await db.delete(conversation)
    await db.commit()
    
    return ApiResponse(data={"deleted": True})


@router.get("/{conversation_id}/messages", response_model=ApiResponse[list])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取对话消息历史"""
    # Check if conversation exists
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    query = select(Message).where(Message.conversation_id == conversation_id)
    
    if before_id:
        # Get messages before a specific ID (for pagination)
        before_msg = await db.execute(select(Message.created_at).where(Message.id == before_id))
        before_time = before_msg.scalar_one_or_none()
        if before_time:
            query = query.where(Message.created_at < before_time)
    
    query = query.order_by(Message.created_at.asc()).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return ApiResponse(data=[message_to_response(m) for m in messages])


@router.post("/{conversation_id}/messages", response_model=ApiResponse[dict])
async def add_message(
    conversation_id: str,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """添加消息到对话"""
    # Check if conversation exists
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get sequence number
    seq_result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    sequence_number = seq_result.scalar() or 0
    
    message = Message(
        id=str(uuid.uuid4()),
        tenant_id=conversation.tenant_id,
        conversation_id=conversation_id,
        user_id=conversation.user_id,
        role=data.role,
        content=data.content,
        sequence_number=sequence_number
    )
    
    db.add(message)
    
    # Update conversation's last_activity
    conversation.last_activity = datetime.utcnow()
    
    await db.commit()
    await db.refresh(message)
    
    return ApiResponse(data=message_to_response(message))


@router.post("/{conversation_id}/archive", response_model=ApiResponse[dict])
async def archive_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """归档对话"""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.is_archived = True
    await db.commit()
    await db.refresh(conversation)
    
    return ApiResponse(data=conversation_to_response(conversation))


@router.post("/{conversation_id}/restore", response_model=ApiResponse[dict])
async def restore_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """恢复归档对话"""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.is_archived = False
    await db.commit()
    await db.refresh(conversation)
    
    return ApiResponse(data=conversation_to_response(conversation))