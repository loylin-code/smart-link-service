"""
Plugin Loader - Dynamic plugin loading mechanism
"""
import importlib
from typing import Dict, Any, Optional

from agent.skills.base import BaseSkill
from core.exceptions import PluginLoadError


class PluginLoader:
    """Dynamic plugin loader for marketplace plugins
    
    Provides loading/unloading of plugins from installed packages.
    Plugins are loaded via their entry point specification.
    """
    
    def __init__(self):
        self._loaded_plugins: Dict[str, BaseSkill] = {}
    
    async def load_plugin(
        self,
        plugin: Any,
        settings: Dict[str, Any]
    ) -> BaseSkill:
        """Load plugin from package
        
        Args:
            plugin: Plugin model with package_name and entry_point
            settings: Plugin-specific settings to pass to skill
            
        Returns:
            Loaded BaseSkill instance
            
        Raises:
            PluginLoadError if loading fails
        """
        try:
            # Import module
            module = importlib.import_module(plugin.package_name)
            
            # Get class from entry point
            class_name = plugin.entry_point.split(":")[-1]
            skill_class = getattr(module, class_name)
            
            # Instantiate with settings
            skill = skill_class(**settings)
            
            # Cache loaded plugin
            self._loaded_plugins[plugin.id] = skill
            
            return skill
            
        except ImportError as e:
            raise PluginLoadError(
                f"Failed to import plugin package '{plugin.package_name}': {str(e)}",
                plugin_name=plugin.name,
                suggestions=[
                    f"Install package: pip install {plugin.package_name}",
                    "Verify package_name is correct"
                ]
            )
        except AttributeError as e:
            raise PluginLoadError(
                f"Entry point '{plugin.entry_point}' not found in package",
                plugin_name=plugin.name,
                suggestions=[
                    "Verify entry_point format: module:ClassName",
                    "Check class exists in module"
                ]
            )
        except Exception as e:
            raise PluginLoadError(
                f"Failed to instantiate plugin: {str(e)}",
                plugin_name=plugin.name,
                suggestions=[
                    "Check plugin constructor signature",
                    "Verify settings match plugin requirements"
                ]
            )
    
    async def unload_plugin(self, plugin_id: str) -> None:
        """Unload plugin from cache
        
        Args:
            plugin_id: Plugin ID to unload
        """
        if plugin_id in self._loaded_plugins:
            del self._loaded_plugins[plugin_id]
    
    def get_loaded(self, plugin_id: str) -> Optional[BaseSkill]:
        """Get loaded skill by plugin ID
        
        Args:
            plugin_id: Plugin ID
            
        Returns:
            BaseSkill instance or None if not loaded
        """
        return self._loaded_plugins.get(plugin_id)
    
    def is_loaded(self, plugin_id: str) -> bool:
        """Check if plugin is loaded
        
        Args:
            plugin_id: Plugin ID
            
        Returns:
            True if loaded
        """
        return plugin_id in self._loaded_plugins
    
    def list_loaded(self) -> Dict[str, BaseSkill]:
        """List all loaded plugins
        
        Returns:
            Dict of plugin_id -> BaseSkill
        """
        return self._loaded_plugins.copy()