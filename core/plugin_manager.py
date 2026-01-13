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
        self.registered_blueprints = {}
    
    def load_plugin_models(self, plugin_name):
        """Load database models from a plugin and register them for merging"""
        try:
            model_module_path = f"plugins.{plugin_name}.models"
            model_module = importlib.import_module(model_module_path)
            
            models = []
            for attr_name in dir(model_module):
                attr = getattr(model_module, attr_name)
                if (isinstance(attr, type) and 
                    hasattr(attr, '__tablename__') and 
                    attr_name != 'Base'):
                    models.append(attr)
            
            if models:
                for model in models:
                    self.model_merger.register_model(model, plugin_name)
                
                self.plugin_models[plugin_name] = models
                print(f"      ✓ {len(models)} model(s) loaded")
                return models
            else:
                print(f"      ℹ No models found")
                return []
                
        except ImportError:
            print(f"      ℹ No models.py file")
            return []
        except Exception as e:
            print(f"      ✗ Model loading error: {e}")
            import traceback
            if os.environ.get('DEBUG') == 'true':
                traceback.print_exc()
            return []
    
    def create_merged_tables(self):
        """Create merged database tables from all registered models"""
        try:
            from core.database import _table_columns, _merged_models
            
            if not _table_columns:
                print("  ℹ No tables to merge")
                return True
            
            for table_name in _table_columns.keys():
                merged_model = self.model_merger.create_merged_model(table_name)
                if not merged_model:
                    print(f"  ✗ Failed to merge table: {table_name}")
            
            try:
                db.create_all()
            except Exception as e:
                if "already exists" not in str(e):
                    raise e
            
            return True
            
        except Exception as e:
            print(f"✗ Table creation error: {e}")
            import traceback
            if os.environ.get('DEBUG') == 'true':
                traceback.print_exc()
            return False
    
    def load_single_plugin_models(self, plugin_name):
        """Load only the models from a plugin"""
        plugin_dir = os.path.join(PLUGIN_FOLDER, plugin_name)
        
        if not os.path.exists(plugin_dir):
            print(f"  ✗ {plugin_name}: Directory not found")
            return False
        
        print(f"  📦 {plugin_name}")
        
        try:
            config_data, plugin_info = load_plugin_configs(plugin_name)
            set_plugin_config(plugin_name, config_data, plugin_info)
            self.load_plugin_models(plugin_name)
            return True
                
        except Exception as e:
            print(f"      ✗ Loading error: {e}")
            import traceback
            if os.environ.get('DEBUG') == 'true':
                traceback.print_exc()
            return False
    
    def register_plugin_routes(self, app, plugin_name):
        """Register routes for a plugin after all models are loaded"""
        try:
            if plugin_name in self.registered_blueprints:
                return True
            
            module_path = f"plugins.{plugin_name}.routes"
            
            if module_path in sys.modules:
                module = importlib.reload(sys.modules[module_path])
            else:
                module = importlib.import_module(module_path)
            
            if hasattr(module, 'register'):
                module.register(app)
                
                if hasattr(module, 'bp'):
                    self.registered_blueprints[plugin_name] = module.bp
                    url_prefix = module.bp.url_prefix or '/'
                    print(f"      ✓ Routes registered at {url_prefix}")
                
                self.loaded_plugins[plugin_name] = {
                    'config': get_plugin_config(plugin_name),
                    'info': get_plugin_info(plugin_name),
                    'module': module
                }
                return True
            else:
                print(f"      ✗ No register() function")
                return False
                
        except ImportError as e:
            print(f"      ✗ Routes import error: {e}")
            return False
        except Exception as e:
            print(f"      ✗ Registration error: {e}")
            import traceback
            if os.environ.get('DEBUG') == 'true':
                traceback.print_exc()
            return False
    
    def unregister_plugin_routes(self, app, plugin_name):
        """Unregister routes for a plugin"""
        try:
            if plugin_name in self.registered_blueprints:
                blueprint = self.registered_blueprints[plugin_name]
                
                if blueprint.name in app.blueprints:
                    del self.registered_blueprints[plugin_name]
                
                if plugin_name in self.loaded_plugins:
                    del self.loaded_plugins[plugin_name]
                
                return True
            return False
        except Exception as e:
            print(f"  ✗ Unregister error for {plugin_name}: {e}")
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
    """Load enabled plugins and register their configurations"""
    if not enabled_plugins:
        print("ℹ No plugins enabled\n")
        return
    
    print(f"\n{'='*70}")
    print(f"  🔌 Loading {len(enabled_plugins)} Plugin(s)")
    print(f"{'='*70}\n")
    
    # PHASE 1: Load plugin models
    print("📦 Phase 1: Loading Models")
    print("-" * 70)
    success_count = 0
    for plugin_name in enabled_plugins:
        if plugin_manager.load_single_plugin_models(plugin_name):
            success_count += 1
    print()
    
    # PHASE 2: Create merged tables
    print("🔧 Phase 2: Creating Database Tables")
    print("-" * 70)
    plugin_manager.create_merged_tables()
    
    # Show merged models summary
    from core.database import _merged_models, _table_columns
    if _merged_models:
        print(f"  ✓ {len(_merged_models)} table(s) created")
        for table_name in _merged_models.keys():
            if table_name in _table_columns:
                columns = _table_columns[table_name]['columns']
                plugins = _table_columns[table_name]['plugins']
                print(f"      • {table_name}: {len(columns)} columns from {len(plugins)} plugin(s)")
    print()
    
    # PHASE 3: Register routes
    print("🔗 Phase 3: Registering Routes")
    print("-" * 70)
    routes_success = 0
    for plugin_name in enabled_plugins:
        print(f"  🔌 {plugin_name}")
        if plugin_manager.register_plugin_routes(app, plugin_name):
            routes_success += 1
    
    print(f"\n{'='*70}")
    print(f"  ✅ Plugin Loading Complete")
    print(f"{'='*70}")
    print(f"  📊 Models Loaded: {success_count}/{len(enabled_plugins)}")
    print(f"  🔗 Routes Registered: {routes_success}/{len(enabled_plugins)}")
    print(f"  🗃️ Tables Created: {len(_merged_models)}")
    print(f"{'='*70}\n")

def get_plugin_manager():
    """Get the global plugin manager instance"""
    return plugin_manager

def get_merged_model(table_name):
    """Helper function to get merged model from anywhere"""
    return plugin_manager.get_merged_model(table_name)