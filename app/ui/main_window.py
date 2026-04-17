import random
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMenu, QSplitter, QScrollArea, QStatusBar, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QByteArray
from PySide6.QtGui import QAction, QCloseEvent

from app.map_format import (
    MAP_EMPTY,
    MAP_FOOD,
    MAP_WALL,
    MapDocument,
    load_map_document,
    map_document_from_world,
)
from app.models import WorldConfig, Creature
from app.simulation import Simulation
from app.reproduction import reproduce
from app.settings_store import load_settings, save_settings
from app.ui.grid_widget import GridWidget
from app.ui.details_window import DetailsWindow
from app.ui.map_editor_window import MapEditorWindow
from app.ui.settings_panel import SettingsPanel
from app.ui.controls_panel import ControlsPanel
from app.ui.stats_graph import StatsGraph


class MainWindow(QMainWindow):
    MAX_RECENT_MAPS = 8

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RLmini – 2D Grid World")
        self.settings: dict = load_settings()
        self.simulation: Optional[Simulation] = None
        self.loaded_map: Optional[MapDocument] = None
        self.map_editor_window: Optional[MapEditorWindow] = None
        self.selected_creature: Optional[Creature] = None
        self._running = False
        self._tick_count_this_epoch = 0
        self._last_status_text = ""

        self._build_ui()
        self._apply_settings_to_ui()
        self._restore_loaded_map()
        self._init_simulation()
        self._restore_geometry()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_tick)

        if self.settings.get("auto_run", False):
            self._start()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        self._build_menu()
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

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        load_map_action = QAction("Load Map...", self)
        load_map_action.triggered.connect(self._choose_and_load_map)
        file_menu.addAction(load_map_action)

        self.recent_maps_menu = QMenu("Recent Maps", self)
        file_menu.addMenu(self.recent_maps_menu)
        self._refresh_recent_maps_menu()

        clear_map_action = QAction("Clear Loaded Map", self)
        clear_map_action.triggered.connect(self._clear_loaded_map)
        file_menu.addAction(clear_map_action)

        open_editor_action = QAction("Open Map Editor", self)
        open_editor_action.triggered.connect(self._open_map_editor)
        file_menu.addAction(open_editor_action)

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

    def _restore_loaded_map(self) -> None:
        path = self.settings.get("loaded_map_path")
        if not path:
            return
        try:
            self.loaded_map = load_map_document(path)
            self._remember_recent_map(path, persist=False)
            self.settings["world_width"] = self.loaded_map.width
            self.settings["world_height"] = self.loaded_map.height
            self.settings["food_count"] = self.loaded_map.count_tile(MAP_FOOD)
            self.settings["wall_count"] = self.loaded_map.count_tile(MAP_WALL)
            if self.loaded_map.spawn_positions:
                self.settings["creature_count"] = len(self.loaded_map.spawn_positions)
            self._apply_settings_to_ui()
        except Exception:
            self.loaded_map = None
            self.settings["loaded_map_path"] = None

    # ------------------------------------------------------------ simulation

    def _init_simulation(self) -> None:
        s = self.settings
        if self.loaded_map is not None:
            w = self.loaded_map.width
            h = self.loaded_map.height
            food_n = self.loaded_map.count_tile(MAP_FOOD)
            wall_n = self.loaded_map.count_tile(MAP_WALL)
            creature_n = len(self.loaded_map.spawn_positions) or s.get("creature_count", 5)
            available_cells = sum(
                cell == MAP_EMPTY
                for row in self.loaded_map.terrain
                for cell in row
            )
            if creature_n > available_cells:
                QMessageBox.warning(
                    self,
                    "Invalid map",
                    f"Loaded map only has {available_cells} empty cells for "
                    f"{creature_n} creatures.",
                )
                return
        else:
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
        self.simulation = Simulation(config, rng_seed=seed, authored_map=self.loaded_map)
        self.grid_widget.apply_settings(self.settings)
        self.grid_widget.set_world(
            self.simulation.world,
            self.simulation.creatures,
            self.simulation.pheromone_trail,
        )
        self.selected_creature = None
        self.details_window.update_creature(None)
        self.stats_graph.clear()
        self._tick_count_this_epoch = 0
        self._update_status()

    def _choose_and_load_map(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Map",
            self._default_map_dialog_path(),
            "RLmini Maps (*.map *.txt);;All Files (*)",
        )
        if path:
            self._load_map_path(path)

    def _load_map_path(self, path: str) -> None:
        try:
            doc = load_map_document(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to load map", str(exc))
            return

        self.loaded_map = doc
        self.settings["loaded_map_path"] = path
        self._remember_recent_map(path, persist=False)
        self.settings["world_width"] = doc.width
        self.settings["world_height"] = doc.height
        self.settings["food_count"] = doc.count_tile(MAP_FOOD)
        self.settings["wall_count"] = doc.count_tile(MAP_WALL)
        if doc.spawn_positions:
            self.settings["creature_count"] = len(doc.spawn_positions)
        self._apply_settings_to_ui()
        save_settings(self.settings)
        self._reset_sim()

    def _clear_loaded_map(self) -> None:
        self.loaded_map = None
        self.settings["loaded_map_path"] = None
        save_settings(self.settings)
        self._reset_sim()

    def _open_map_editor(self) -> None:
        if self.map_editor_window is None:
            self.map_editor_window = MapEditorWindow(
                initial_document=self._current_map_document(),
                settings=self.settings,
                allow_apply=True,
            )
            self.map_editor_window.map_applied.connect(self._apply_map_document)
        else:
            self.map_editor_window.load_document(self._current_map_document(), mark_clean=True)
        self._pause()
        self.map_editor_window.show()
        self.map_editor_window.raise_()
        self.map_editor_window.activateWindow()

    def _current_map_document(self) -> MapDocument:
        if self.loaded_map is not None:
            return self.loaded_map.copy()
        if self.simulation is None:
            width = self.settings.get("world_width", 20)
            height = self.settings.get("world_height", 15)
            return map_document_from_world(
                width,
                height,
                [[MAP_WALL if r in (0, height - 1) or c in (0, width - 1) else MAP_EMPTY for c in range(width)] for r in range(height)],
                name="current-sim",
            )
        return map_document_from_world(
            self.simulation.world.width,
            self.simulation.world.height,
            self.simulation.world.grid,
            [creature.position for creature in self.simulation.creatures],
            name="current-sim",
        )

    def _apply_map_document(self, doc: MapDocument) -> None:
        self.loaded_map = doc.copy()
        self.settings["loaded_map_path"] = None
        self.settings["world_width"] = doc.width
        self.settings["world_height"] = doc.height
        self.settings["food_count"] = doc.count_tile(MAP_FOOD)
        self.settings["wall_count"] = doc.count_tile(MAP_WALL)
        if doc.spawn_positions:
            self.settings["creature_count"] = len(doc.spawn_positions)
        self._apply_settings_to_ui()
        save_settings(self.settings)
        self._reset_sim()

    def _refresh_recent_maps_menu(self) -> None:
        self.recent_maps_menu.clear()
        recent_paths = self._recent_map_paths()
        if not recent_paths:
            empty_action = QAction("No Recent Maps", self)
            empty_action.setEnabled(False)
            self.recent_maps_menu.addAction(empty_action)
            return

        for path in recent_paths:
            action = QAction(Path(path).name, self)
            action.setStatusTip(path)
            action.triggered.connect(lambda checked=False, map_path=path: self._load_recent_map(map_path))
            self.recent_maps_menu.addAction(action)

        self.recent_maps_menu.addSeparator()
        clear_recent_action = QAction("Clear Recent Maps", self)
        clear_recent_action.triggered.connect(self._clear_recent_maps)
        self.recent_maps_menu.addAction(clear_recent_action)

    def _load_recent_map(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(
                self,
                "Missing map",
                f"The recent map no longer exists:\n{path}",
            )
            self._remove_recent_map(path)
            return
        self._load_map_path(path)

    def _clear_recent_maps(self) -> None:
        self.settings["recent_map_paths"] = []
        save_settings(self.settings)
        self._refresh_recent_maps_menu()

    def _remember_recent_map(self, path: str, *, persist: bool = True) -> None:
        normalized = str(Path(path).expanduser())
        recent_paths = [entry for entry in self._recent_map_paths() if entry != normalized]
        recent_paths.insert(0, normalized)
        self.settings["recent_map_paths"] = recent_paths[: self.MAX_RECENT_MAPS]
        self._refresh_recent_maps_menu()
        if persist:
            save_settings(self.settings)

    def _remove_recent_map(self, path: str) -> None:
        normalized = str(Path(path).expanduser())
        self.settings["recent_map_paths"] = [
            entry for entry in self._recent_map_paths() if entry != normalized
        ]
        save_settings(self.settings)
        self._refresh_recent_maps_menu()

    def _recent_map_paths(self) -> list[str]:
        value = self.settings.get("recent_map_paths", [])
        if not isinstance(value, list):
            return []
        return [str(entry) for entry in value if isinstance(entry, str) and entry]

    def _default_map_dialog_path(self) -> str:
        loaded_map_path = self.settings.get("loaded_map_path")
        if isinstance(loaded_map_path, str) and loaded_map_path:
            return loaded_map_path
        recent_paths = self._recent_map_paths()
        if recent_paths:
            return recent_paths[0]
        return str(Path.cwd())

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
            changed = self.simulation.take_dirty_cells()
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
        self.simulation.take_dirty_cells()  # drain
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
        self.simulation.take_dirty_cells()  # drain
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
        self.grid_widget.pheromone_trail = self.simulation.pheromone_trail
        self.stats_graph.update_data(self.simulation.history)
        self._update_status()

    def _update_status(self) -> None:
        if self.simulation is None:
            self.status_label.setText("No simulation")
            return
        stats = self.simulation.stats
        map_text = ""
        if self.loaded_map is not None:
            map_name = self.loaded_map.metadata.get("name", "loaded map")
            map_text = f"  |  Map: {map_name}"
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
            f"Avg: {stats.avg_creature_score:.1f}{map_text}{sel}"
        )
        if text != self._last_status_text:
            self._last_status_text = text
            self.status_label.setText(text)

    # ----------------------------------------------------------------- close

    def closeEvent(self, event: QCloseEvent) -> None:
        self._pause()
        if self.map_editor_window is not None:
            self.map_editor_window.close()
            if self.map_editor_window.isVisible():
                event.ignore()
                return
        self._save_settings()
        self.details_window.close()
        event.accept()
