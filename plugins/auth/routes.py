# plugins/auth/routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from core.config_loader import get_plugin_config, get_plugin_info
from core.database import db
from core.plugin_manager import get_merged_model
from sqlalchemy.exc import IntegrityError

bp = Blueprint("auth", __name__, template_folder="templates", static_folder="static", url_prefix="/auth")

@bp.context_processor
def inject_plugin_configs():
    return dict(
        plugin_configs=get_plugin_config,
        plugin_infos=get_plugin_info
    )

def register(app):
    app.register_blueprint(bp)
    print(f"    🔗 Auth plugin routes registered at /auth")