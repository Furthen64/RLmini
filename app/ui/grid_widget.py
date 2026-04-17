from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent, QPaintEvent, QRegion

from app.enums import Tile, CreatureMode
from app.models import Creature

WALL_COLOR = QColor(90, 90, 100)
EMPTY_COLOR = QColor(30, 30, 35)
FOOD_COLOR = QColor(100, 220, 80)
CREATURE_COLOR = QColor(80, 160, 240)
MEMORY_COLOR = QColor(160, 80, 230)
SELECTED_COLOR = QColor(255, 220, 0)
GRID_LINE_COLOR = QColor(60, 60, 70)
PHEROMONE_COLOR = QColor(180, 80, 255)
PHEROMONE_MAX_ALPHA = 170


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
        self.show_pheromone_trail = True
        self.pheromone_trail: dict[tuple[int, int], float] = {}
        self._prev_creature_cells: set[tuple[int, int]] = set()
        self.setMinimumSize(200, 200)

    def set_world(
        self,
        world: object,
        creatures: list[Creature],
        pheromone_trail: dict[tuple[int, int], float] | None = None,
    ) -> None:
        self.world = world
        self.creatures = creatures
        self.pheromone_trail = pheromone_trail or {}
        self._update_size()
        self.update()

    def refresh(self) -> None:
        self.update()

    def refresh_dirty(self, changed_cells: list[tuple[int, int]]) -> None:
        """Request repaint only for the given cells plus creature movement."""
        if self.world is None:
            self.update()
            return
        cs = self.cell_size
        total = self.world.width * self.world.height

        # Collect current creature cells
        cur_creature_cells = {(c.position.row, c.position.col) for c in self.creatures}
        # Cells that need repaint: changed tiles + old creature positions + new creature positions
        dirty = set(changed_cells) | self._prev_creature_cells | cur_creature_cells
        self._prev_creature_cells = cur_creature_cells

        if len(dirty) > total // 2:
            self.update()
            return

        region = QRegion()
        for row, col in dirty:
            region += QRegion(QRect(col * cs, row * cs, cs, cs))
        self.update(region)

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
        self.show_pheromone_trail = settings.get("show_pheromone_trail", True)
        self._update_size()
        self.update()

    def _draw_pheromone_overlay(
        self,
        painter: QPainter,
        x: int,
        y: int,
        cell_size: int,
        strength: float,
    ) -> None:
        if not self.show_pheromone_trail or strength <= 0.0:
            return
        painter.fillRect(
            x,
            y,
            cell_size,
            cell_size,
            QColor(
                PHEROMONE_COLOR.red(),
                PHEROMONE_COLOR.green(),
                PHEROMONE_COLOR.blue(),
                min(
                    PHEROMONE_MAX_ALPHA,
                    int(PHEROMONE_MAX_ALPHA * min(1.0, strength / 2.0)),
                ),
            ),
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.world is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cs = self.cell_size
        clip = event.rect()

        # Determine visible cell range from clip rect
        col_min = max(0, clip.left() // cs)
        col_max = min(self.world.width - 1, clip.right() // cs)
        row_min = max(0, clip.top() // cs)
        row_max = min(self.world.height - 1, clip.bottom() // cs)

        # Draw background tiles (only visible cells)
        for row in range(row_min, row_max + 1):
            for col in range(col_min, col_max + 1):
                tile = self.world.get_tile(row, col)
                x, y = col * cs, row * cs
                pheromone_strength = self.pheromone_trail.get((row, col), 0.0)

                if tile == Tile.WALL:
                    painter.fillRect(x, y, cs, cs, WALL_COLOR)
                elif tile == Tile.FOOD:
                    painter.fillRect(x, y, cs, cs, EMPTY_COLOR)
                    self._draw_pheromone_overlay(painter, x, y, cs, pheromone_strength)
                    painter.setBrush(FOOD_COLOR)
                    painter.setPen(Qt.PenStyle.NoPen)
                    margin = max(2, cs // 4)
                    painter.drawEllipse(
                        x + margin, y + margin,
                        cs - 2 * margin, cs - 2 * margin,
                    )
                else:
                    painter.fillRect(x, y, cs, cs, EMPTY_COLOR)
                    self._draw_pheromone_overlay(painter, x, y, cs, pheromone_strength)

        # Draw creatures (only those in clip region)
        font = QFont()
        font.setPixelSize(max(8, cs // 3))
        font.setBold(True)
        painter.setFont(font)

        for creature in self.creatures:
            row = creature.position.row
            col = creature.position.col
            if row < row_min or row > row_max or col < col_min or col > col_max:
                continue
            x, y = col * cs, row * cs

            is_selected = (
                self.highlight_selected
                and self.selected_creature is not None
                and self.selected_creature.id == creature.id
            )
            if is_selected:
                color = SELECTED_COLOR
            elif creature.mode == CreatureMode.MEMORY_REPLAY:
                color = MEMORY_COLOR
            else:
                color = CREATURE_COLOR

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

        # Grid lines (only within clip)
        if self.show_grid_lines:
            pen = QPen(GRID_LINE_COLOR)
            pen.setWidth(1)
            painter.setPen(pen)
            x_left = col_min * cs
            x_right = (col_max + 1) * cs
            y_top = row_min * cs
            y_bottom = (row_max + 1) * cs
            for row in range(row_min, row_max + 2):
                ry = row * cs
                painter.drawLine(x_left, ry, x_right, ry)
            for col in range(col_min, col_max + 2):
                cx = col * cs
                painter.drawLine(cx, y_top, cx, y_bottom)

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
