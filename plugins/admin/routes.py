# plugins/admin/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
import json
import os
import sys
import signal
from core.config_loader import get_plugin_config, get_plugin_info
from core.plugin_manager import plugin_manager
from functools import wraps

bp = Blueprint("admin", __name__, template_folder="templates", static_folder="static", url_prefix="/admin")

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_authenticated' not in session:
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        admin_config = get_plugin_config('admin')
        correct_password = admin_config.get('ADMIN_PASSWORD', 'admin123')
        
        if password == correct_password:
            session['admin_authenticated'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid password")
    
    return render_template('admin_login.html')

@bp.route('/logout')
def logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin.login'))

@bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard"""
    # Get main config
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
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
                    
                    # Check if plugin has config.json
                    has_config = os.path.exists(os.path.join(item_path, 'config.json'))
                    
                    available_plugins.append({
                        'name': item,
                        'info': plugin_info,
                        'enabled': item in config.get('PLUGINS_ENABLED', []),
                        'has_config': has_config
                    })
    
    return render_template('admin_dashboard.html', 
                         config=config, 
                         available_plugins=available_plugins,
                         loaded_plugins=plugin_manager.get_loaded_plugins())

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
    
    # Get plugin info
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

@bp.route('/api/toggle-plugin', methods=['POST'])
@admin_required
def toggle_plugin():
    """Toggle plugin on/off"""
    data = request.get_json()
    plugin_name = data.get('plugin_name')
    enable = data.get('enable', False)
    
    if not plugin_name:
        return jsonify({'success': False, 'message': 'Plugin name required'}), 400
    
    # Read current config
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Update PLUGINS_ENABLED
    if 'PLUGINS_ENABLED' not in config:
        config['PLUGINS_ENABLED'] = []
    
    if enable:
        if plugin_name not in config['PLUGINS_ENABLED']:
            config['PLUGINS_ENABLED'].append(plugin_name)
    else:
        if plugin_name in config['PLUGINS_ENABLED']:
            config['PLUGINS_ENABLED'].remove(plugin_name)
    
    # Save config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    return jsonify({
        'success': True, 
        'message': f"Plugin '{plugin_name}' {'enabled' if enable else 'disabled'}. Please restart the server to apply changes.",
        'requires_restart': True
    })

@bp.route('/api/update-config', methods=['POST'])
@admin_required
def update_config():
    """Update main configuration"""
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    
    if not key:
        return jsonify({'success': False, 'message': 'Config key required'}), 400
    
    # Read current config
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Update value
    config[key] = value
    
    # Save config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    return jsonify({
        'success': True,
        'message': f"Updated {key}. Restart server to apply changes.",
        'requires_restart': True
    })

@bp.route('/api/save-plugin-config', methods=['POST'])
@admin_required
def save_plugin_config():
    """Save plugin configuration"""
    data = request.get_json()
    plugin_name = data.get('plugin_name')
    config_content = data.get('config_content')
    
    if not plugin_name or config_content is None:
        return jsonify({'success': False, 'message': 'Plugin name and config content required'}), 400
    
    # Validate JSON
    try:
        json.loads(config_content)
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'message': f'Invalid JSON: {str(e)}'}), 400
    
    # Save config
    plugin_dir = os.path.join(os.path.dirname(__file__), '..', plugin_name)
    config_path = os.path.join(plugin_dir, 'config.json')
    
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        return jsonify({
            'success': True,
            'message': f"Configuration for '{plugin_name}' saved successfully. Restart server to apply changes.",
            'requires_restart': True
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saving config: {str(e)}'}), 500

@bp.route('/api/save-env', methods=['POST'])
@admin_required
def save_env():
    """Save .env file"""
    data = request.get_json()
    env_content = data.get('env_content')
    
    if env_content is None:
        return jsonify({'success': False, 'message': 'Environment content required'}), 400
    
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        return jsonify({
            'success': True,
            'message': 'Environment variables saved successfully. Restart server to apply changes.',
            'requires_restart': True
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saving .env: {str(e)}'}), 500

@bp.route('/api/get-config')
@admin_required
def get_config():
    """Get current configuration"""
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    return jsonify(config)

@bp.route('/api/restart-server', methods=['POST'])
@admin_required
def restart_server():
    """Trigger server restart"""
    def restart():
        """Restart the Flask application"""
        import time
        time.sleep(1)  # Give time for response to be sent
        
        # For development mode, we can use werkzeug's restart
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            # We're in the reloader process
            os._exit(3)  # Exit code 3 tells werkzeug to restart
        else:
            # Manual restart
            python = sys.executable
            os.execl(python, python, *sys.argv)
    
    # Start restart in background
    import threading
    threading.Thread(target=restart).start()
    
    return jsonify({
        'success': True,
        'message': 'Server is restarting...'
    })

@bp.route('/api/plugin-info/<plugin_name>')
@admin_required
def plugin_info(plugin_name):
    """Get detailed plugin information"""
    plugin_dir = os.path.join(os.path.dirname(__file__), '..', plugin_name)
    
    info = {
        'exists': False,
        'has_config': False,
        'has_models': False,
        'has_routes': False,
        'config': {},
        'plugin_json': {}
    }
    
    if os.path.exists(plugin_dir):
        info['exists'] = True
        
        # Check for config.json
        config_path = os.path.join(plugin_dir, 'config.json')
        if os.path.exists(config_path):
            info['has_config'] = True
            with open(config_path, 'r') as f:
                try:
                    info['config'] = json.load(f)
                except:
                    info['config'] = {'error': 'Invalid JSON'}
        
        # Check for plugin.json
        plugin_json_path = os.path.join(plugin_dir, 'plugin.json')
        if os.path.exists(plugin_json_path):
            with open(plugin_json_path, 'r') as f:
                try:
                    info['plugin_json'] = json.load(f)
                except:
                    info['plugin_json'] = {'error': 'Invalid JSON'}
        
        # Check for models.py
        info['has_models'] = os.path.exists(os.path.join(plugin_dir, 'models.py'))
        
        # Check for routes.py
        info['has_routes'] = os.path.exists(os.path.join(plugin_dir, 'routes.py'))
    
    return jsonify(info)

def register(app):
    """Register blueprint with Flask app"""
    app.register_blueprint(bp)
    print(f"    🔗 Admin plugin routes registered at /admin")