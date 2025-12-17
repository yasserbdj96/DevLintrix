# plugins/admin/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app
import json
import os
import sys
import hashlib
import psutil
import time
from datetime import datetime
from functools import wraps
from core.config_loader import get_plugin_config, get_plugin_info, main_config
from core.settings_loader import reload_settings, get_current_settings
from core.plugin_manager import plugin_manager
from core.database import db

bp = Blueprint("admin", __name__, template_folder="templates", static_folder="static", url_prefix="/admin")

# Global maintenance mode state
MAINTENANCE_MODE = {
    'enabled': False,
    'message': 'System is currently under maintenance. Please check back later.',
    'allowed_ips': ['127.0.0.1']
}

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_maintenance_mode():
    """Check if maintenance mode is active"""
    if MAINTENANCE_MODE['enabled']:
        client_ip = request.remote_addr
        if client_ip not in MAINTENANCE_MODE['allowed_ips']:
            return True
    return False

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_authenticated' not in session:
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.before_request
def check_maintenance():
    """Check maintenance mode before each request"""
    # Skip maintenance check for admin routes
    if request.endpoint and 'admin' in request.endpoint:
        return None
    
    if check_maintenance_mode():
        return render_template('maintenance.html', 
                             message=MAINTENANCE_MODE['message']), 503

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        admin_config = get_plugin_config('admin')
        stored_password = admin_config.get('ADMIN_PASSWORD', 'admin1234')
        
        # Support both plain text (for backwards compatibility) and hashed
        if password == stored_password or hash_password(password) == stored_password:
            session['admin_authenticated'] = True
            session['login_time'] = datetime.now().isoformat()
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid password")
    
    return render_template('admin_login.html')

@bp.route('/logout')
def logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    session.pop('login_time', None)
    return redirect(url_for('admin.login'))

@bp.route('/')
@admin_required
def dashboard():
    """Enhanced admin dashboard with system metrics"""
    # Get main config
    config = get_current_settings()
    
    # Get all available plugins
    plugins_dir = os.path.join(os.path.dirname(__file__), '..')
    available_plugins = []
    
    for item in os.listdir(plugins_dir):
        item_path = os.path.join(plugins_dir, item)
        if os.path.isdir(item_path) and not item.startswith('_'):
            plugin_info_path = os.path.join(item_path, 'plugin.json')
            if os.path.exists(plugin_info_path):
                with open(plugin_info_path, 'r') as f:
                    plugin_info = json.load(f)
                    
                    has_config = os.path.exists(os.path.join(item_path, 'config.json'))
                    
                    available_plugins.append({
                        'name': item,
                        'info': plugin_info,
                        'enabled': item in config.get('PLUGINS_ENABLED', []),
                        'has_config': has_config,
                        'loaded': plugin_manager.is_plugin_loaded(item)
                    })
    
    # Get system metrics
    system_info = {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory': psutil.virtual_memory()._asdict(),
        'disk': psutil.disk_usage('/')._asdict(),
        'uptime': time.time() - psutil.boot_time()
    }
    
    return render_template('admin_dashboard.html', 
                         config=config, 
                         available_plugins=available_plugins,
                         loaded_plugins=plugin_manager.get_loaded_plugins(),
                         system_info=system_info,
                         maintenance_mode=MAINTENANCE_MODE)

@bp.route('/settings')
@admin_required
def settings_page():
    """Real-time settings editor"""
    config = get_current_settings()
    return render_template('admin_settings.html', config=config)

@bp.route('/maintenance')
@admin_required
def maintenance_page():
    """Maintenance mode control panel"""
    return render_template('admin_maintenance.html', maintenance=MAINTENANCE_MODE)

@bp.route('/system')
@admin_required
def system_page():
    """System monitoring page"""
    return render_template('admin_system.html')

@bp.route('/logs')
@admin_required
def logs_page():
    """System logs viewer"""
    log_file = 'app.log'
    logs = []
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = f.readlines()[-100:]  # Last 100 lines
    
    return render_template('admin_logs.html', logs=logs)

@bp.route('/plugin-config/<plugin_name>')
@admin_required
def plugin_config_editor(plugin_name):
    """Plugin configuration editor page"""
    plugin_dir = os.path.join(os.path.dirname(__file__), '..', plugin_name)
    config_path = os.path.join(plugin_dir, 'config.json')
    
    if not os.path.exists(config_path):
        return "Plugin config not found", 404
    
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    plugin_info_path = os.path.join(plugin_dir, 'plugin.json')
    plugin_info = {}
    if os.path.exists(plugin_info_path):
        with open(plugin_info_path, 'r') as f:
            plugin_info = json.load(f)
    
    return render_template('plugin_config_editor.html',
                         plugin_name=plugin_name,
                         plugin_info=plugin_info,
                         config_content=config_content)

@bp.route('/env-editor')
@admin_required
def env_editor():
    """Environment variables editor page"""
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
    
    return render_template('env_editor.html', env_content=env_content)

# ==================== API ENDPOINTS ====================

@bp.route('/api/toggle-maintenance', methods=['POST'])
@admin_required
def toggle_maintenance():
    """Toggle maintenance mode"""
    data = request.get_json()
    enabled = data.get('enabled', False)
    message = data.get('message', 'System is under maintenance')
    allowed_ips = data.get('allowed_ips', ['127.0.0.1'])
    
    MAINTENANCE_MODE['enabled'] = enabled
    MAINTENANCE_MODE['message'] = message
    MAINTENANCE_MODE['allowed_ips'] = allowed_ips
    
    return jsonify({
        'success': True,
        'message': f"Maintenance mode {'enabled' if enabled else 'disabled'}",
        'maintenance': MAINTENANCE_MODE
    })

@bp.route('/api/update-setting', methods=['POST'])
@admin_required
def update_setting():
    """Update a single setting in real-time"""
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    restart_required = data.get('restart_required', False)
    
    if not key:
        return jsonify({'success': False, 'message': 'Setting key required'}), 400
    
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update the setting
        config[key] = value
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        # Reload settings in memory (no restart for most settings)
        if not restart_required:
            reload_settings()
            current_app.config[key] = value
        
        return jsonify({
            'success': True,
            'message': f"Setting '{key}' updated successfully" + 
                      (" (restart required)" if restart_required else " (applied immediately)"),
            'restart_required': restart_required
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/toggle-plugin', methods=['POST'])
@admin_required
def toggle_plugin():
    """Toggle plugin on/off"""
    data = request.get_json()
    plugin_name = data.get('plugin_name')
    enable = data.get('enable', False)
    
    if not plugin_name:
        return jsonify({'success': False, 'message': 'Plugin name required'}), 400
    
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'PLUGINS_ENABLED' not in config:
            config['PLUGINS_ENABLED'] = []
        
        if enable:
            if plugin_name not in config['PLUGINS_ENABLED']:
                config['PLUGINS_ENABLED'].append(plugin_name)
        else:
            if plugin_name in config['PLUGINS_ENABLED']:
                config['PLUGINS_ENABLED'].remove(plugin_name)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        return jsonify({
            'success': True,
            'message': f"Plugin '{plugin_name}' {'enabled' if enable else 'disabled'}. Restart server to apply.",
            'requires_restart': True
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/save-plugin-config', methods=['POST'])
@admin_required
def save_plugin_config():
    """Save plugin configuration"""
    data = request.get_json()
    plugin_name = data.get('plugin_name')
    config_content = data.get('config_content')
    
    if not plugin_name or config_content is None:
        return jsonify({'success': False, 'message': 'Plugin name and config required'}), 400
    
    try:
        json.loads(config_content)
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'message': f'Invalid JSON: {str(e)}'}), 400
    
    plugin_dir = os.path.join(os.path.dirname(__file__), '..', plugin_name)
    config_path = os.path.join(plugin_dir, 'config.json')
    
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        return jsonify({
            'success': True,
            'message': f"Config for '{plugin_name}' saved. Restart to apply changes."
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/system-metrics')
@admin_required
def system_metrics():
    """Get real-time system metrics"""
    try:
        metrics = {
            'cpu': {
                'percent': psutil.cpu_percent(interval=1),
                'count': psutil.cpu_count(),
                'per_cpu': psutil.cpu_percent(interval=1, percpu=True)
            },
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent,
                'used': psutil.virtual_memory().used
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            },
            'network': {
                'bytes_sent': psutil.net_io_counters().bytes_sent,
                'bytes_recv': psutil.net_io_counters().bytes_recv
            },
            'process': {
                'pid': os.getpid(),
                'threads': len(psutil.Process(os.getpid()).threads()),
                'connections': len(psutil.Process(os.getpid()).connections())
            },
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/database-stats')
@admin_required
def database_stats():
    """Get database statistics"""
    try:
        from core.database import _merged_models, _table_columns
        
        stats = {
            'tables': [],
            'total_tables': len(_merged_models),
            'total_plugins': len(set(
                plugin 
                for table_info in _table_columns.values() 
                for plugin in table_info.get('plugins', [])
            ))
        }
        
        for table_name, model in _merged_models.items():
            if table_name in _table_columns:
                table_info = _table_columns[table_name]
                
                # Get row count
                try:
                    row_count = db.session.query(model).count()
                except:
                    row_count = 0
                
                stats['tables'].append({
                    'name': table_name,
                    'model': model.__name__,
                    'columns': len(table_info['columns']),
                    'plugins': table_info['plugins'],
                    'rows': row_count
                })
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/restart-server', methods=['POST'])
@admin_required
def restart_server():
    """Trigger server restart"""
    def restart():
        import time
        time.sleep(1)
        
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            os._exit(3)
        else:
            python = sys.executable
            os.execl(python, python, *sys.argv)
    
    import threading
    threading.Thread(target=restart).start()
    
    return jsonify({'success': True, 'message': 'Server restarting...'})

@bp.route('/api/clear-cache', methods=['POST'])
@admin_required
def clear_cache():
    """Clear application cache"""
    try:
        # Reload settings
        reload_settings()
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/backup-config', methods=['POST'])
@admin_required
def backup_config():
    """Create backup of configuration files"""
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'config_backup_{timestamp}.json')
        
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
        
        import shutil
        shutil.copy2(config_path, backup_file)
        
        return jsonify({
            'success': True,
            'message': f'Backup created: config_backup_{timestamp}.json',
            'filename': f'config_backup_{timestamp}.json'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def register(app):
    """Register blueprint with Flask app"""
    app.register_blueprint(bp)
    print(f"    🔗 Admin plugin routes registered at /admin")