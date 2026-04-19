from PySide6.QtWidgets import (
    QWidget, QFormLayout, QSpinBox, QDoubleSpinBox,
    QCheckBox, QPushButton, QVBoxLayout, QGroupBox, QHBoxLayout,
)
from PySide6.QtCore import Signal

from app.config import DEFAULT_RNG_SEED
from app.models import (
    EXPLORE_HISTORY_WINDOW_DEFAULT,
    EXPLORE_NEW_TILE_BONUS_DEFAULT,
    EXPLORE_LOW_VISIT_FACTOR_DEFAULT,
    EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT,
    EXPLORE_REVERSE_PENALTY_DEFAULT,
)


class SettingsPanel(QWidget):
    save_requested = Signal()
    reload_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        group = QGroupBox("Settings")
        form = QFormLayout(group)

        self.sb_width = QSpinBox()
        self.sb_width.setRange(5, 100)
        self.sb_width.setValue(20)
        form.addRow("Grid Width:", self.sb_width)

        self.sb_height = QSpinBox()
        self.sb_height.setRange(5, 100)
        self.sb_height.setValue(15)
        form.addRow("Grid Height:", self.sb_height)

        self.sb_creatures = QSpinBox()
        self.sb_creatures.setRange(1, 200)
        self.sb_creatures.setValue(5)
        form.addRow("Creature Count:", self.sb_creatures)

        self.sb_food = QSpinBox()
        self.sb_food.setRange(0, 500)
        self.sb_food.setValue(20)
        form.addRow("Food Count:", self.sb_food)

        self.sb_walls = QSpinBox()
        self.sb_walls.setRange(0, 200)
        self.sb_walls.setValue(10)
        form.addRow("Wall Count:", self.sb_walls)

        self.sb_epoch_len = QSpinBox()
        self.sb_epoch_len.setRange(10, 10000)
        self.sb_epoch_len.setValue(200)
        form.addRow("Epoch Length:", self.sb_epoch_len)

        self.sb_tick_ms = QSpinBox()
        self.sb_tick_ms.setRange(10, 5000)
        self.sb_tick_ms.setValue(100)
        form.addRow("Tick Interval (ms):", self.sb_tick_ms)

        self.dsb_threshold = QDoubleSpinBox()
        self.dsb_threshold.setRange(0.0, 1.0)
        self.dsb_threshold.setSingleStep(0.05)
        self.dsb_threshold.setValue(0.75)
        form.addRow("Match Threshold:", self.dsb_threshold)

        self.sb_sense_radius = QSpinBox()
        self.sb_sense_radius.setRange(1, 5)
        self.sb_sense_radius.setValue(1)
        self.sb_sense_radius.setToolTip(
            "Sense radius (shells): 1 = 8 tiles, 2 = 24 tiles, 3 = 48 tiles, …"
        )
        form.addRow("Sense Radius (shells):", self.sb_sense_radius)

        self.sb_cell_size = QSpinBox()
        self.sb_cell_size.setRange(8, 128)
        self.sb_cell_size.setValue(32)
        form.addRow("Cell Size (px):", self.sb_cell_size)

        self.sb_seed = QSpinBox()
        self.sb_seed.setRange(0, 999999)
        self.sb_seed.setValue(42)
        form.addRow("RNG Seed:", self.sb_seed)

        self.cb_fixed_seed = QCheckBox()
        self.cb_fixed_seed.setChecked(False)
        form.addRow("Fixed Seed:", self.cb_fixed_seed)

        self.cb_auto_run = QCheckBox()
        self.cb_auto_run.setChecked(False)
        form.addRow("Auto-run:", self.cb_auto_run)

        self.cb_grid_lines = QCheckBox()
        self.cb_grid_lines.setChecked(True)
        form.addRow("Show Grid Lines:", self.cb_grid_lines)

        self.cb_creature_ids = QCheckBox()
        self.cb_creature_ids.setChecked(True)
        form.addRow("Show Creature IDs:", self.cb_creature_ids)

        self.cb_highlight = QCheckBox()
        self.cb_highlight.setChecked(True)
        form.addRow("Highlight Selected:", self.cb_highlight)

        self.cb_pheromone_trail = QCheckBox()
        self.cb_pheromone_trail.setChecked(True)
        form.addRow("View pheromone trail:", self.cb_pheromone_trail)

        main_layout.addWidget(group)

        # Exploration novelty settings
        explore_group = QGroupBox("Exploration Settings")
        explore_form = QFormLayout(explore_group)

        self.sb_explore_window = QSpinBox()
        self.sb_explore_window.setRange(1, 200)
        self.sb_explore_window.setValue(EXPLORE_HISTORY_WINDOW_DEFAULT)
        self.sb_explore_window.setToolTip(
            "Number of recent positions used for repeat-penalty scoring"
        )
        explore_form.addRow("History Window:", self.sb_explore_window)

        self.dsb_new_tile_bonus = QDoubleSpinBox()
        self.dsb_new_tile_bonus.setRange(0.0, 100.0)
        self.dsb_new_tile_bonus.setSingleStep(1.0)
        self.dsb_new_tile_bonus.setValue(EXPLORE_NEW_TILE_BONUS_DEFAULT)
        self.dsb_new_tile_bonus.setToolTip("Score bonus for visiting a tile not yet seen this epoch")
        explore_form.addRow("New Tile Bonus:", self.dsb_new_tile_bonus)

        self.dsb_low_visit_factor = QDoubleSpinBox()
        self.dsb_low_visit_factor.setRange(0.0, 100.0)
        self.dsb_low_visit_factor.setSingleStep(0.1)
        self.dsb_low_visit_factor.setValue(EXPLORE_LOW_VISIT_FACTOR_DEFAULT)
        self.dsb_low_visit_factor.setToolTip("Factor for 1/(1+visit_count) low-visit bonus")
        explore_form.addRow("Low Visit Factor:", self.dsb_low_visit_factor)

        self.dsb_recent_repeat_penalty = QDoubleSpinBox()
        self.dsb_recent_repeat_penalty.setRange(0.0, 100.0)
        self.dsb_recent_repeat_penalty.setSingleStep(1.0)
        self.dsb_recent_repeat_penalty.setValue(EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT)
        self.dsb_recent_repeat_penalty.setToolTip(
            "Score penalty when candidate tile is in the recent-positions window"
        )
        explore_form.addRow("Recent Repeat Penalty:", self.dsb_recent_repeat_penalty)

        self.dsb_reverse_penalty = QDoubleSpinBox()
        self.dsb_reverse_penalty.setRange(0.0, 100.0)
        self.dsb_reverse_penalty.setSingleStep(0.5)
        self.dsb_reverse_penalty.setValue(EXPLORE_REVERSE_PENALTY_DEFAULT)
        self.dsb_reverse_penalty.setToolTip("Score penalty for immediately reversing the last move")
        explore_form.addRow("Reverse Move Penalty:", self.dsb_reverse_penalty)

        main_layout.addWidget(explore_group)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Settings")
        self.btn_reload = QPushButton("Reload Settings")
        self.btn_save.clicked.connect(self.save_requested)
        self.btn_reload.clicked.connect(self.reload_requested)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_reload)
        main_layout.addLayout(btn_layout)

        main_layout.addStretch()

    def get_settings(self) -> dict:
        return {
            "world_width": self.sb_width.value(),
            "world_height": self.sb_height.value(),
            "creature_count": self.sb_creatures.value(),
            "food_count": self.sb_food.value(),
            "wall_count": self.sb_walls.value(),
            "epoch_length": self.sb_epoch_len.value(),
            "tick_interval_ms": self.sb_tick_ms.value(),
            "match_threshold": self.dsb_threshold.value(),
            "sense_radius": self.sb_sense_radius.value(),
            "cell_size": self.sb_cell_size.value(),
            "seed": self.sb_seed.value(),
            "seed_fixed": self.cb_fixed_seed.isChecked(),
            "auto_run": self.cb_auto_run.isChecked(),
            "show_grid_lines": self.cb_grid_lines.isChecked(),
            "show_creature_ids": self.cb_creature_ids.isChecked(),
            "highlight_selected": self.cb_highlight.isChecked(),
            "show_pheromone_trail": self.cb_pheromone_trail.isChecked(),
            "explore_history_window": self.sb_explore_window.value(),
            "explore_new_tile_bonus": self.dsb_new_tile_bonus.value(),
            "explore_low_visit_factor": self.dsb_low_visit_factor.value(),
            "explore_recent_repeat_penalty": self.dsb_recent_repeat_penalty.value(),
            "explore_reverse_penalty": self.dsb_reverse_penalty.value(),
        }

    def apply_settings(self, settings: dict) -> None:
        self.sb_width.setValue(settings.get("world_width", 20))
        self.sb_height.setValue(settings.get("world_height", 15))
        self.sb_creatures.setValue(settings.get("creature_count", 5))
        self.sb_food.setValue(settings.get("food_count", 20))
        self.sb_walls.setValue(settings.get("wall_count", 10))
        self.sb_epoch_len.setValue(settings.get("epoch_length", 200))
        self.sb_tick_ms.setValue(settings.get("tick_interval_ms", 100))
        self.dsb_threshold.setValue(settings.get("match_threshold", 0.75))
        self.sb_sense_radius.setValue(settings.get("sense_radius", 1))
        self.sb_cell_size.setValue(settings.get("cell_size", 32))
        seed_val = settings.get("seed")
        self.sb_seed.setValue(seed_val if isinstance(seed_val, int) else DEFAULT_RNG_SEED)
        self.cb_fixed_seed.setChecked(bool(settings.get("seed_fixed", False)))
        self.cb_auto_run.setChecked(bool(settings.get("auto_run", False)))
        self.cb_grid_lines.setChecked(bool(settings.get("show_grid_lines", True)))
        self.cb_creature_ids.setChecked(bool(settings.get("show_creature_ids", True)))
        self.cb_highlight.setChecked(bool(settings.get("highlight_selected", True)))
        self.cb_pheromone_trail.setChecked(bool(settings.get("show_pheromone_trail", True)))
        self.sb_explore_window.setValue(
            int(settings.get("explore_history_window", EXPLORE_HISTORY_WINDOW_DEFAULT))
        )
        self.dsb_new_tile_bonus.setValue(
            float(settings.get("explore_new_tile_bonus", EXPLORE_NEW_TILE_BONUS_DEFAULT))
        )
        self.dsb_low_visit_factor.setValue(
            float(settings.get("explore_low_visit_factor", EXPLORE_LOW_VISIT_FACTOR_DEFAULT))
        )
        self.dsb_recent_repeat_penalty.setValue(
            float(settings.get("explore_recent_repeat_penalty", EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT))
        )
        self.dsb_reverse_penalty.setValue(
            float(settings.get("explore_reverse_penalty", EXPLORE_REVERSE_PENALTY_DEFAULT))
        )
