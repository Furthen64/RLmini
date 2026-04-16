import random
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QScrollArea, QStatusBar, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QByteArray
from PySide6.QtGui import QCloseEvent

from app.models import WorldConfig, Creature
from app.simulation import Simulation
from app.reproduction import reproduce
from app.settings_store import load_settings, save_settings
from app.ui.grid_widget import GridWidget
from app.ui.details_window import DetailsWindow
from app.ui.settings_panel import SettingsPanel
from app.ui.controls_panel import ControlsPanel
from app.ui.stats_graph import StatsGraph


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RLmini – 2D Grid World")
        self.settings: dict = load_settings()
        self.simulation: Optional[Simulation] = None
        self.selected_creature: Optional[Creature] = None
        self._running = False
        self._tick_count_this_epoch = 0
        self._last_status_text = ""

        self._build_ui()
        self._apply_settings_to_ui()
        self._init_simulation()
        self._restore_geometry()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_tick)

        if self.settings.get("auto_run", False):
            self._start()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left: controls + scrollable grid
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.controls = ControlsPanel()
        self.controls.start_requested.connect(self._start)
        self.controls.pause_requested.connect(self._pause)
        self.controls.step_requested.connect(self._step)
        self.controls.reset_epoch_requested.connect(self._reset_epoch)
        self.controls.reset_sim_requested.connect(self._reset_sim)
        left_layout.addWidget(self.controls)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.grid_widget = GridWidget()
        self.grid_widget.creature_selected.connect(self._on_creature_selected)
        self.scroll.setWidget(self.grid_widget)
        left_layout.addWidget(self.scroll, 1)

        # Stats graph below the grid
        self.stats_graph = StatsGraph()
        left_layout.addWidget(self.stats_graph, 0)

        # Right: settings panel
        self.settings_panel = SettingsPanel()
        self.settings_panel.save_requested.connect(self._save_settings)
        self.settings_panel.reload_requested.connect(self._reload_settings)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.settings_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        # Status bar
        self.status_label = QLabel("Ready")
        status_bar = QStatusBar()
        status_bar.addPermanentWidget(self.status_label)
        self.setStatusBar(status_bar)

        # Separate details window
        self.details_window = DetailsWindow()
        self.details_window.show()

        self.resize(1050, 720)

    # --------------------------------------------------------------- settings

    def _apply_settings_to_ui(self) -> None:
        self.settings_panel.apply_settings(self.settings)

    def _save_settings(self) -> None:
        new_s = self.settings_panel.get_settings()
        self.settings.update(new_s)
        geom = self.saveGeometry()
        self.settings["main_window_geometry"] = geom.toBase64().data().decode()
        dgeom = self.details_window.saveGeometry()
        self.settings["details_window_geometry"] = dgeom.toBase64().data().decode()
        save_settings(self.settings)

    def _reload_settings(self) -> None:
        self.settings = load_settings()
        self._apply_settings_to_ui()
        self.grid_widget.apply_settings(self.settings)
        if self._running:
            self.timer.setInterval(self.settings.get("tick_interval_ms", 100))

    def _restore_geometry(self) -> None:
        try:
            geom_str = self.settings.get("main_window_geometry")
            if geom_str:
                self.restoreGeometry(QByteArray.fromBase64(geom_str.encode()))
            dgeom_str = self.settings.get("details_window_geometry")
            if dgeom_str:
                self.details_window.restoreGeometry(
                    QByteArray.fromBase64(dgeom_str.encode())
                )
        except Exception:
            pass  # Fall back safely

    # ------------------------------------------------------------ simulation

    def _init_simulation(self) -> None:
        s = self.settings
        w = s.get("world_width", 20)
        h = s.get("world_height", 15)
        interior = (w - 2) * (h - 2)
        creature_n = s.get("creature_count", 5)
        food_n = s.get("food_count", 20)
        wall_n = s.get("wall_count", 10)
        total = creature_n + food_n + wall_n
        if total > interior:
            QMessageBox.warning(
                self,
                "Invalid settings",
                f"creatures ({creature_n}) + food ({food_n}) + walls ({wall_n}) "
                f"= {total} exceeds interior cells ({interior}).\n"
                f"Reduce counts or increase grid size.",
            )
            return
        config = WorldConfig(
            width=w,
            height=h,
            creature_count=creature_n,
            food_count=food_n,
            wall_count=wall_n,
            epoch_length=s.get("epoch_length", 200),
            tick_interval_ms=s.get("tick_interval_ms", 100),
            match_threshold=s.get("match_threshold", 0.75),
            cell_size=s.get("cell_size", 32),
            sense_radius=s.get("sense_radius", 1),
        )
        if s.get("seed_fixed"):
            seed: Optional[int] = s.get("seed")
        else:
            seed = random.randint(0, 999_999)
        self.simulation = Simulation(config, rng_seed=seed)
        self.grid_widget.apply_settings(self.settings)
        self.grid_widget.set_world(self.simulation.world, self.simulation.creatures)
        self.selected_creature = None
        self.details_window.update_creature(None)
        self.stats_graph.clear()
        self._tick_count_this_epoch = 0
        self._update_status()

    # --------------------------------------------------------------- controls

    def _start(self) -> None:
        if self.simulation is None:
            return
        self._running = True
        self.timer.start(self.settings.get("tick_interval_ms", 100))

    def _pause(self) -> None:
        self._running = False
        self.timer.stop()

    def _step(self) -> None:
        if self.simulation is None:
            return
        self._do_tick()

    def _auto_tick(self) -> None:
        if self.simulation is None:
            return
        self._do_tick()

    def _do_tick(self) -> None:
        if self.simulation is None:
            return
        self.simulation.tick()
        self._tick_count_this_epoch += 1
        epoch_len = self.settings.get("epoch_length", 200)
        if self._tick_count_this_epoch >= epoch_len:
            self._auto_epoch_end()
        else:
            self._update_ui()
            # Use dirty-rect refresh with changed cells from the world
            changed = self.simulation.world.take_changed_cells()
            self.grid_widget.refresh_dirty(changed)

    def _auto_epoch_end(self) -> None:
        if self.simulation is None:
            return
        s = self.settings
        target_count = s.get("creature_count", 5)
        seed: Optional[int] = s.get("seed") if s.get("seed_fixed") else None
        rng = random.Random(seed)
        offspring = reproduce(
            self.simulation.creatures,
            target_count,
            self.simulation._next_creature_id,
            rng,
        )
        self.simulation._next_creature_id += len(offspring)
        self.simulation.epoch_reset(offspring)
        self._tick_count_this_epoch = 0
        self.selected_creature = None
        self.grid_widget.selected_creature = None
        self.details_window.update_creature(None)
        self.simulation.world.take_changed_cells()  # drain
        self._update_ui()
        self.grid_widget.refresh()

    def _reset_epoch(self) -> None:
        if self.simulation is None:
            return
        self.simulation.epoch_reset()
        self._tick_count_this_epoch = 0
        self.selected_creature = None
        self.grid_widget.selected_creature = None
        self.details_window.update_creature(None)
        self.simulation.world.take_changed_cells()  # drain
        self._update_ui()
        self.grid_widget.refresh()

    def _reset_sim(self) -> None:
        was_running = self._running
        self._pause()
        self._init_simulation()
        if was_running:
            self._start()

    # -------------------------------------------------------------- UI update

    def _on_creature_selected(self, creature: Optional[Creature]) -> None:
        self.selected_creature = creature
        self.details_window.update_creature(creature)
        self.details_window.show()
        self.details_window.raise_()

    def _update_ui(self) -> None:
        if self.simulation is None:
            return
        # Keep reference to selected creature current
        if self.selected_creature is not None:
            found = next(
                (c for c in self.simulation.creatures if c.id == self.selected_creature.id),
                None,
            )
            self.selected_creature = found
            self.grid_widget.selected_creature = found
            self.details_window.update_creature(found)

        self.grid_widget.creatures = self.simulation.creatures
        self.stats_graph.update_data(self.simulation.history)
        self._update_status()

    def _update_status(self) -> None:
        if self.simulation is None:
            self.status_label.setText("No simulation")
            return
        stats = self.simulation.stats
        sel = (
            f"  |  Selected: #{self.selected_creature.id}"
            if self.selected_creature
            else ""
        )
        text = (
            f"Tick: {stats.tick}  |  Epoch: {stats.epoch}  |  "
            f"Creatures: {stats.creature_count}  |  "
            f"Food remaining: {stats.food_remaining}  |  "
            f"Food consumed: {stats.food_consumed}  |  "
            f"Best: {stats.best_creature_score}  |  "
            f"Avg: {stats.avg_creature_score:.1f}{sel}"
        )
        if text != self._last_status_text:
            self._last_status_text = text
            self.status_label.setText(text)

    # ----------------------------------------------------------------- close

    def closeEvent(self, event: QCloseEvent) -> None:
        self._pause()
        self.details_window.close()
        event.accept()
