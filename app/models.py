from dataclasses import dataclass, field
from typing import Optional

# Explore scoring defaults (also configurable via WorldConfig / settings)
EXPLORE_HISTORY_WINDOW_DEFAULT: int = 15
EXPLORE_NEW_TILE_BONUS_DEFAULT: float = 10.0
EXPLORE_LOW_VISIT_FACTOR_DEFAULT: float = 1.0
EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT: float = 5.0
EXPLORE_REVERSE_PENALTY_DEFAULT: float = 3.0


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
    sense_vector: list[int]  # length = (2*sense_radius+1)^2 - 1
    action: int


@dataclass
class MemorySequence:
    steps: list[MemoryStep]


@dataclass
class Creature:
    id: int
    position: Position
    memories: list[MemorySequence] = field(default_factory=list)
    follow_pheromone_trail: bool = False
    food_score: int = 0
    # runtime state
    mode: int = 2  # CreatureMode.EXPLORE
    last_action: Optional[int] = None
    last_match_score: float = 0.0
    last_replay_fail_reason: str = ""
    recent_steps: list = field(default_factory=list)  # list of (Position, list[int], int)
    active_memory_idx: Optional[int] = None
    active_step_idx: Optional[int] = None
    last_replayed_memory_idx: Optional[int] = None
    current_sense_vector: list[int] = field(default_factory=list)
    current_action: Optional[int] = None
    recovery_steps_remaining: int = 0
    recovery_loop_positions: list[Position] = field(default_factory=list)
    memory_cooldowns: dict[int, int] = field(default_factory=dict)
    memory_loop_strikes: dict[int, int] = field(default_factory=dict)
    reverse_pheromone: dict[tuple[int, int], float] = field(default_factory=dict)
    visible_pheromone: dict[tuple[int, int], float] = field(default_factory=dict)
    # Exploration novelty state (reset each epoch)
    visit_count_by_pos: dict[tuple[int, int], int] = field(default_factory=dict)
    recent_positions: list[tuple[int, int]] = field(default_factory=list)
    # Last explore candidate scores for debug display:
    # list of (action, pos_key, score, new_tile, in_recent, is_reversal)
    last_explore_scores: list[tuple[int, tuple[int, int], float, bool, bool, bool]] = field(default_factory=list)


@dataclass
class WorldConfig:
    width: int = 20
    height: int = 15
    creature_count: int = 5
    food_count: int = 20
    wall_count: int = 10
    epoch_length: int = 200
    tick_interval_ms: int = 100
    match_threshold: float = 0.75
    cell_size: int = 32
    seed: Optional[int] = None
    auto_run: bool = False
    show_grid_lines: bool = True
    show_creature_ids: bool = True
    highlight_selected: bool = True
    sense_radius: int = 1
    pheromone_drop_chance: float = 0.35
    pheromone_follow_chance: float = 0.5
    # Exploration novelty scoring weights
    explore_history_window: int = EXPLORE_HISTORY_WINDOW_DEFAULT
    explore_new_tile_bonus: float = EXPLORE_NEW_TILE_BONUS_DEFAULT
    explore_low_visit_factor: float = EXPLORE_LOW_VISIT_FACTOR_DEFAULT
    explore_recent_repeat_penalty: float = EXPLORE_RECENT_REPEAT_PENALTY_DEFAULT
    explore_reverse_penalty: float = EXPLORE_REVERSE_PENALTY_DEFAULT


@dataclass
class TickSnapshot:
    tick: int
    food_remaining: int
    best_score: int
    avg_score: float


@dataclass
class SimulationStats:
    tick: int = 0
    epoch: int = 0
    food_remaining: int = 0
    food_consumed: int = 0
    creature_count: int = 0
    best_creature_score: int = 0
    avg_creature_score: float = 0.0
