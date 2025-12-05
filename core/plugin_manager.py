# core/plugin_manager.py
import importlib
import os
from core.config_loader import load_plugin_configs, set_plugin_config

PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), "../plugins")

def load_plugins(app, enabled_plugins):
    """
    Load only enabled plugins and register their configurations
    
    Args:
        app: Flask application instance
        enabled_plugins: List of plugin names to load (from config.json)
    """
    if not enabled_plugins:
        print("ℹ️  No plugins enabled in config.json")
        return
    
    print(f"🔌 Loading {len(enabled_plugins)} enabled plugin(s)...")
    
    for plugin_name in enabled_plugins:
        plugin_dir = os.path.join(PLUGIN_FOLDER, plugin_name)
        
        # Check if plugin directory exists
        if not os.path.exists(plugin_dir):
            print(f"❌ Plugin '{plugin_name}' directory not found in plugins folder")
            continue
        
        print(f"  → Processing plugin: {plugin_name}")
        
        # Load plugin configuration and info
        config_data, plugin_info = load_plugin_configs(plugin_name)
        
        # Store in config_loader
        set_plugin_config(plugin_name, config_data, plugin_info)
        
        # Load and register routes
        try:
            module_path = f"plugins.{plugin_name}.routes"
            module = importlib.import_module(module_path)
            
            if hasattr(module, 'register'):
                module.register(app)
                print(f"    ✅ Registered routes for '{plugin_name}'")
            else:
                print(f"    ⚠️  Plugin '{plugin_name}' has no register() function in routes.py")
                
        except ImportError as e:
            print(f"    ❌ Could not import routes for '{plugin_name}': {e}")
        except Exception as e:
            print(f"    ❌ Error loading plugin '{plugin_name}': {e}")
    
    print("✅ Plugin loading complete")