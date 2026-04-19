import pyqtgraph as pg
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from app.models import TickSnapshot

# Match the dark grid background
pg.setConfigOptions(antialias=True)

FOOD_COLOR = (100, 220, 80)
BEST_SCORE_COLOR = (255, 180, 50)
AVG_SCORE_COLOR = (80, 160, 240)
MARKER_COLOR = (255, 110, 110)
BEST_TIME_MARKER_COLOR = (70, 210, 110)


class StatsGraph(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._epoch_length = 200
        self._tick_interval_ms = 100
        self._best_time_tooltip = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setFixedHeight(190)
        self.plot_widget.setBackground((30, 30, 35))
        self.plot_widget.showGrid(x=False, y=True, alpha=0.15)
        self.plot_widget.setLabel("bottom", "Tick")
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()
        self.plot_widget.setMenuEnabled(False)
        self.plot_widget.setLimits(xMin=0, xMax=self._epoch_length)
        self.plot_widget.setXRange(0, self._epoch_length, padding=0)
        self.plot_widget.enableAutoRange(axis="x", enable=False)

        legend = self.plot_widget.addLegend(
            offset=(10, 10),
            labelTextColor=(200, 200, 200),
            labelTextSize="9pt",
        )
        legend.setParentItem(self.plot_widget.getPlotItem())

        self.food_curve = self.plot_widget.plot(
            [], [], pen=pg.mkPen(color=FOOD_COLOR, width=2), name="Food left",
        )
        self.best_curve = self.plot_widget.plot(
            [], [], pen=pg.mkPen(color=BEST_SCORE_COLOR, width=2), name="Best score",
        )
        self.avg_curve = self.plot_widget.plot(
            [], [], pen=pg.mkPen(color=AVG_SCORE_COLOR, width=2, style=Qt.PenStyle.DashLine),
            name="Avg score",
        )
        self.food_empty_markers = pg.ScatterPlotItem(
            [],
            [],
            pen=pg.mkPen(color=MARKER_COLOR, width=1),
            brush=pg.mkBrush(MARKER_COLOR),
            size=9,
            symbol="o",
        )
        self.best_time_marker = pg.ScatterPlotItem(
            [],
            [],
            pen=pg.mkPen(color=BEST_TIME_MARKER_COLOR, width=1),
            brush=pg.mkBrush(BEST_TIME_MARKER_COLOR),
            size=10,
            symbol="t",
            hoverable=True,
            tip=self._best_time_marker_tip,
        )
        self.plot_widget.addItem(self.food_empty_markers)
        self.plot_widget.addItem(self.best_time_marker)

        layout.addWidget(self.plot_widget)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(8, 0, 8, 4)
        controls_layout.setSpacing(12)
        controls_layout.addWidget(QLabel("Graph lines:"))

        self.cb_food = QCheckBox("Food left")
        self.cb_best = QCheckBox("Best score")
        self.cb_avg = QCheckBox("Avg score")
        self.cb_markers = QCheckBox("Show markers")

        for checkbox in (self.cb_food, self.cb_best, self.cb_avg, self.cb_markers):
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._update_curve_visibility)
            controls_layout.addWidget(checkbox)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self.info_label = QLabel("")
        self.info_label.setContentsMargins(8, 0, 8, 4)
        self.info_label.setStyleSheet("color: rgb(205, 205, 210);")
        layout.addWidget(self.info_label)

        self._update_curve_visibility()

    def apply_settings(self, settings: dict) -> None:
        self.set_epoch_length(int(settings.get("epoch_length", 200)))
        self.set_tick_interval_ms(int(settings.get("tick_interval_ms", 100)))
        self.cb_food.setChecked(bool(settings.get("graph_show_food_left", True)))
        self.cb_best.setChecked(bool(settings.get("graph_show_best_score", True)))
        self.cb_avg.setChecked(bool(settings.get("graph_show_avg_score", True)))
        self.cb_markers.setChecked(bool(settings.get("graph_show_markers", True)))

    def get_settings(self) -> dict:
        return {
            "graph_show_food_left": self.cb_food.isChecked(),
            "graph_show_best_score": self.cb_best.isChecked(),
            "graph_show_avg_score": self.cb_avg.isChecked(),
            "graph_show_markers": self.cb_markers.isChecked(),
        }

    def set_epoch_length(self, epoch_length: int) -> None:
        self._epoch_length = max(1, epoch_length)
        self.plot_widget.setLimits(xMin=0, xMax=self._epoch_length)
        self.plot_widget.setXRange(0, self._epoch_length, padding=0)

    def set_tick_interval_ms(self, tick_interval_ms: int) -> None:
        self._tick_interval_ms = max(1, tick_interval_ms)

    def set_best_time_marker(
        self,
        best_time_ticks: int | None,
        best_time_seconds: float | None = None,
        achieved_at: str = "",
    ) -> None:
        if best_time_ticks is None or best_time_seconds is None:
            self._best_time_tooltip = ""
            self.best_time_marker.setData([], [])
            return

        self._best_time_tooltip = (
            f"Best time: {best_time_seconds:.1f} seconds\n"
            f"Date of highscore: {achieved_at}"
        )
        self.best_time_marker.setData([best_time_ticks], [0])

    def _best_time_marker_tip(self, x: float, y: float, data: object) -> str:
        return self._best_time_tooltip

    def _update_curve_visibility(self) -> None:
        self.food_curve.setVisible(self.cb_food.isChecked())
        self.best_curve.setVisible(self.cb_best.isChecked())
        self.avg_curve.setVisible(self.cb_avg.isChecked())
        self.food_empty_markers.setVisible(
            self.cb_food.isChecked() and self.cb_markers.isChecked()
        )

    def update_data(
        self,
        history: list[TickSnapshot],
        initial_snapshot: TickSnapshot | None = None,
    ) -> None:
        ticks: list[int] = []
        food_values: list[float] = []
        best_values: list[float] = []
        avg_values: list[float] = []

        if initial_snapshot is not None:
            ticks.append(0)
            food_values.append(initial_snapshot.food_remaining)
            best_values.append(initial_snapshot.best_score)
            avg_values.append(initial_snapshot.avg_score)

        if history:
            ticks.extend(s.tick for s in history)
            food_values.extend(s.food_remaining for s in history)
            best_values.extend(s.best_score for s in history)
            avg_values.extend(s.avg_score for s in history)

        depletion_tick: int | None = None
        if initial_snapshot is not None and initial_snapshot.food_remaining == 0:
            depletion_tick = 0
        else:
            for snapshot in history:
                if snapshot.food_remaining == 0:
                    depletion_tick = snapshot.tick
                    break

        self.food_curve.setData(ticks, food_values)
        self.best_curve.setData(ticks, best_values)
        self.avg_curve.setData(ticks, avg_values)
        if depletion_tick is None:
            self.food_empty_markers.setData([], [])
            self.info_label.setText("")
        else:
            self.food_empty_markers.setData([depletion_tick], [0])
            elapsed_seconds = (depletion_tick * self._tick_interval_ms) / 1000.0
            self.info_label.setText(
                f"All food eaten after {elapsed_seconds:.1f} seconds"
            )
        self.plot_widget.setXRange(0, self._epoch_length, padding=0)
        self._update_curve_visibility()

    def clear(self) -> None:
        self.food_curve.setData([], [])
        self.best_curve.setData([], [])
        self.avg_curve.setData([], [])
        self.food_empty_markers.setData([], [])
        self.best_time_marker.setData([], [])
        self.info_label.setText("")
        self.plot_widget.setXRange(0, self._epoch_length, padding=0)
