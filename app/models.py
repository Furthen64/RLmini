from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    row: int
    col: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Position) and self.row == other.row and self.col == other.col

    def __hash__(self) -> int:
        return hash((self.row, self.col))


@dataclass
class MemoryStep:
    sense_vector: list[int]  # length 8
    action: int


@dataclass
class MemorySequence:
    steps: list[MemoryStep]


@dataclass
class Creature:
    id: int
    position: Position
    memories: list[MemorySequence] = field(default_factory=list)
    food_score: int = 0
    # runtime state
    mode: int = 2  # CreatureMode.EXPLORE
    last_action: Optional[int] = None
    last_match_score: float = 0.0
    last_replay_fail_reason: str = ""
    recent_steps: list = field(default_factory=list)  # list of (Position, list[int], int)
    active_memory_idx: Optional[int] = None
    active_step_idx: Optional[int] = None
    current_sense_vector: list[int] = field(default_factory=list)
    current_action: Optional[int] = None


@dataclass
class WorldConfig:
    width: int = 20
    height: int = 15
    creature_count: int = 5
    food_count: int = 20
    epoch_length: int = 200
    tick_interval_ms: int = 100
    match_threshold: float = 0.75
    cell_size: int = 32
    seed: Optional[int] = None
    auto_run: bool = False
    show_grid_lines: bool = True
    show_creature_ids: bool = True
    highlight_selected: bool = True


@dataclass
class SimulationStats:
    tick: int = 0
    epoch: int = 0
    food_remaining: int = 0
    food_consumed: int = 0
    creature_count: int = 0
