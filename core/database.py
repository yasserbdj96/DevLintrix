# core/database.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, inspect as sqlalchemy_inspect
import copy
import importlib

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Global registry for merged models
_merged_models = {}
_table_columns = {}  # Store all columns per table name


# core/database.py

class ModelMerger:
    """Handles merging of models with the same table names from different plugins"""
    
    @staticmethod
    def register_model(model_class, plugin_name):
        """Register a model and merge it if table name already exists"""
        table_name = model_class.__tablename__
        
        print(f"    🔧 Registering model '{model_class.__name__}' for table '{table_name}' from plugin '{plugin_name}'")
        
        # Initialize storage for this table if first time
        if table_name not in _table_columns:
            _table_columns[table_name] = {
                'columns': {},
                'relationships': {},
                'indexes': set(),
                'constraints': set(),
                'plugins': [],
                'base_class_name': model_class.__name__,
                'base_classes': [],
                'merged_model_created': False  # NEW: Track if merged model was created
            }
        else:
            # If table already exists, we need to recreate the merged model
            _table_columns[table_name]['merged_model_created'] = False
        
        # Store plugin info
        _table_columns[table_name]['plugins'].append(plugin_name)
        
        # Store the actual model class for reference
        _table_columns[table_name]['model_class'] = model_class
        
        # Register parent classes (UserMixin, TimestampMixin, etc.)
        for base in model_class.__bases__:
            if base != db.Model and base not in _table_columns[table_name]['base_classes']:
                _table_columns[table_name]['base_classes'].append(base)
        
        # Get columns from the model
        mapper = sqlalchemy_inspect(model_class)
        
        for col in mapper.columns:
            col_name = col.key
            
            if col_name in _table_columns[table_name]['columns']:
                print(f"    ⚠️  Column '{col_name}' in table '{table_name}' already defined by another plugin")
            else:
                # Create a copy of the column with all attributes
                copied_col = Column(
                    col.type,
                    primary_key=col.primary_key,
                    nullable=col.nullable,
                    default=col.default,
                    unique=col.unique,
                    index=col.index,
                    server_default=col.server_default,
                    server_onupdate=col.server_onupdate,
                    comment=col.comment
                )
                _table_columns[table_name]['columns'][col_name] = copied_col
                
                print(f"    ➕ Added column '{col_name}' to '{table_name}' from plugin '{plugin_name}'")
        
        # If merged model was already created, delete it so it gets recreated
        if table_name in _merged_models:
            print(f"    🔄 Model for '{table_name}' needs recreation after new column")
            del _merged_models[table_name]
        
        return table_name
    
    @staticmethod
    def create_merged_model(table_name, force_recreate=False):
        """Create a merged model class with all columns from all plugins"""
        if table_name not in _table_columns:
            print(f"    ❌ No table info found for '{table_name}'")
            return None
        
        table_info = _table_columns[table_name]
        
        if not table_info['columns']:
            print(f"    ⚠️  No columns found for table '{table_name}'")
            return None
        
        # Check if we already created this merged model and don't need to recreate
        if table_name in _merged_models and not force_recreate and table_info.get('merged_model_created', False):
            return _merged_models[table_name]
        
        print(f"    🔀 Creating merged model for table '{table_name}'...")
        
        # Prepare attributes dictionary for the new class
        attrs = {
            '__tablename__': table_name,
            '__table_args__': {'extend_existing': True},
            '__module__': 'core.database'  # Important for SQLAlchemy
        }
        
        # Add all merged columns
        for col_name, column in table_info['columns'].items():
            attrs[col_name] = column
        
        # Base classes: db.Model + any mixins
        base_classes = [db.Model]
        for base in table_info['base_classes']:
            if base not in base_classes:
                base_classes.append(base)
        
        # Use the model class from the first plugin as the base
        if 'model_class' in table_info:
            # Copy the class attributes but keep the new columns
            original_model = table_info['model_class']
            for attr_name, attr_value in original_model.__dict__.items():
                if not attr_name.startswith('_') and attr_name not in attrs and not callable(attr_value):
                    attrs[attr_name] = attr_value
        
        # Copy methods from original models
        for plugin in table_info['plugins']:
            try:
                model_module_path = f"plugins.{plugin}.models"
                model_module = importlib.import_module(model_module_path)
                
                # Find the model class in the module
                for attr_name in dir(model_module):
                    attr = getattr(model_module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, '__tablename__') and 
                        attr.__tablename__ == table_name):
                        
                        # Copy methods
                        for method_name in dir(attr):
                            method = getattr(attr, method_name)
                            if callable(method) and not method_name.startswith('_'):
                                attrs[method_name] = method
                        break
            except ImportError:
                pass
        
        # Name of the merged class
        merged_class_name = table_info['base_class_name']
        
        # Create the merged class dynamically
        merged_model = type(merged_class_name, tuple(base_classes), attrs)
        
        # Store in global registry
        _merged_models[table_name] = merged_model
        table_info['merged_model_created'] = True
        
        plugins_str = ', '.join(table_info['plugins'])
        print(f"    ✅ Created merged model '{merged_class_name}' for table '{table_name}' (from plugins: {plugins_str})")
        print(f"       Total columns: {len(table_info['columns'])}")
        
        return merged_model

    @staticmethod
    def get_merged_model(table_name):
        """Get a merged model by table name"""
        return _merged_models.get(table_name)

    @staticmethod
    def get_all_merged_models():
        """Get all merged models"""
        return _merged_models


def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)

    with app.app_context():
        # Check if tables already exist before creating them
        db.create_all()
        print("✅ Database initialized successfully")


def get_db():
    """Get database instance"""
    return db


def get_model_merger():
    """Get the model merger instance"""
    return ModelMerger