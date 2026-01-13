# core/config_loader.py
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

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
    
    # Load config.json
    config_path = os.path.join(plugin_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                resolved_content = resolve_env_vars(content)
                config_data = json.loads(resolved_content)
        except json.JSONDecodeError as e:
            print(f"      ✗ Invalid config.json: {e}")
        except Exception as e:
            print(f"      ✗ Config load error: {e}")
    
    # Load plugin.json
    plugin_path = os.path.join(plugin_dir, "plugin.json")
    if os.path.exists(plugin_path):
        try:
            with open(plugin_path, "r", encoding="utf-8") as f:
                plugin_info = json.load(f)
        except Exception as e:
            print(f"      ✗ Plugin info load error: {e}")
    
    return config_data, plugin_info

def resolve_env_vars(content):
    """Replace ${VAR_NAME} patterns with environment variables"""
    def replace_env_var(match):
        var_name = match.group(1)
        env_value = os.environ.get(var_name, '')
        if not env_value and os.environ.get('DEBUG') == 'true':
            print(f"      ⚠ Missing env var: {var_name}")
        return env_value if env_value else match.group(0)
    
    pattern = r'\$\{([A-Za-z0-9_]+)\}'
    return re.sub(pattern, replace_env_var, content)

# Global dictionaries
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
    """Load main config.json from root directory"""
    project_root = os.path.join(os.path.dirname(__file__), "..")
    config_path = os.path.join(project_root, "config.json")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(resolve_env_vars(content))
    except FileNotFoundError:
        raise FileNotFoundError(f"config.json not found at: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config.json: {e}")

main_config = load_main_config()