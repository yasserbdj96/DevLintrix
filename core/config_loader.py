# core/config_loader.py
import json
import os

def load_plugin_configs(plugin_name):
    """Load config.json and plugin.json for a specific plugin"""
    plugin_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "plugins", 
        plugin_name
    )
    
    config_data = {}
    plugin_info = {}
    
    # Load config.json (if exists)
    config_path = os.path.join(plugin_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"⚠️  Warning: Could not load config.json for plugin '{plugin_name}': {e}")
    
    # Load plugin.json (if exists)
    plugin_path = os.path.join(plugin_dir, "plugin.json")
    if os.path.exists(plugin_path):
        try:
            with open(plugin_path, "r", encoding="utf-8") as f:
                plugin_info = json.load(f)
        except Exception as e:
            print(f"⚠️  Warning: Could not load plugin.json for plugin '{plugin_name}': {e}")
    
    return config_data, plugin_info

# Global dictionaries to store loaded plugin configs
plugin_configs = {}
plugin_infos = {}

def set_plugin_config(plugin_name, config_data, plugin_info):
    """Store plugin configuration and info"""
    plugin_configs[plugin_name] = config_data
    plugin_infos[plugin_name] = plugin_info

def get_plugin_config(plugin_name):
    """Get config.json data for a plugin"""
    return plugin_configs.get(plugin_name, {})

def get_plugin_info(plugin_name):
    """Get plugin.json data for a plugin"""
    return plugin_infos.get(plugin_name, {})

def load_main_config():
    """Load only the main config.json from root directory"""
    project_root = os.path.join(os.path.dirname(__file__), "..")
    config_path = os.path.join(project_root, "config.json")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Main config.json not found at: {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in main config.json")

# Load main config
main_config = load_main_config()