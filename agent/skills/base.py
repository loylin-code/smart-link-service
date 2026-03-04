"""
Skill base class and registry
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import importlib
import inspect
import pkgutil
from pathlib import Path

from agent.core.context import AgentContext
from core.exceptions import SkillError


class BaseSkill(ABC):
    """
    Base class for all skills
    Skills are reusable capabilities that agents can use
    """
    
    # Metadata
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    
    # Skill configuration schema
    config_schema: Optional[Dict[str, Any]] = None
    
    @abstractmethod
    async def execute(
        self,
        context: AgentContext,
        params: Dict[str, Any]
    ) -> Any:
        """
        Execute the skill
        
        Args:
            context: Agent execution context
            params: Skill parameters
            
        Returns:
            Execution result
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate parameters against config schema
        
        Args:
            params: Parameters to validate
            
        Returns:
            True if valid
            
        Raises:
            SkillError if invalid
        """
        # TODO: Implement schema validation
        return True
    
    def to_openai_tool(self) -> Dict[str, Any]:
        """
        Convert skill to OpenAI tool format
        
        Returns:
            Tool definition dict
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema()
            }
        }
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Get parameters JSON schema
        
        Returns:
            JSON schema dict
        """
        pass


class SkillRegistry:
    """
    Registry for managing skills
    Supports auto-discovery and dynamic loading
    """
    
    def __init__(self):
        # Skill storage: {skill_name: skill_instance}
        self._skills: Dict[str, BaseSkill] = {}
        
        # Auto-discover and register builtin skills
        self._auto_discover()
    
    def register(self, skill: BaseSkill):
        """
        Register a skill
        
        Args:
            skill: Skill instance to register
        """
        if not skill.name:
            raise ValueError("Skill must have a name")
        
        self._skills[skill.name] = skill
        print(f"✓ Registered skill: {skill.name}")
    
    def get(self, skill_name: str) -> Optional[BaseSkill]:
        """
        Get skill by name
        
        Args:
            skill_name: Skill name
            
        Returns:
            Skill instance or None
        """
        return self._skills.get(skill_name)
    
    def list_skills(self) -> List[str]:
        """List all registered skill names"""
        return list(self._skills.keys())
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all skills as OpenAI tools
        
        Returns:
            List of tool definitions
        """
        return [skill.to_openai_tool() for skill in self._skills.values()]
    
    def _auto_discover(self):
        """Auto-discover and register builtin skills"""
        # Get the builtin skills directory
        skills_dir = Path(__file__).parent.parent / "skills" / "builtin"
        
        if not skills_dir.exists():
            return
        
        # Import all Python modules in the directory
        for importer, module_name, is_pkg in pkgutil.iter_modules([str(skills_dir)]):
            if module_name.startswith("_"):
                continue
            
            try:
                # Import the module
                module = importlib.import_module(
                    f"agent.skills.builtin.{module_name}"
                )
                
                # Find all skill classes
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj) and
                        issubclass(obj, BaseSkill) and
                        obj != BaseSkill and
                        obj.name  # Has a name
                    ):
                        # Instantiate and register
                        skill_instance = obj()
                        self.register(skill_instance)
                        
            except Exception as e:
                print(f"Warning: Failed to load skill {module_name}: {e}")


# Global skill registry
skill_registry = SkillRegistry()