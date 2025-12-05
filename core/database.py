# core/database.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, inspect
import copy

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Global registry for merged models
_merged_models = {}
_table_columns = {}  # Store all columns per table name

class ModelMerger:
    """Handles merging of models with same table names from different plugins"""
    
    @staticmethod
    def register_model(model_class, plugin_name):
        """Register a model and merge it if table name already exists"""
        table_name = model_class.__tablename__
        
        # Initialize storage for this table if first time
        if table_name not in _table_columns:
            _table_columns[table_name] = {
                'columns': {},
                'relationships': {},
                'indexes': set(),
                'constraints': set(),
                'plugins': [],
                'base_class_name': model_class.__name__,
                'base_classes': []  # Store parent classes (like UserMixin)
            }
        
        # Store plugin info
        _table_columns[table_name]['plugins'].append(plugin_name)
        
        # Extract parent classes (like UserMixin)
        for base in model_class.__bases__:
            if base != db.Model and base not in _table_columns[table_name]['base_classes']:
                _table_columns[table_name]['base_classes'].append(base)
        
        # Extract all columns from the model
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            
            # Check if it's a Column
            if isinstance(attr, Column):
                column_name = attr.name or attr_name
                
                # If column already exists, check compatibility
                if column_name in _table_columns[table_name]['columns']:
                    existing_col = _table_columns[table_name]['columns'][column_name]
                    # You could add validation here to ensure columns are compatible
                    print(f"    ⚠️  Column '{column_name}' in table '{table_name}' already defined by another plugin")
                else:
                    # Store the column
                    _table_columns[table_name]['columns'][column_name] = copy.deepcopy(attr)
                    print(f"    ➕ Added column '{column_name}' to '{table_name}' from plugin '{plugin_name}'")
        
        # Store relationships
        if hasattr(model_class, '__mapper__'):
            for rel in model_class.__mapper__.relationships:
                rel_name = rel.key
                if rel_name not in _table_columns[table_name]['relationships']:
                    _table_columns[table_name]['relationships'][rel_name] = rel
        
        return table_name
    
    @staticmethod
    def create_merged_model(table_name):
        """Create a merged model class with all columns from all plugins"""
        if table_name not in _table_columns:
            return None
        
        table_info = _table_columns[table_name]
        
        # Prepare attributes dictionary for the new class
        attrs = {
            '__tablename__': table_name,
            '__table_args__': {'extend_existing': True}
        }
        
        # Add all merged columns
        for col_name, column in table_info['columns'].items():
            attrs[col_name] = column
        
        # Add relationships if any
        for rel_name, relationship in table_info['relationships'].items():
            attrs[rel_name] = relationship
        
        # Get base classes (like UserMixin) + db.Model
        base_classes = tuple(table_info['base_classes']) + (db.Model,)
        
        # Create the merged class dynamically
        merged_class_name = table_info['base_class_name']
        merged_model = type(merged_class_name, base_classes, attrs)
        
        # Store in global registry
        _merged_models[table_name] = merged_model
        
        plugins_str = ', '.join(table_info['plugins'])
        print(f"    🔀 Created merged model '{merged_class_name}' for table '{table_name}' (from plugins: {plugins_str})")
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
        # Create all tables (will be populated by plugin manager)
        db.create_all()
        print("✅ Database initialized successfully")

def get_db():
    """Get database instance"""
    return db

def get_model_merger():
    """Get the model merger instance"""
    return ModelMerger