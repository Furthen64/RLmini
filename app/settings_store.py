import json
import logging
import os
from pathlib import Path
from typing import Any

from app.config import SETTINGS_VERSION, DEFAULT_RNG_SEED
from app.models import (
    EXPLORE_HISTORY_WINDOW_DEFAULT,
    EXPLORE_NEW_TILE_BONUS_DEFAULT,
    EXPLORE_LOW_VISIT_FACTOR_DEFAULT,
    EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT,
    EXPLORE_REVERSE_PENALTY_DEFAULT,
)

log = logging.getLogger(__name__)


def _app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "RLmini"


def _settings_path() -> Path:
    return _app_data_dir() / "settings.json"


DEFAULT_SETTINGS: dict[str, Any] = {
    "version": SETTINGS_VERSION,
    "world_width": 20,
    "world_height": 15,
    "creature_count": 5,
    "food_count": 20,
    "epoch_length": 200,
    "tick_interval_ms": 100,
    "match_threshold": 0.75,
    "cell_size": 32,
    "seed": DEFAULT_RNG_SEED,
    "seed_fixed": False,
    "auto_run": False,
    "show_grid_lines": True,
    "show_creature_ids": True,
    "highlight_selected": True,
    "show_pheromone_trail": True,
    "sense_radius": 1,
    "loaded_map_path": None,
    "recent_map_paths": [],
    "main_window_geometry": None,
    "details_window_geometry": None,
    "editor_window_geometry": None,
    "editor_recent_map_path": None,
    # Exploration novelty scoring weights
    "explore_history_window": EXPLORE_HISTORY_WINDOW_DEFAULT,
    "explore_new_tile_bonus": EXPLORE_NEW_TILE_BONUS_DEFAULT,
    "explore_low_visit_factor": EXPLORE_LOW_VISIT_FACTOR_DEFAULT,
    "explore_recent_repeat_penalty": EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT,
    "explore_reverse_penalty": EXPLORE_REVERSE_PENALTY_DEFAULT,
}


def load_settings() -> dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged
    except Exception as e:
        log.warning(f"Failed to load settings: {e}. Using defaults.")
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save settings: {e}")
