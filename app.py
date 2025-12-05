# app.py
from flask import Flask
from core.config_loader import main_config
from core.settings_loader import settings
from core.plugin_manager import load_plugins

app = Flask(__name__)
app.config.update(settings)

# Make main config available to all templates
'''@app.context_processor
def inject_main_config():
    """Inject main application configuration into templates"""
    return dict(config=main_config)'''

# Load only enabled plugins
load_plugins(app, settings.get("PLUGINS_ENABLED", []))

if __name__ == "__main__":
    app.run(debug=settings["DEBUG"])