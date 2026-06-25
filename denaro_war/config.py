import json
import os
from typing import Dict, Any


def load_config(filename: str = "war_config.json") -> Dict[str, Any]:
    config_path = os.environ.get("DENARO_CONFIG")
    if not config_path:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", filename)
        if not os.path.exists(config_path):
            config_path = "config/" + filename

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load config from {config_path}: {e}")
        return {}


__all__ = ["load_config"]