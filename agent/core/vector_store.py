"""
向量存储实现
基于PgVector的语义搜索
"""
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Float, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from db.session import Base


class MemoryVector(Base):
    """记忆向量表"""
    __tablename__ = "memory_vectors"
    
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    conversation_id = Column(String, nullable=True, index=True)
    
    content = Column(Text, nullable=False)
    content_type = Column(String(50), default="conversation")  # conversation, summary, fact
    extra_metadata = Column("metadata", JSONB, default=dict)
    
    # 向量列 (使用pgvector)
    # embedding = Column(Vector(1536))  # OpenAI embedding维度
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_memory_vectors_tenant_user', 'tenant_id', 'user_id'),
    )


class VectorStore:
    """
    向量存储
    
    功能:
    - 向量存储
    - 语义搜索
    - 相似度计算
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        embedding_dim: int = 1536
    ):
        self.db = db_session
        self.embedding_dim = embedding_dim
    
    async def store(
        self,
        tenant_id: str,
        content: str,
        user_id: str = None,
        conversation_id: str = None,
        content_type: str = "conversation",
        metadata: Dict = None,
        embedding: List[float] = None
    ) -> str:
        """
        存储向量
        
        Args:
            tenant_id: 租户ID
            content: 文本内容
            user_id: 用户ID
            conversation_id: 对话ID
            content_type: 内容类型
            metadata: 元数据
            embedding: 向量嵌入 (可选)
            
        Returns:
            记录ID
        """
        import uuid
        record_id = str(uuid.uuid4())
        
        # 如果没有提供embedding，生成一个
        if embedding is None:
            embedding = await self._generate_embedding(content)
        
        # 存储到数据库
        memory = MemoryVector(
            id=record_id,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            content_type=content_type,
            extra_metadata=metadata or {}
        )
        
        self.db.add(memory)
        await self.db.commit()
        
        # 如果有向量，存储到pgvector
        if embedding:
            await self._store_embedding(record_id, embedding)
        
        return record_id
    
    async def search(
        self,
        query: str,
        tenant_id: str,
        user_id: str = None,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            tenant_id: 租户ID
            user_id: 用户ID (可选)
            top_k: 返回结果数量
            threshold: 相似度阈值
            
        Returns:
            搜索结果列表
        """
        # 生成查询向量
        query_embedding = await self._generate_embedding(query)
        
        # 构建查询
        sql = """
            SELECT id, content, metadata, created_at,
                   1 - (embedding <=> :query_embedding) as similarity
            FROM memory_vectors
            WHERE tenant_id = :tenant_id
        """
        params = {
            "tenant_id": tenant_id,
            "query_embedding": str(query_embedding)
        }
        
        if user_id:
            sql += " AND user_id = :user_id"
            params["user_id"] = user_id
        
        sql += f"""
            ORDER BY similarity DESC
            LIMIT {top_k}
        """
        
        try:
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": row[2],
                    "created_at": row[3],
                    "similarity": float(row[4]) if row[4] else 0.0
                }
                for row in rows
                if row[4] and float(row[4]) >= threshold
            ]
        except Exception as e:
            # 如果向量搜索失败，回退到文本搜索
            return await self._text_search(query, tenant_id, user_id, top_k)
    
    async def _text_search(
        self,
        query: str,
        tenant_id: str,
        user_id: str = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """文本搜索回退"""
        stmt = select(MemoryVector).where(
            MemoryVector.tenant_id == tenant_id
        )
        
        if user_id:
            stmt = stmt.where(MemoryVector.user_id == user_id)
        
        stmt = stmt.where(
            MemoryVector.content.ilike(f"%{query}%")
        ).limit(top_k)
        
        result = await self.db.execute(stmt)
        memories = result.scalars().all()
        
        return [
            {
                "id": m.id,
                "content": m.content,
                "metadata": m.extra_metadata,
                "created_at": m.created_at,
                "similarity": 0.5  # 默认相似度
            }
            for m in memories
        ]
    
    async def delete(self, record_id: str):
        """删除记录"""
        stmt = select(MemoryVector).where(MemoryVector.id == record_id)
        result = await self.db.execute(stmt)
        memory = result.scalar_one_or_none()
        
        if memory:
            await self.db.delete(memory)
            await self.db.commit()
    
    async def delete_by_conversation(self, conversation_id: str):
        """删除对话相关的所有记忆"""
        stmt = select(MemoryVector).where(
            MemoryVector.conversation_id == conversation_id
        )
        result = await self.db.execute(stmt)
        memories = result.scalars().all()
        
        for memory in memories:
            await self.db.delete(memory)
        
        await self.db.commit()
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        生成文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量
        """
        # TODO: 实际调用embedding模型
        # 这里返回一个占位向量
        return [0.0] * self.embedding_dim
    
    async def _store_embedding(self, record_id: str, embedding: List[float]):
        """存储向量到pgvector"""
        # TODO: 实际存储向量
        pass


def create_vector_store(db_session: AsyncSession) -> VectorStore:
    """创建向量存储实例"""
    return VectorStore(db_session)