"""
SkillFile service for file operations
"""
import io
import zipfile
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.skill_file import SkillFile


class SkillFileService:
    """Service for skill file operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_file(self, skill_id: str, path: str) -> Optional[SkillFile]:
        """Get file by skill_id and path"""
        query = select(SkillFile).where(
            SkillFile.skill_id == skill_id,
            SkillFile.path == path
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def save_file(
        self,
        skill_id: str,
        path: str,
        content: str,
        mime_type: str = "text/markdown",
        version_id: Optional[str] = None
    ) -> SkillFile:
        """Save or update a skill file"""
        file = await self.get_file(skill_id, path)
        
        if file:
            file.content = content
            file.mime_type = mime_type
            file.size_bytes = len(content.encode('utf-8'))
            file.updated_at = datetime.utcnow()
        else:
            file = SkillFile(
                skill_id=skill_id,
                version_id=version_id,
                path=path,
                content=content,
                mime_type=mime_type,
                size_bytes=len(content.encode('utf-8'))
            )
            self.db.add(file)
        
        await self.db.commit()
        await self.db.refresh(file)
        return file
    
    async def get_all_files(self, skill_id: str) -> List[SkillFile]:
        """Get all files for a skill"""
        query = select(SkillFile).where(
            SkillFile.skill_id == skill_id
        ).order_by(SkillFile.path)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def build_file_tree(self, skill_id: str) -> List[Dict[str, Any]]:
        """Build file tree structure"""
        files = await self.get_all_files(skill_id)
        
        tree: List[Dict[str, Any]] = []
        for file in files:
            parts = file.path.split('/')
            current = tree
            
            for part in parts[:-1]:
                dir_node = next((n for n in current if n.get('name') == part), None)
                if not dir_node:
                    dir_node = {'name': part, 'type': 'directory', 'children': []}
                    current.append(dir_node)
                current = dir_node['children']
            
            current.append({
                'name': parts[-1],
                'type': 'file',
                'path': file.path,
                'mime_type': file.mime_type,
                'size': file.size_bytes
            })
        
        return tree
    
    async def export_skill_zip(self, skill_id: str, skill_name: str) -> bytes:
        """Export skill files as ZIP"""
        files = await self.get_all_files(skill_id)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in files:
                zf.writestr(file.path, file.content)
        
        zip_buffer.seek(0)
        return zip_buffer.read()
