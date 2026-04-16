from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.map_format import (
    MAP_EMPTY,
    MAP_FOOD,
    MAP_SPAWN,
    MAP_WALL,
    MapDocument,
    create_empty_map,
)
from app.models import Position

EMPTY_COLOR = QColor(30, 30, 35)
WALL_COLOR = QColor(90, 90, 100)
FOOD_COLOR = QColor(100, 220, 80)
SPAWN_COLOR = QColor(245, 160, 60)
GRID_LINE_COLOR = QColor(60, 60, 70)


class MapEditorWidget(QWidget):
    document_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = create_empty_map(20, 15, name="untitled")
        self.cell_size = 32
        self.current_tool = MAP_WALL
        self._painting = False
        self.setMinimumSize(200, 200)
        self._update_size()

    @property
    def document(self) -> MapDocument:
        return self._document

    def set_document(self, doc: MapDocument) -> None:
        self._document = doc.copy()
        self._update_size()
        self.update()

    def set_tool(self, tool: int) -> None:
        self.current_tool = tool

    def resize_document(self, width: int, height: int) -> None:
        resized = create_empty_map(width, height, name=self._document.metadata.get("name"))

        row_limit = min(self._document.height, height)
        col_limit = min(self._document.width, width)
        for row in range(1, max(1, row_limit - 1)):
            for col in range(1, max(1, col_limit - 1)):
                resized.terrain[row][col] = self._document.terrain[row][col]

        resized.spawn_positions = [
            Position(pos.row, pos.col)
            for pos in self._document.spawn_positions
            if 0 < pos.row < height - 1 and 0 < pos.col < width - 1
        ]
        resized.metadata.update(self._document.metadata)
        self.set_document(resized)
        self.document_changed.emit()

    def set_name(self, name: str) -> None:
        clean_name = name.strip()
        if clean_name:
            self._document.metadata["name"] = clean_name
        else:
            self._document.metadata.pop("name", None)
        self.document_changed.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cs = self.cell_size
        clip = event.rect()
        col_min = max(0, clip.left() // cs)
        col_max = min(self._document.width - 1, clip.right() // cs)
        row_min = max(0, clip.top() // cs)
        row_max = min(self._document.height - 1, clip.bottom() // cs)
        spawn_lookup = {(pos.row, pos.col) for pos in self._document.spawn_positions}

        for row in range(row_min, row_max + 1):
            for col in range(col_min, col_max + 1):
                x = col * cs
                y = row * cs
                tile = self._document.terrain[row][col]
                if tile == MAP_WALL:
                    painter.fillRect(x, y, cs, cs, WALL_COLOR)
                else:
                    painter.fillRect(x, y, cs, cs, EMPTY_COLOR)
                    if tile == MAP_FOOD:
                        painter.setBrush(FOOD_COLOR)
                        painter.setPen(Qt.PenStyle.NoPen)
                        margin = max(2, cs // 4)
                        painter.drawEllipse(
                            x + margin,
                            y + margin,
                            cs - 2 * margin,
                            cs - 2 * margin,
                        )

                if (row, col) in spawn_lookup:
                    painter.setBrush(SPAWN_COLOR)
                    painter.setPen(Qt.PenStyle.NoPen)
                    margin = max(3, cs // 5)
                    painter.drawRoundedRect(
                        x + margin,
                        y + margin,
                        cs - 2 * margin,
                        cs - 2 * margin,
                        4,
                        4,
                    )

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
        if event.button() == Qt.MouseButton.LeftButton:
            self._painting = True
            self._apply_event_tool(event, self.current_tool)
        elif event.button() == Qt.MouseButton.RightButton:
            self._apply_event_tool(event, MAP_EMPTY)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._painting and event.buttons() & Qt.MouseButton.LeftButton:
            self._apply_event_tool(event, self.current_tool)
        elif event.buttons() & Qt.MouseButton.RightButton:
            self._apply_event_tool(event, MAP_EMPTY)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._painting = False

    def _apply_event_tool(self, event: QMouseEvent, tool: int) -> None:
        cell = self._cell_from_point(int(event.position().x()), int(event.position().y()))
        if cell is None:
            return
        row, col = cell
        if self._apply_tool(row, col, tool):
            cs = self.cell_size
            self.update(QRect(col * cs, row * cs, cs, cs))
            self.document_changed.emit()

    def _apply_tool(self, row: int, col: int, tool: int) -> bool:
        is_border = row in (0, self._document.height - 1) or col in (0, self._document.width - 1)
        original_tile = self._document.terrain[row][col]
        had_spawn = any(pos.row == row and pos.col == col for pos in self._document.spawn_positions)

        if is_border:
            if original_tile == MAP_WALL and not had_spawn:
                return False
            self._document.terrain[row][col] = MAP_WALL
            self._document.spawn_positions = [
                pos
                for pos in self._document.spawn_positions
                if pos.row != row or pos.col != col
            ]
            return True

        self._document.spawn_positions = [
            pos
            for pos in self._document.spawn_positions
            if pos.row != row or pos.col != col
        ]

        if tool == MAP_SPAWN:
            self._document.terrain[row][col] = MAP_EMPTY
            self._document.spawn_positions.append(Position(row, col))
            return not had_spawn or original_tile != MAP_EMPTY

        self._document.terrain[row][col] = tool
        return original_tile != tool or had_spawn

    def _cell_from_point(self, x: int, y: int) -> tuple[int, int] | None:
        col = x // self.cell_size
        row = y // self.cell_size
        if 0 <= row < self._document.height and 0 <= col < self._document.width:
            return row, col
        return None

    def _update_size(self) -> None:
        width = self._document.width * self.cell_size
        height = self._document.height * self.cell_size
        self.setMinimumSize(width, height)
        self.resize(width, height)