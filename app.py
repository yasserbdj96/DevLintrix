# app.py
from flask import Flask, render_template
from core.config_loader import main_config
from core.settings_loader import settings
from core.plugin_manager import load_plugins
from core.database import db, init_db
import os

app = Flask(__name__)

# Flask configuration
app.config.update(settings)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = settings.get('DATABASE_URI', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize database
init_db(app)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    app.logger.error(f"Unhandled exception: {error}")
    db.session.rollback()
    if app.config.get('DEBUG'):
        raise error
    return render_template('errors/500.html'), 500

# Context processor for global template variables
@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    from core.plugin_manager import plugin_manager
    return dict(
        app_name=main_config.get('APP_NAME', 'My Application'),
        app_version=main_config.get('VERSION', '1.0.0'),
        loaded_plugins=plugin_manager.get_loaded_plugins(),
        is_plugin_loaded=plugin_manager.is_plugin_loaded,
        plugin_manager=plugin_manager
    )

# Load plugins after database initialization
with app.app_context():
    load_plugins(app, settings.get("PLUGINS_ENABLED", []))

if __name__ == "__main__":
    port = settings.get("PORT", 5000)
    host = settings.get("HOST", "0.0.0.0")
    
    print(f"\n{'='*60}")
    print(f"🚀 Server starting on http://{host}:{port}")
    print(f"📊 Admin panel: http://localhost:{port}/admin")
    print(f"🔐 Default admin password: admin123")
    print(f"{'='*60}\n")
    
    app.run(host=host, port=port, debug=settings["DEBUG"])