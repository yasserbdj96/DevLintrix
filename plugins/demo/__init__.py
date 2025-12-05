# plugins/demo/__init__.py
import json
import os
from typing import Any, Optional

def create_config_class(config_file_name: str, class_name: str = None):
    """
    Factory function to create configuration classes that load specific JSON files.
    
    Args:
        config_file_name: Name of the JSON configuration file (e.g., "config.json")
        class_name: Optional custom name for the generated class
    
    Returns:
        A class that automatically loads the specified JSON file
    """
    if class_name is None:
        # Generate a class name from the filename
        base_name = os.path.splitext(config_file_name)[0]
        class_name = f"{base_name.capitalize()}Config"
    
    class ConfigClass:
        def __init__(self, config_path: Optional[str] = None):
            """
            Initialize the configuration by loading the JSON file.
            
            Args:
                config_path: Optional custom path to the config file.
                            If not provided, looks in the same directory as this module.
            """
            if config_path is None:
                # Get path of this package
                BASE_DIR = os.path.dirname(os.path.abspath(__file__))
                config_path = os.path.join(BASE_DIR, config_file_name)
            
            # Load JSON config
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config_data = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"{config_file_name} not found in: {config_path}")
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON format in: {config_path}")
            
            # Set attributes dynamically
            for key, value in self.config_data.items():
                setattr(self, key, value)
        
        def get(self, key: str, default: Any = None) -> Any:
            """Safely get a configuration value with a default fallback."""
            return self.config_data.get(key, default)
        
        def __str__(self) -> str:
            """String representation of the configuration."""
            return f"{class_name}({self.config_data})"
        
        def __repr__(self) -> str:
            """Representation of the configuration instance."""
            return f"{class_name} loaded from {config_file_name}"
    
    # Set the class name
    ConfigClass.__name__ = class_name
    ConfigClass.__qualname__ = class_name
    
    return ConfigClass

# Create specific configuration classes
AppConfig = create_config_class("config.json", "AppConfig")
plugininfo = create_config_class("plugin.json", "plugininfo")

# Instantiate them
config = AppConfig()
plugin_info = plugininfo()