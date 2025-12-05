# core/plugin_manager.py
import importlib
import os
import sys
from core.config_loader import load_plugin_configs, set_plugin_config
from core.database import db, ModelMerger

PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), "../plugins")

class PluginManager:
    """Manages plugin lifecycle and database models with merging support"""
    
    def __init__(self):
        self.loaded_plugins = {}
        self.plugin_models = {}
        self.model_merger = ModelMerger()
    
    def load_plugin_models(self, plugin_name):
        """Load database models from a plugin and register them for merging"""
        try:
            model_module_path = f"plugins.{plugin_name}.models"
            model_module = importlib.import_module(model_module_path)
            
            # Get all model classes from the module
            models = []
            for attr_name in dir(model_module):
                attr = getattr(model_module, attr_name)
                # Check if it's a SQLAlchemy model
                if (isinstance(attr, type) and 
                    hasattr(attr, '__tablename__') and 
                    attr_name != 'Base'):
                    models.append(attr)
            
            if models:
                print(f"    📊 Found {len(models)} model(s) in plugin '{plugin_name}'")
                
                # Register each model with the merger
                for model in models:
                    table_name = self.model_merger.register_model(model, plugin_name)
                
                self.plugin_models[plugin_name] = models
                return models
            else:
                print(f"    ℹ️  No models found in '{plugin_name}'")
                return []
                
        except ImportError:
            print(f"    ℹ️  No models.py found for plugin '{plugin_name}'")
            return []
        except Exception as e:
            print(f"    ⚠️  Error loading models for '{plugin_name}': {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def create_merged_tables(self):
        """Create merged database tables from all registered models"""
        try:
            from core.database import _table_columns
            
            print(f"\n🔀 Creating merged tables...")
            
            # Create merged model for each unique table
            for table_name in _table_columns.keys():
                merged_model = self.model_merger.create_merged_model(table_name)
                if merged_model:
                    # The merged model is now registered in SQLAlchemy
                    pass
            
            # Now create all tables with merged columns
            db.create_all()
            print(f"✅ All merged tables created successfully\n")
            return True
            
        except Exception as e:
            print(f"❌ Error creating merged tables: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_single_plugin(self, app, plugin_name):
        """Load a single plugin with full error handling"""
        plugin_dir = os.path.join(PLUGIN_FOLDER, plugin_name)
        
        # Check if plugin directory exists
        if not os.path.exists(plugin_dir):
            print(f"❌ Plugin '{plugin_name}' directory not found")
            return False
        
        print(f"  → Processing plugin: {plugin_name}")
        
        try:
            # Load plugin configuration and info
            config_data, plugin_info = load_plugin_configs(plugin_name)
            
            # Store in config_loader
            set_plugin_config(plugin_name, config_data, plugin_info)
            
            # Load models (will be registered for merging)
            self.load_plugin_models(plugin_name)
            
            # Load and register routes
            try:
                module_path = f"plugins.{plugin_name}.routes"
                module = importlib.import_module(module_path)
                
                if hasattr(module, 'register'):
                    # Note: We register routes but don't create tables yet
                    # Tables will be created after all plugins are loaded
                    module.register(app)
                    print(f"    ✅ Registered routes for '{plugin_name}'")
                    self.loaded_plugins[plugin_name] = {
                        'config': config_data,
                        'info': plugin_info,
                        'module': module
                    }
                    return True
                else:
                    print(f"    ⚠️  Plugin '{plugin_name}' has no register() function")
                    return False
                    
            except ImportError as e:
                print(f"    ❌ Could not import routes for '{plugin_name}': {e}")
                return False
                
        except Exception as e:
            print(f"    ❌ Error loading plugin '{plugin_name}': {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_loaded_plugins(self):
        """Get list of successfully loaded plugins"""
        return list(self.loaded_plugins.keys())
    
    def is_plugin_loaded(self, plugin_name):
        """Check if a plugin is loaded"""
        return plugin_name in self.loaded_plugins
    
    def get_merged_model(self, table_name):
        """Get a merged model by table name"""
        return self.model_merger.get_merged_model(table_name)

# Global plugin manager instance
plugin_manager = PluginManager()

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
    
    success_count = 0
    
    # PHASE 1: Load all plugins and collect their models
    for plugin_name in enabled_plugins:
        if plugin_manager.load_single_plugin(app, plugin_name):
            success_count += 1
    
    # PHASE 2: Create merged tables from all collected models
    print(f"\n{'='*60}")
    plugin_manager.create_merged_tables()
    print(f"{'='*60}\n")
    
    print(f"✅ Plugin loading complete: {success_count}/{len(enabled_plugins)} successful")
    
    # Register context processor for plugin status
    @app.context_processor
    def inject_plugin_status():
        return dict(
            loaded_plugins=plugin_manager.get_loaded_plugins(),
            is_plugin_loaded=plugin_manager.is_plugin_loaded
        )

def get_plugin_manager():
    """Get the global plugin manager instance"""
    return plugin_manager

def get_merged_model(table_name):
    """Helper function to get merged model from anywhere"""
    return plugin_manager.get_merged_model(table_name)