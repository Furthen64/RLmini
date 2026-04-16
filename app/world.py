from app.enums import Tile, Action
from app.models import Position

# Cardinal directions mapped to (row_delta, col_delta)
CARDINAL_OFFSETS: dict[int, tuple[int, int]] = {
    Action.UP:    (-1, 0),
    Action.DOWN:  (1, 0),
    Action.LEFT:  (0, -1),
    Action.RIGHT: (0, 1),
}


def get_sense_offsets(radius: int) -> list[tuple[int, int]]:
    """Return sense offsets for a square neighbourhood of the given radius.

    Offsets are ordered row-major (top-left to bottom-right), skipping (0, 0).
    radius=1 → 8 tiles (3×3 minus centre)
    radius=2 → 24 tiles (5×5 minus centre)
    radius=n → (2n+1)² − 1 tiles
    """
    offsets: list[tuple[int, int]] = []
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            offsets.append((dr, dc))
    return offsets


class World:
    def __init__(self, width: int, height: int, sense_radius: int = 1) -> None:
        self.width = width
        self.height = height
        self.sense_radius = sense_radius
        self.sense_offsets: list[tuple[int, int]] = get_sense_offsets(sense_radius)
        self.grid: list[list[int]] = [
            [Tile.EMPTY] * width for _ in range(height)
        ]
        self._food_count: int = 0
        self._changed_cells: list[tuple[int, int]] = []

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def get_tile(self, row: int, col: int) -> int:
        if not self.in_bounds(row, col):
            return Tile.WALL
        return self.grid[row][col]

    def _sample_tile(self, row: int, col: int) -> int:
        if not self.in_bounds(row, col):
            return Tile.WALL
        return self.grid[row][col]

    def set_tile(self, row: int, col: int, tile: int) -> None:
        if not self.in_bounds(row, col):
            return
        old = self.grid[row][col]
        if old == tile:
            return
        if old == Tile.FOOD:
            self._food_count -= 1
        if tile == Tile.FOOD:
            self._food_count += 1
        self.grid[row][col] = tile
        self._changed_cells.append((row, col))

    def get_sense_vector(self, pos: Position) -> list[int]:
        return [
            self._sample_tile(pos.row + dr, pos.col + dc)
            for dr, dc in self.sense_offsets
        ]

    def get_cardinal_adjacent_food(self, pos: Position) -> list[tuple[int, int]]:
        result = []
        for action, (dr, dc) in CARDINAL_OFFSETS.items():
            nr, nc = pos.row + dr, pos.col + dc
            if self._sample_tile(nr, nc) == Tile.FOOD:
                result.append((nr, nc))
        return result

    def get_visible_food(self, pos: Position) -> list[tuple[int, int]]:
        result = []
        for dr, dc in self.sense_offsets:
            nr, nc = pos.row + dr, pos.col + dc
            if self._sample_tile(nr, nc) == Tile.FOOD:
                result.append((nr, nc))
        return result

    def get_legal_moves(self, pos: Position) -> list[int]:
        legal = []
        for action, (dr, dc) in CARDINAL_OFFSETS.items():
            nr, nc = pos.row + dr, pos.col + dc
            tile = self._sample_tile(nr, nc)
            if tile in (Tile.EMPTY, Tile.FOOD):
                legal.append(int(action))
        return legal

    def move_pos(self, pos: Position, action: int) -> Position:
        if action == Action.IDLE:
            return Position(pos.row, pos.col)
        dr, dc = CARDINAL_OFFSETS.get(action, (0, 0))
        return Position(pos.row + dr, pos.col + dc)

    def count_food(self) -> int:
        return self._food_count

    def take_changed_cells(self) -> list[tuple[int, int]]:
        changes = self._changed_cells
        self._changed_cells = []
        return changes
