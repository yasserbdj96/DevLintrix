# core/settings_loader.py
import json
import os

def load_settings():
    """Load main application settings from config.json in root directory"""
    # Get the project root directory (one level up from core/)
    project_root = os.path.join(os.path.dirname(__file__), "..")
    config_path = os.path.join(project_root, "config.json")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        
        # Ensure PLUGINS_ENABLED exists and is a list
        if "PLUGINS_ENABLED" not in settings:
            settings["PLUGINS_ENABLED"] = []
        elif not isinstance(settings["PLUGINS_ENABLED"], list):
            settings["PLUGINS_ENABLED"] = []
            
        return settings
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Main config.json not found at: {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in: {config_path}")

settings = load_settings()