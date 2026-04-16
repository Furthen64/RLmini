from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from app.models import Position

MAP_EMPTY = 0
MAP_WALL = 1
MAP_FOOD = 2
MAP_SPAWN = 3
SUPPORTED_MAP_TOKENS = {MAP_EMPTY, MAP_WALL, MAP_FOOD, MAP_SPAWN}
MAP_VERSION = "1"


@dataclass
class MapDocument:
    width: int
    height: int
    terrain: list[list[int]]
    spawn_positions: list[Position] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def copy(self) -> "MapDocument":
        return MapDocument(
            width=self.width,
            height=self.height,
            terrain=[list(row) for row in self.terrain],
            spawn_positions=[Position(pos.row, pos.col) for pos in self.spawn_positions],
            metadata=dict(self.metadata),
        )

    def count_tile(self, tile: int) -> int:
        return sum(cell == tile for row in self.terrain for cell in row)


def create_empty_map(
    width: int,
    height: int,
    *,
    name: str | None = None,
) -> MapDocument:
    terrain = [[MAP_EMPTY for _ in range(width)] for _ in range(height)]
    doc = MapDocument(width=width, height=height, terrain=terrain)
    if name:
        doc.metadata["name"] = name
    _apply_border_walls(doc)
    return doc


def load_map_document(path: str | Path) -> MapDocument:
    map_path = Path(path)
    doc = parse_map_text(map_path.read_text(encoding="utf-8"))
    if "name" not in doc.metadata:
        doc.metadata["name"] = map_path.stem
    return doc


def save_map_document(doc: MapDocument, path: str | Path) -> None:
    validated = normalize_map_document(doc)
    map_path = Path(path)
    map_path.write_text(serialize_map_text(validated), encoding="utf-8")


def parse_map_text(text: str) -> MapDocument:
    metadata: dict[str, str] = {}
    matrix_lines: list[tuple[int, str]] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") and not matrix_lines:
            key, value = _parse_metadata_line(stripped[1:].strip())
            if key:
                metadata[key] = value
            continue
        compact = "".join(ch for ch in stripped if not ch.isspace())
        if compact:
            matrix_lines.append((line_no, compact))

    if not matrix_lines:
        raise ValueError("Map file does not contain any matrix rows.")

    width = len(matrix_lines[0][1])
    height = len(matrix_lines)
    terrain: list[list[int]] = []
    spawn_positions: list[Position] = []

    for row_index, (line_no, row_text) in enumerate(matrix_lines):
        if len(row_text) != width:
            raise ValueError(
                f"Map rows must all have the same width; line {line_no} has "
                f"length {len(row_text)} instead of {width}."
            )
        terrain_row: list[int] = []
        for col_index, char in enumerate(row_text):
            if not char.isdigit():
                raise ValueError(
                    f"Map rows may only contain digits; found {char!r} "
                    f"on line {line_no}."
                )
            value = int(char)
            if value not in SUPPORTED_MAP_TOKENS:
                raise ValueError(
                    f"Unsupported map token {value} on line {line_no}. "
                    "Supported tokens are 0, 1, 2, and 3."
                )
            if value == MAP_SPAWN:
                spawn_positions.append(Position(row_index, col_index))
                terrain_row.append(MAP_EMPTY)
            else:
                terrain_row.append(value)
        terrain.append(terrain_row)

    return normalize_map_document(
        MapDocument(
            width=width,
            height=height,
            terrain=terrain,
            spawn_positions=spawn_positions,
            metadata=metadata,
        )
    )


def serialize_map_text(doc: MapDocument) -> str:
    normalized = normalize_map_document(doc)
    metadata = dict(normalized.metadata)
    metadata.setdefault("version", MAP_VERSION)

    spawn_lookup = {(pos.row, pos.col) for pos in normalized.spawn_positions}
    lines: list[str] = []
    for key in sorted(metadata):
        value = metadata[key].strip()
        if value:
            lines.append(f"# {key}: {value}")

    if lines:
        lines.append("")

    for row in range(normalized.height):
        chars: list[str] = []
        for col in range(normalized.width):
            if (row, col) in spawn_lookup:
                chars.append(str(MAP_SPAWN))
            else:
                chars.append(str(normalized.terrain[row][col]))
        lines.append("".join(chars))
    lines.append("")
    return "\n".join(lines)


def normalize_map_document(doc: MapDocument) -> MapDocument:
    normalized = doc.copy()
    _validate_rectangular(normalized)
    _validate_tiles(normalized)
    _validate_spawns(normalized)
    _validate_border(normalized)
    return normalized


def map_document_from_world(
    width: int,
    height: int,
    terrain_rows: Sequence[Sequence[int]],
    spawn_positions: Sequence[Position] | None = None,
    *,
    name: str | None = None,
) -> MapDocument:
    terrain = [[MAP_EMPTY for _ in range(width)] for _ in range(height)]
    for row in range(height):
        for col in range(width):
            value = terrain_rows[row][col]
            if value == MAP_WALL:
                terrain[row][col] = MAP_WALL
            elif value == MAP_FOOD:
                terrain[row][col] = MAP_FOOD
            else:
                terrain[row][col] = MAP_EMPTY

    doc = MapDocument(
        width=width,
        height=height,
        terrain=terrain,
        spawn_positions=[Position(pos.row, pos.col) for pos in (spawn_positions or [])],
        metadata={"name": name} if name else {},
    )
    return normalize_map_document(doc)


def generate_maze_map(
    width: int,
    height: int,
    *,
    name: str | None = None,
    rng: random.Random | None = None,
) -> MapDocument:
    maze_rng = rng if rng is not None else random.Random()
    doc = create_empty_map(width, height, name=name)

    for row in range(1, height - 1):
        for col in range(1, width - 1):
            doc.terrain[row][col] = MAP_WALL

    max_row = height - 2
    max_col = width - 2
    start_row = 1
    start_col = 1
    doc.terrain[start_row][start_col] = MAP_EMPTY
    stack: list[tuple[int, int]] = [(start_row, start_col)]
    directions = [(-2, 0), (2, 0), (0, -2), (0, 2)]

    while stack:
        row, col = stack[-1]
        neighbors: list[tuple[int, int, int, int]] = []
        for dr, dc in directions:
            next_row = row + dr
            next_col = col + dc
            if not (1 <= next_row <= max_row and 1 <= next_col <= max_col):
                continue
            if doc.terrain[next_row][next_col] != MAP_WALL:
                continue
            wall_row = row + (dr // 2)
            wall_col = col + (dc // 2)
            neighbors.append((next_row, next_col, wall_row, wall_col))

        if not neighbors:
            stack.pop()
            continue

        next_row, next_col, wall_row, wall_col = maze_rng.choice(neighbors)
        doc.terrain[wall_row][wall_col] = MAP_EMPTY
        doc.terrain[next_row][next_col] = MAP_EMPTY
        stack.append((next_row, next_col))

    doc.spawn_positions = []
    return normalize_map_document(doc)


def _apply_border_walls(doc: MapDocument) -> None:
    if doc.width <= 0 or doc.height <= 0:
        return
    for row in range(doc.height):
        for col in range(doc.width):
            if row in (0, doc.height - 1) or col in (0, doc.width - 1):
                doc.terrain[row][col] = MAP_WALL
    doc.spawn_positions = [
        pos
        for pos in doc.spawn_positions
        if 0 < pos.row < doc.height - 1 and 0 < pos.col < doc.width - 1
    ]


def _validate_rectangular(doc: MapDocument) -> None:
    if doc.height != len(doc.terrain):
        raise ValueError("Map height does not match the number of terrain rows.")
    if doc.height == 0 or doc.width == 0:
        raise ValueError("Map dimensions must be greater than zero.")
    for row in doc.terrain:
        if len(row) != doc.width:
            raise ValueError("Map terrain rows must all match the declared width.")


def _validate_tiles(doc: MapDocument) -> None:
    for row in doc.terrain:
        for tile in row:
            if tile not in (MAP_EMPTY, MAP_WALL, MAP_FOOD):
                raise ValueError(
                    f"Invalid terrain tile {tile}; terrain may only contain 0, 1, or 2."
                )


def _validate_spawns(doc: MapDocument) -> None:
    seen: set[tuple[int, int]] = set()
    for pos in doc.spawn_positions:
        key = (pos.row, pos.col)
        if key in seen:
            raise ValueError("Duplicate spawn markers are not allowed.")
        seen.add(key)
        if not (0 <= pos.row < doc.height and 0 <= pos.col < doc.width):
            raise ValueError("Spawn marker is outside the map bounds.")
        if pos.row in (0, doc.height - 1) or pos.col in (0, doc.width - 1):
            raise ValueError("Spawn markers cannot be placed on the border.")
        if doc.terrain[pos.row][pos.col] != MAP_EMPTY:
            raise ValueError("Spawn markers may only be placed on empty tiles.")


def _validate_border(doc: MapDocument) -> None:
    for row in range(doc.height):
        for col in range(doc.width):
            if row not in (0, doc.height - 1) and col not in (0, doc.width - 1):
                continue
            if doc.terrain[row][col] != MAP_WALL:
                raise ValueError("Map border cells must all be walls.")


def _parse_metadata_line(content: str) -> tuple[str, str]:
    if not content:
        return "", ""
    if ":" not in content:
        return content.strip().lower(), ""
    key, value = content.split(":", 1)
    return key.strip().lower(), value.strip()