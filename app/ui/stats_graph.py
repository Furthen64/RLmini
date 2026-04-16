import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from app.models import TickSnapshot

# Match the dark grid background
pg.setConfigOptions(antialias=True)

FOOD_COLOR = (100, 220, 80)
BEST_SCORE_COLOR = (255, 180, 50)
AVG_SCORE_COLOR = (80, 160, 240)


class StatsGraph(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(190)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground((30, 30, 35))
        self.plot_widget.showGrid(x=False, y=True, alpha=0.15)
        self.plot_widget.setLabel("bottom", "Tick")
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.hideButtons()

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

        layout.addWidget(self.plot_widget)

    def update_data(self, history: list[TickSnapshot]) -> None:
        if not history:
            self.food_curve.setData([], [])
            self.best_curve.setData([], [])
            self.avg_curve.setData([], [])
            return

        ticks = [s.tick for s in history]
        self.food_curve.setData(ticks, [s.food_remaining for s in history])
        self.best_curve.setData(ticks, [s.best_score for s in history])
        self.avg_curve.setData(ticks, [s.avg_score for s in history])

    def clear(self) -> None:
        self.food_curve.setData([], [])
        self.best_curve.setData([], [])
        self.avg_curve.setData([], [])
