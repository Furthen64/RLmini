from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent, QPaintEvent

from app.enums import Tile
from app.models import Creature

WALL_COLOR = QColor(90, 90, 100)
EMPTY_COLOR = QColor(30, 30, 35)
FOOD_COLOR = QColor(100, 220, 80)
CREATURE_COLOR = QColor(80, 160, 240)
SELECTED_COLOR = QColor(255, 220, 0)
GRID_LINE_COLOR = QColor(60, 60, 70)


class GridWidget(QWidget):
    creature_selected = Signal(object)  # emits Creature or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.world = None
        self.creatures: list[Creature] = []
        self.selected_creature: Creature | None = None
        self.cell_size = 32
        self.show_grid_lines = True
        self.show_creature_ids = True
        self.highlight_selected = True
        self.setMinimumSize(200, 200)

    def set_world(self, world: object, creatures: list[Creature]) -> None:
        self.world = world
        self.creatures = creatures
        self._update_size()
        self.update()

    def refresh(self) -> None:
        self.update()

    def _update_size(self) -> None:
        if self.world is not None:
            w = self.world.width * self.cell_size
            h = self.world.height * self.cell_size
            self.setMinimumSize(w, h)
            self.resize(w, h)

    def apply_settings(self, settings: dict) -> None:
        self.cell_size = settings.get("cell_size", 32)
        self.show_grid_lines = settings.get("show_grid_lines", True)
        self.show_creature_ids = settings.get("show_creature_ids", True)
        self.highlight_selected = settings.get("highlight_selected", True)
        self._update_size()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.world is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cs = self.cell_size

        # Draw background tiles
        for row in range(self.world.height):
            for col in range(self.world.width):
                tile = self.world.get_tile(row, col)
                x, y = col * cs, row * cs

                if tile == Tile.WALL:
                    painter.fillRect(x, y, cs, cs, WALL_COLOR)
                elif tile == Tile.FOOD:
                    painter.fillRect(x, y, cs, cs, EMPTY_COLOR)
                    painter.setBrush(FOOD_COLOR)
                    painter.setPen(Qt.PenStyle.NoPen)
                    margin = max(2, cs // 4)
                    painter.drawEllipse(
                        x + margin, y + margin,
                        cs - 2 * margin, cs - 2 * margin,
                    )
                else:
                    painter.fillRect(x, y, cs, cs, EMPTY_COLOR)

        # Draw creatures
        font = QFont()
        font.setPixelSize(max(8, cs // 3))
        font.setBold(True)
        painter.setFont(font)

        for creature in self.creatures:
            row = creature.position.row
            col = creature.position.col
            x, y = col * cs, row * cs

            is_selected = (
                self.highlight_selected
                and self.selected_creature is not None
                and self.selected_creature.id == creature.id
            )
            color = SELECTED_COLOR if is_selected else CREATURE_COLOR

            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            margin = max(2, cs // 6)
            painter.drawRoundedRect(
                x + margin, y + margin,
                cs - 2 * margin, cs - 2 * margin,
                4, 4,
            )

            if self.show_creature_ids:
                painter.setPen(QColor(10, 10, 10))
                painter.drawText(
                    x, y, cs, cs,
                    int(Qt.AlignmentFlag.AlignCenter),
                    str(creature.id),
                )

        # Grid lines
        if self.show_grid_lines:
            pen = QPen(GRID_LINE_COLOR)
            pen.setWidth(1)
            painter.setPen(pen)
            for row in range(self.world.height + 1):
                painter.drawLine(0, row * cs, self.world.width * cs, row * cs)
            for col in range(self.world.width + 1):
                painter.drawLine(col * cs, 0, col * cs, self.world.height * cs)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.world is None:
            return
        cs = self.cell_size
        col = int(event.position().x()) // cs
        row = int(event.position().y()) // cs

        clicked: Creature | None = None
        for creature in self.creatures:
            if creature.position.row == row and creature.position.col == col:
                clicked = creature
                break

        self.selected_creature = clicked
        self.creature_selected.emit(clicked)
        self.update()
