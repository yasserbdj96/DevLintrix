# core/plugin_manager.py
import importlib
import os
import sys
from core.config_loader import load_plugin_configs, set_plugin_config, get_plugin_config, get_plugin_info
from core.database import db, ModelMerger

PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), "../plugins")

class PluginManager:
    """Manages plugin lifecycle and database models with merging support"""
    
    def __init__(self):
        self.loaded_plugins = {}
        self.plugin_models = {}
        self.model_merger = ModelMerger()
        self.registered_blueprints = {}  # Track registered blueprints
    
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
            from core.database import _table_columns, _merged_models
            
            print(f"\n🔀 Creating merged tables...")
            
            # Create merged model for each unique table
            for table_name in _table_columns.keys():
                merged_model = self.model_merger.create_merged_model(table_name)
                if merged_model:
                    print(f"    ✅ Created merged model for '{table_name}'")
                else:
                    print(f"    ⚠️  Failed to create merged model for '{table_name}'")
            
            # Try to create tables, ignoring errors if they already exist
            try:
                db.create_all()
                print(f"✅ All merged tables created successfully\n")
            except Exception as e:
                # If tables already exist, that's fine - just log it
                if "already exists" in str(e):
                    print(f"ℹ️  Tables already exist, continuing...")
                else:
                    # Re-raise if it's a different error
                    raise e
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating merged tables: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_single_plugin_models(self, plugin_name):
        """Load only the models from a plugin (for phase 1 loading)"""
        plugin_dir = os.path.join(PLUGIN_FOLDER, plugin_name)
        
        # Check if plugin directory exists
        if not os.path.exists(plugin_dir):
            print(f"❌ Plugin '{plugin_name}' directory not found")
            return False
        
        print(f"  → Loading models for plugin: {plugin_name}")
        
        try:
            # Load plugin configuration and info
            config_data, plugin_info = load_plugin_configs(plugin_name)
            
            # Store in config_loader
            set_plugin_config(plugin_name, config_data, plugin_info)
            
            # Load models (will be registered for merging)
            self.load_plugin_models(plugin_name)
            
            return True
                
        except Exception as e:
            print(f"    ❌ Error loading plugin '{plugin_name}': {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def register_plugin_routes(self, app, plugin_name):
        """Register routes for a plugin after all models are loaded"""
        try:
            # Check if already registered
            if plugin_name in self.registered_blueprints:
                print(f"    ℹ️  Plugin '{plugin_name}' routes already registered, skipping")
                return True
            
            module_path = f"plugins.{plugin_name}.routes"
            
            # Reload module if it was already imported
            if module_path in sys.modules:
                module = importlib.reload(sys.modules[module_path])
            else:
                module = importlib.import_module(module_path)
            
            if hasattr(module, 'register'):
                module.register(app)
                print(f"    ✅ Registered routes for '{plugin_name}'")
                
                # Store blueprint reference
                if hasattr(module, 'bp'):
                    self.registered_blueprints[plugin_name] = module.bp
                
                self.loaded_plugins[plugin_name] = {
                    'config': get_plugin_config(plugin_name),
                    'info': get_plugin_info(plugin_name),
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
            print(f"    ❌ Error registering routes for '{plugin_name}': {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def unregister_plugin_routes(self, app, plugin_name):
        """Unregister routes for a plugin"""
        try:
            if plugin_name in self.registered_blueprints:
                blueprint = self.registered_blueprints[plugin_name]
                
                # Remove blueprint from app
                if blueprint.name in app.blueprints:
                    # Flask doesn't officially support unregistering blueprints
                    # So we'll just mark it as unloaded in our tracking
                    print(f"    🗑️  Marked plugin '{plugin_name}' routes for removal")
                    del self.registered_blueprints[plugin_name]
                
                if plugin_name in self.loaded_plugins:
                    del self.loaded_plugins[plugin_name]
                
                return True
            return False
        except Exception as e:
            print(f"    ⚠️  Error unregistering plugin '{plugin_name}': {e}")
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
    
    # PHASE 1: Load ALL plugin models first (without registering routes)
    print(f"\n📦 Phase 1: Loading plugin models...")
    for plugin_name in enabled_plugins:
        if plugin_manager.load_single_plugin_models(plugin_name):
            success_count += 1
    
    # PHASE 2: Create merged tables from ALL collected models
    print(f"\n{'='*60}")
    print(f"🔧 Phase 2: Creating merged tables...")
    plugin_manager.create_merged_tables()
    print(f"{'='*60}\n")
    
    # PHASE 3: Register routes for all plugins (now models are ready)
    print(f"🔗 Phase 3: Registering plugin routes...")
    routes_success_count = 0
    for plugin_name in enabled_plugins:
        if plugin_manager.register_plugin_routes(app, plugin_name):
            routes_success_count += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Plugin loading complete:")
    print(f"   - Models loaded: {success_count}/{len(enabled_plugins)}")
    print(f"   - Routes registered: {routes_success_count}/{len(enabled_plugins)}")
    print(f"{'='*60}\n")
    
    # Debug: Show all merged models
    from core.database import _merged_models, _table_columns
    print(f"📊 Merged models created:")
    for table_name, model in _merged_models.items():
        if table_name in _table_columns:
            columns = list(_table_columns[table_name]['columns'].keys())
            plugins = ', '.join(_table_columns[table_name]['plugins'])
            print(f"   - {table_name} ({model.__name__}): {len(columns)} columns from [{plugins}]")

def get_plugin_manager():
    """Get the global plugin manager instance"""
    return plugin_manager

def get_merged_model(table_name):
    """Helper function to get merged model from anywhere"""
    return plugin_manager.get_merged_model(table_name)