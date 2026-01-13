# plugins/admincp/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from functools import wraps
from core.database import db, get_model_merger
from core.plugin_manager import get_plugin_manager
from core.config_loader import main_config, get_plugin_config, get_plugin_info
from core.settings_loader import get_current_settings, reload_settings
import json
import os
import importlib
import sys

bp = Blueprint('admincp', __name__, 
               template_folder='templates',
               static_folder='static',
               url_prefix='/admincp')

# Simple admin check (you should implement proper authentication)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TODO: Implement proper authentication
        # For now, allowing all access - CHANGE THIS IN PRODUCTION
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@admin_required
def dashboard():
    """Main admin dashboard"""
    plugin_manager = get_plugin_manager()
    merger = get_model_merger()
    
    # Get system stats
    loaded_plugins = plugin_manager.get_loaded_plugins()
    all_models = merger.get_all_merged_models()
    
    # Count total records across all models
    total_records = 0
    model_stats = {}
    for table_name, model in all_models.items():
        try:
            count = db.session.query(model).count()
            total_records += count
            model_stats[table_name] = count
        except:
            model_stats[table_name] = 0
    
    stats = {
        'total_plugins': len(loaded_plugins),
        'total_tables': len(all_models),
        'total_records': total_records,
        'model_stats': model_stats
    }
    
    return render_template('admincp/dashboard.html', 
                         stats=stats,
                         loaded_plugins=loaded_plugins,
                         main_config=main_config)

@bp.route('/plugins')
@admin_required
def plugins():
    """Plugin management page"""
    plugin_manager = get_plugin_manager()
    
    # Get all available plugins
    plugins_dir = os.path.join(os.path.dirname(__file__), '..', '..')
    plugins_path = os.path.join(plugins_dir, 'plugins')
    
    available_plugins = []
    if os.path.exists(plugins_path):
        for item in os.listdir(plugins_path):
            plugin_dir = os.path.join(plugins_path, item)
            if os.path.isdir(plugin_dir) and not item.startswith('_'):
                plugin_info = get_plugin_info(item) or {}
                plugin_config = get_plugin_config(item) or {}
                available_plugins.append({
                    'name': item,
                    'loaded': plugin_manager.is_plugin_loaded(item),
                    'info': plugin_info,
                    'config': plugin_config
                })
    
    return render_template('admincp/plugins.html', plugins=available_plugins)

@bp.route('/database')
@admin_required
def database():
    """Database management page"""
    merger = get_model_merger()
    all_models = merger.get_all_merged_models()
    
    from core.database import _table_columns
    
    table_details = {}
    for table_name, model in all_models.items():
        if table_name in _table_columns:
            info = _table_columns[table_name]
            table_details[table_name] = {
                'columns': list(info['columns'].keys()),
                'plugins': info['plugins'],
                'record_count': 0
            }
            try:
                table_details[table_name]['record_count'] = db.session.query(model).count()
            except:
                pass
    
    return render_template('admincp/database.html', tables=table_details)

@bp.route('/database/browse/<table_name>')
@admin_required
def browse_table(table_name):
    """Browse table data"""
    merger = get_model_merger()
    model = merger.get_merged_model(table_name)
    
    if not model:
        flash(f'Table {table_name} not found', 'error')
        return redirect(url_for('admincp.database'))
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    try:
        pagination = db.session.query(model).paginate(
            page=page, 
            per_page=per_page,
            error_out=False
        )
        
        # Get column names
        from sqlalchemy import inspect
        mapper = inspect(model)
        columns = [col.key for col in mapper.columns]
        
        # Convert records to dicts
        records = []
        for record in pagination.items:
            record_dict = {}
            for col in columns:
                try:
                    value = getattr(record, col)
                    record_dict[col] = str(value) if value is not None else None
                except:
                    record_dict[col] = None
            records.append(record_dict)
        
        return render_template('admincp/browse_table.html',
                             table_name=table_name,
                             columns=columns,
                             records=records,
                             pagination=pagination)
    except Exception as e:
        flash(f'Error browsing table: {str(e)}', 'error')
        return redirect(url_for('admincp.database'))

@bp.route('/config')
@admin_required
def config():
    """Configuration management page"""
    settings = get_current_settings()
    
    # Get config.json path
    project_root = os.path.join(os.path.dirname(__file__), '..', '..')
    config_path = os.path.join(project_root, 'config.json')
    
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    return render_template('admincp/config.html', 
                         config_content=config_content,
                         settings=settings)

@bp.route('/config/save', methods=['POST'])
@admin_required
def save_config():
    """Save configuration changes"""
    try:
        config_content = request.form.get('config_content')
        
        # Validate JSON
        json.loads(config_content)
        
        # Save to file
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        config_path = os.path.join(project_root, 'config.json')
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Reload settings
        reload_settings()
        
        flash('Configuration saved successfully! Restart the application for changes to take effect.', 'success')
    except json.JSONDecodeError as e:
        flash(f'Invalid JSON: {str(e)}', 'error')
    except Exception as e:
        flash(f'Error saving configuration: {str(e)}', 'error')
    
    return redirect(url_for('admincp.config'))

@bp.route('/plugin/toggle/<plugin_name>', methods=['POST'])
@admin_required
def toggle_plugin(plugin_name):
    """Enable or disable a plugin"""
    try:
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        config_path = os.path.join(project_root, 'config.json')
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'PLUGINS_ENABLED' not in config:
            config['PLUGINS_ENABLED'] = []
        
        if plugin_name in config['PLUGINS_ENABLED']:
            config['PLUGINS_ENABLED'].remove(plugin_name)
            action = 'disabled'
        else:
            config['PLUGINS_ENABLED'].append(plugin_name)
            action = 'enabled'
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        reload_settings()
        
        return jsonify({
            'success': True,
            'message': f'Plugin {plugin_name} {action}. Restart required.',
            'action': action
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@bp.route('/database/query', methods=['POST'])
@admin_required
def execute_query():
    """Execute custom SQL query (read-only for safety)"""
    try:
        query = request.form.get('query', '').strip()
        
        # Only allow SELECT queries for safety
        if not query.upper().startswith('SELECT'):
            return jsonify({
                'success': False,
                'message': 'Only SELECT queries are allowed'
            }), 400
        
        result = db.session.execute(db.text(query))
        rows = result.fetchall()
        columns = result.keys()
        
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))
        
        return jsonify({
            'success': True,
            'columns': list(columns),
            'data': data,
            'count': len(data)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@bp.route('/logs')
@admin_required
def logs():
    """View application logs"""
    # Check for common log files
    project_root = os.path.join(os.path.dirname(__file__), '..', '..')
    log_files = []
    
    common_log_paths = ['app.log', 'error.log', 'access.log', 'logs/app.log']
    for log_path in common_log_paths:
        full_path = os.path.join(project_root, log_path)
        if os.path.exists(full_path):
            log_files.append(log_path)
    
    selected_log = request.args.get('file', log_files[0] if log_files else None)
    log_content = ""
    
    if selected_log:
        log_path = os.path.join(project_root, selected_log)
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    log_content = ''.join(lines[-1000:])  # Last 1000 lines
            except:
                log_content = "Error reading log file"
    
    return render_template('admincp/logs.html',
                         log_files=log_files,
                         selected_log=selected_log,
                         log_content=log_content)

@bp.route('/system')
@admin_required
def system():
    """System information page"""
    import platform
    import psutil
    
    # System info
    system_info = {
        'python_version': sys.version,
        'platform': platform.platform(),
        'processor': platform.processor(),
        'cpu_count': psutil.cpu_count(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_total': f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
        'memory_used': f"{psutil.virtual_memory().used / (1024**3):.2f} GB",
        'memory_percent': psutil.virtual_memory().percent,
        'disk_total': f"{psutil.disk_usage('/').total / (1024**3):.2f} GB",
        'disk_used': f"{psutil.disk_usage('/').used / (1024**3):.2f} GB",
        'disk_percent': psutil.disk_usage('/').percent
    }
    
    # Installed packages
    import pkg_resources
    installed_packages = sorted([f"{pkg.key}=={pkg.version}" 
                                for pkg in pkg_resources.working_set])
    
    return render_template('admincp/system.html',
                         system_info=system_info,
                         packages=installed_packages)

@bp.route('/database/record/delete/<table_name>/<int:record_id>', methods=['POST'])
@admin_required
def delete_record(table_name, record_id):
    """Delete a record from a table"""
    try:
        merger = get_model_merger()
        model = merger.get_merged_model(table_name)
        
        if not model:
            return jsonify({'success': False, 'message': 'Table not found'}), 404
        
        record = db.session.query(model).get(record_id)
        if record:
            db.session.delete(record)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Record deleted'})
        else:
            return jsonify({'success': False, 'message': 'Record not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

def register(app):
    """Register the admin control panel blueprint"""
    app.register_blueprint(bp)