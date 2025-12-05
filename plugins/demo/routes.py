# plugins/demo/routes.py
from flask import Blueprint, render_template
from core.config_loader import get_plugin_config, get_plugin_info

#bp = Blueprint("demo",__name__,template_folder="views",static_folder="static",url_prefix="/example")
bp = Blueprint("demo",__name__,template_folder="templates",static_folder="static")


# Make plugin configurations available to templates
@bp.context_processor
def inject_plugin_configs():
    """Inject plugin configurations into templates
    
    This makes all loaded plugin configs available as:
    - plugin_configs['demo'] for config.json
    - plugin_infos['demo'] for plugin.json
    
    You can also access specific plugin's config in templates like:
    {{ plugin_configs['demo'].GITHUB_CLIENT_ID }}
    """
    # We'll create these dynamically when needed
    # They will be populated by config_loader after plugins are loaded
    return dict(
        plugin_configs=get_plugin_config,
        plugin_infos=get_plugin_info
    )


@bp.route("/")
def index():
    return render_template("index.html")

def register(app):
    app.register_blueprint(bp)
