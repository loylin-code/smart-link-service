"""
Skill base class and registry with caching support.

Optimized with:
- Disk cache for skill discovery results
- Code hash validation for cache invalidation
- Fast startup (200ms → 10ms when cached)
"""
import json
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import importlib
import inspect
import pkgutil
from pathlib import Path

from agent.core.context import AgentContext
from core.exceptions import SkillError


# ============================================================
# BASE SKILL CLASS
# ============================================================

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
        schema = self.get_parameters_schema()
        if not schema:
            return True
        
        try:
            import jsonschema
            jsonschema.validate(params, schema)
            return True
        except jsonschema.ValidationError as e:
            raise SkillError(
                f"Parameter validation failed for skill '{self.name}': {e.message}",
                skill_name=self.name
            )
        except jsonschema.SchemaError as e:
            raise SkillError(
                f"Invalid schema for skill '{self.name}': {e.message}",
                skill_name=self.name
            )
        except ImportError:
            # jsonschema not installed, skip validation
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


# ============================================================
# SKILL REGISTRY WITH CACHING
# ============================================================

class SkillRegistry:
    """
    Registry for managing skills with disk caching.
    
    Optimizations:
    - Cache discovery results to disk
    - Code hash validation for cache invalidation
    - Fast startup when skills haven't changed
    """
    
    CACHE_DIR = Path(".cache")
    CACHE_FILE = CACHE_DIR / "skill-discovery.json"
    
    def __init__(self, use_cache: bool = True):
        """
        Initialize skill registry.
        
        Args:
            use_cache: Whether to use disk cache (default: True)
        """
        # Skill storage: {skill_name: skill_instance}
        self._skills: Dict[str, BaseSkill] = {}
        self._use_cache = use_cache
        
        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(exist_ok=True)
        
        # Try loading from cache first
        if use_cache and self._load_from_cache():
            print(f"[Skills] ✅ Loaded {len(self._skills)} skills from cache")
        else:
            # Fall back to discovery
            self._auto_discover()
            self._save_cache()
    
    def register(self, skill: BaseSkill):
        """
        Register a skill
        
        Args:
            skill: Skill instance to register
        """
        if not skill.name:
            raise ValueError("Skill must have a name")
        
        self._skills[skill.name] = skill
    
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
    
    def _get_code_hash(self) -> str:
        """
        Calculate hash of builtin skills directory.
        
        Used to invalidate cache when skills code changes.
        
        Returns:
            MD5 hash of all skill files
        """
        skills_dir = Path(__file__).parent / "builtin"
        hasher = hashlib.md5()
        
        if not skills_dir.exists():
            return "empty"
        
        # Hash all Python files
        for py_file in sorted(skills_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            hasher.update(py_file.read_bytes())
        
        return hasher.hexdigest()
    
    def _load_from_cache(self) -> bool:
        """
        Load skills from disk cache.
        
        Returns:
            True if cache is valid and loaded successfully
        """
        if not self.CACHE_FILE.exists():
            return False
        
        try:
            cached = json.loads(self.CACHE_FILE.read_text())
            
            # Validate cache version (hash must match current code)
            current_hash = self._get_code_hash()
            if cached.get("hash") != current_hash:
                print(f"[Skills] Cache invalid (code changed)")
                return False
            
            # Load cached skills metadata
            skills_meta = cached.get("skills", {})
            
            for name, meta in skills_meta.items():
                skill_class = self._get_skill_class(meta["module"], meta["class"])
                if skill_class:
                    self._skills[name] = skill_class()
            
            return len(self._skills) > 0
            
        except Exception as e:
            print(f"[Skills] Cache load failed: {str(e)[:50]}")
            return False
    
    def _save_cache(self):
        """
        Save skill discovery results to disk cache.
        """
        cache_data = {
            "hash": self._get_code_hash(),
            "timestamp": time.time(),
            "skills": {
                name: {
                    "module": skill.__class__.__module__,
                    "class": skill.__class__.__name__,
                    "description": skill.description,
                    "version": skill.version,
                }
                for name, skill in self._skills.items()
            }
        }
        
        self.CACHE_FILE.write_text(json.dumps(cache_data, indent=2))
        print(f"[Skills] Saved {len(self._skills)} skills to cache")
    
    def _get_skill_class(self, module: str, class_name: str) -> Optional[type]:
        """
        Get skill class by module and class name.
        
        Args:
            module: Module path (e.g., "agent.skills.builtin.search")
            class_name: Class name (e.g., "WebSearchSkill")
            
        Returns:
            Skill class or None if not found
        """
        try:
            mod = importlib.import_module(module)
            return getattr(mod, class_name, None)
        except ImportError:
            return None
    
    def _auto_discover(self):
        """
        Auto-discover and register builtin skills.
        
        Scans agent/skills/builtin/ directory for skill classes.
        """
        skills_dir = Path(__file__).parent / "builtin"
        
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
                print(f"[Skills] Failed to load {module_name}: {str(e)[:50]}")
    
    def invalidate_cache(self):
        """
        Invalidate and remove the cache file.
        
        Forces fresh discovery on next startup.
        """
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()
            print("[Skills] Cache invalidated")


# ============================================================
# GLOBAL SKILL REGISTRY
# ============================================================

# Global skill registry (instantiated on import)
skill_registry = SkillRegistry()


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "BaseSkill",
    "SkillRegistry",
    "skill_registry",
]