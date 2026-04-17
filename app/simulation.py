import random
from typing import Optional

from app.enums import Tile, Action, CreatureMode
from app.map_format import MAP_FOOD, MapDocument
from app.models import Position, Creature, WorldConfig, SimulationStats, TickSnapshot
from app.world import World, CARDINAL_OFFSETS
from app.memory import find_best_memory_match, try_create_memory

MAX_RECENT_STEPS = 6
MAX_LOOP_PATTERN_LEN = 3
RECOVERY_EXPLORE_STEPS = 4
MEMORY_LOOP_COOLDOWN_TICKS = 8
MEMORY_LOOP_DELETE_STRIKES = 3
REVERSE_PHEROMONE_DECAY = 0.82
REVERSE_PHEROMONE_DEPOSIT = 1.0
REVERSE_PHEROMONE_NEIGHBOR_WEIGHT = 0.35
REVERSE_PHEROMONE_DISTANCE2_WEIGHT = 0.12
REVERSE_PHEROMONE_PRUNE_THRESHOLD = 0.05
REVERSE_PHEROMONE_OSCILLATION_PENALTY = 1.75
REVERSE_PHEROMONE_REPEATED_HIT_PENALTY = 0.5
REVERSE_PHEROMONE_STAGNATION_RATIO = 0.6
REVERSE_PHEROMONE_STAGNATION_MULTIPLIER = 1.5
VISIBLE_PHEROMONE_DECAY = 0.9
VISIBLE_PHEROMONE_DEPOSIT = 1.0
VISIBLE_PHEROMONE_PRUNE_THRESHOLD = 0.05
OTHER_PHEROMONE_ATTRACTION_WEIGHT = 0.8


class Simulation:
    def __init__(
        self,
        config: WorldConfig,
        rng_seed: Optional[int] = None,
        authored_map: Optional[MapDocument] = None,
    ) -> None:
        self.config = config
        self.rng = random.Random(rng_seed)
        self.world = World(config.width, config.height, config.sense_radius)
        self.creatures: list[Creature] = []
        self.stats = SimulationStats()
        self.history: list[TickSnapshot] = []
        self.pheromone_trail: dict[tuple[int, int], float] = {}
        self._dirty_pheromone_cells: set[tuple[int, int]] = set()
        self._next_creature_id = 0
        self.authored_map = authored_map.copy() if authored_map is not None else None
        self._initialize()

    def _initialize(self) -> None:
        if self.authored_map is not None:
            self._apply_authored_map()
            self._place_creatures_from_authored_map()
        else:
            self._place_walls()
            self._place_food()
            self._place_creatures()
        self._seed_pheromones()
        self._update_stats()

    def _apply_authored_map(self) -> None:
        if self.authored_map is None:
            return
        for row in range(self.config.height):
            for col in range(self.config.width):
                self.world.set_tile(row, col, self.authored_map.terrain[row][col])

    def _place_creatures_from_authored_map(self) -> None:
        if self.authored_map is None or not self.authored_map.spawn_positions:
            self._place_creatures()
            return

        preferred_positions = list(self.authored_map.spawn_positions)
        for spawn in preferred_positions[: self.config.creature_count]:
            creature = self._create_creature(spawn.row, spawn.col)
            self._next_creature_id += 1
            self.world.set_tile(spawn.row, spawn.col, Tile.CREATURE)
            self.creatures.append(creature)

        remaining = self.config.creature_count - len(self.creatures)
        if remaining > 0:
            empties = self._empty_positions()
            self.rng.shuffle(empties)
            for r, c in empties[:remaining]:
                creature = self._create_creature(r, c)
                self._next_creature_id += 1
                self.world.set_tile(r, c, Tile.CREATURE)
                self.creatures.append(creature)

    def _place_walls(self) -> None:
        # Border walls
        for row in range(self.config.height):
            for col in range(self.config.width):
                if (
                    row == 0
                    or row == self.config.height - 1
                    or col == 0
                    or col == self.config.width - 1
                ):
                    self.world.set_tile(row, col, Tile.WALL)

        # Interior walls (random scatter)
        interior = [
            (r, c)
            for r in range(1, self.config.height - 1)
            for c in range(1, self.config.width - 1)
            if self.world.get_tile(r, c) == Tile.EMPTY
        ]
        self.rng.shuffle(interior)
        for r, c in interior[: self.config.wall_count]:
            self.world.set_tile(r, c, Tile.WALL)

    def _empty_positions(self) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(self.config.height)
            for c in range(self.config.width)
            if self.world.get_tile(r, c) == Tile.EMPTY
        ]

    def _place_food(self) -> None:
        empties = self._empty_positions()
        self.rng.shuffle(empties)
        for r, c in empties[: self.config.food_count]:
            self.world.set_tile(r, c, Tile.FOOD)

    def _place_creatures(self) -> None:
        empties = self._empty_positions()
        self.rng.shuffle(empties)
        for r, c in empties[: self.config.creature_count]:
            creature = self._create_creature(r, c)
            self._next_creature_id += 1
            self.world.set_tile(r, c, Tile.CREATURE)
            self.creatures.append(creature)

    def _create_creature(self, row: int, col: int) -> Creature:
        return Creature(
            id=self._next_creature_id,
            position=Position(row, col),
            follow_pheromone_trail=(
                self.rng.random() < self.config.pheromone_follow_chance
            ),
        )

    def _update_stats(self) -> None:
        self.stats.food_remaining = self.world.count_food()
        self.stats.creature_count = len(self.creatures)
        if self.creatures:
            scores = [c.food_score for c in self.creatures]
            self.stats.best_creature_score = max(scores)
            self.stats.avg_creature_score = sum(scores) / len(scores)
        else:
            self.stats.best_creature_score = 0
            self.stats.avg_creature_score = 0.0

    def tick(self) -> None:
        self._decay_visible_pheromones()
        order = list(self.creatures)
        self.rng.shuffle(order)
        for creature in order:
            self._tick_creature(creature)
        self.stats.tick += 1
        self._update_stats()
        self.history.append(TickSnapshot(
            tick=self.stats.tick,
            food_remaining=self.stats.food_remaining,
            best_score=self.stats.best_creature_score,
            avg_score=self.stats.avg_creature_score,
        ))

    def _tick_creature(self, creature: Creature) -> None:
        self._tick_down_memory_cooldowns(creature)
        self._decay_reverse_pheromone(creature)
        self._decay_visible_pheromone_for_creature(creature)
        pos = creature.position
        sense = self.world.get_sense_vector(pos)
        creature.current_sense_vector = list(sense)

        # 1. Adjacent food override
        adj_food = self.world.get_cardinal_adjacent_food(pos)
        if adj_food:
            target_r, target_c = self.rng.choice(adj_food)
            self.world.set_tile(pos.row, pos.col, Tile.EMPTY)
            self.world.set_tile(target_r, target_c, Tile.CREATURE)
            new_pos = Position(target_r, target_c)
            creature.position = new_pos
            creature.food_score += 1
            self.stats.food_consumed += 1
            creature.mode = CreatureMode.FOOD_DIRECT
            action = self._direction_to(pos, new_pos)
            creature.recent_steps.append((pos, list(sense), action, None))
            if len(creature.recent_steps) > 4:
                creature.recent_steps.pop(0)
            creature.current_action = action
            creature.last_action = action
            # Try to learn
            new_mem = try_create_memory(creature, creature.recent_steps)
            if new_mem is not None:
                creature.memories.append(new_mem)
            creature.recent_steps.clear()
            creature.active_memory_idx = None
            creature.active_step_idx = None
            creature.last_replayed_memory_idx = None
            creature.recovery_steps_remaining = 0
            creature.recovery_loop_positions = []
            self._maybe_record_pheromone(creature)
            return

        # 2. Visible food pursuit (diagonal counts)
        visible_food = self.world.get_visible_food(pos)
        if visible_food:
            target = self.rng.choice(visible_food)
            best_moves = self._moves_toward(pos, target)
            legal = self.world.get_legal_moves(pos)
            toward_legal = [m for m in best_moves if m in legal]
            if toward_legal:
                action = self._choose_action_with_lowest_revisit_penalty(
                    creature,
                    pos,
                    toward_legal,
                )
                creature.mode = CreatureMode.FOOD_DIRECT
                creature.active_memory_idx = None
                creature.active_step_idx = None
                creature.last_replayed_memory_idx = None
                self._execute_move(creature, action, sense, CreatureMode.FOOD_DIRECT)
                return

        if creature.recovery_steps_remaining <= 0:
            loop_steps = self._detect_recent_loop(creature)
            if loop_steps is not None:
                self._enter_loop_recovery(creature, loop_steps)
                self._recovery_explore(creature, sense, pos)
                return

        if creature.recovery_steps_remaining > 0:
            creature.last_replay_fail_reason = "movement loop - recovery explore"
            creature.active_memory_idx = None
            creature.active_step_idx = None
            creature.last_replayed_memory_idx = None
            self._recovery_explore(creature, sense, pos)
            return

        # 3. Memory replay
        cooling_down = {
            mem_idx
            for mem_idx, ticks in creature.memory_cooldowns.items()
            if ticks > 0
        }
        match = find_best_memory_match(
            creature,
            sense,
            self.config.match_threshold,
            excluded_memory_indices=cooling_down,
        )
        if match is not None:
            mem_idx, step_idx, score = match

            # Validate memory indices
            if mem_idx < 0 or mem_idx >= len(creature.memories):
                creature.last_replay_fail_reason = "invalid memory index"
                self._explore(creature, sense, pos)
                return

            mem_seq = creature.memories[mem_idx]
            if step_idx < 0 or step_idx >= len(mem_seq.steps):
                creature.last_replay_fail_reason = "invalid step index"
                self._explore(creature, sense, pos)
                return

            # If the same memory fired last tick, force one explore step to break loops.
            if creature.last_replayed_memory_idx == mem_idx:
                creature.last_replay_fail_reason = "repeated memory — forced explore"
                creature.last_replayed_memory_idx = None
                creature.active_memory_idx = None
                creature.active_step_idx = None
                self._explore(creature, sense, pos)
                return

            action = mem_seq.steps[step_idx].action
            new_pos = self.world.move_pos(pos, action)
            target_tile = self.world.get_tile(new_pos.row, new_pos.col)
            if action != Action.IDLE and target_tile == Tile.WALL:
                creature.last_replay_fail_reason = "blocked by wall"
                creature.last_replayed_memory_idx = None
                creature.active_memory_idx = None
                creature.active_step_idx = None
                self._explore(creature, sense, pos)
                return
            elif action != Action.IDLE and target_tile == Tile.CREATURE:
                creature.last_replay_fail_reason = "blocked by creature"
                creature.last_replayed_memory_idx = None
                creature.active_memory_idx = None
                creature.active_step_idx = None
                self._explore(creature, sense, pos)
                return

            creature.last_match_score = score
            creature.last_replay_fail_reason = ""
            creature.active_memory_idx = mem_idx
            creature.active_step_idx = step_idx
            creature.last_replayed_memory_idx = mem_idx
            self._execute_move(creature, action, sense, CreatureMode.MEMORY_REPLAY)
            return

        # 4. Explore
        creature.active_memory_idx = None
        creature.active_step_idx = None
        creature.last_replayed_memory_idx = None
        self._explore(creature, sense, pos)

    def _tick_down_memory_cooldowns(self, creature: Creature) -> None:
        updated: dict[int, int] = {}
        for mem_idx, ticks in creature.memory_cooldowns.items():
            if ticks > 1:
                updated[mem_idx] = ticks - 1
        creature.memory_cooldowns = updated

    def _seed_pheromones(self) -> None:
        for creature in self.creatures:
            self._maybe_record_pheromone(creature)

    def _decay_reverse_pheromone(self, creature: Creature) -> None:
        updated: dict[tuple[int, int], float] = {}
        for key, strength in creature.reverse_pheromone.items():
            next_strength = strength * REVERSE_PHEROMONE_DECAY
            if next_strength >= REVERSE_PHEROMONE_PRUNE_THRESHOLD:
                updated[key] = next_strength
        creature.reverse_pheromone = updated

    def _record_reverse_pheromone(self, creature: Creature) -> None:
        key = (creature.position.row, creature.position.col)
        creature.reverse_pheromone[key] = (
            creature.reverse_pheromone.get(key, 0.0) + REVERSE_PHEROMONE_DEPOSIT
        )

    def _decay_visible_pheromones(self) -> None:
        if not self.pheromone_trail:
            return
        updated: dict[tuple[int, int], float] = {}
        for key, strength in self.pheromone_trail.items():
            next_strength = strength * VISIBLE_PHEROMONE_DECAY
            self._dirty_pheromone_cells.add(key)
            if next_strength >= VISIBLE_PHEROMONE_PRUNE_THRESHOLD:
                updated[key] = next_strength
        self.pheromone_trail = updated

    def _record_visible_pheromone(self, creature: Creature) -> None:
        key = (creature.position.row, creature.position.col)
        self.pheromone_trail[key] = (
            self.pheromone_trail.get(key, 0.0) + VISIBLE_PHEROMONE_DEPOSIT
        )
        creature.visible_pheromone[key] = (
            creature.visible_pheromone.get(key, 0.0) + VISIBLE_PHEROMONE_DEPOSIT
        )
        self._dirty_pheromone_cells.add(key)

    def _decay_visible_pheromone_for_creature(self, creature: Creature) -> None:
        updated: dict[tuple[int, int], float] = {}
        for key, strength in creature.visible_pheromone.items():
            next_strength = strength * VISIBLE_PHEROMONE_DECAY
            if next_strength >= VISIBLE_PHEROMONE_PRUNE_THRESHOLD:
                updated[key] = next_strength
        creature.visible_pheromone = updated

    def _maybe_record_pheromone(self, creature: Creature) -> None:
        if self.rng.random() < self.config.pheromone_drop_chance:
            self._record_reverse_pheromone(creature)
            self._record_visible_pheromone(creature)

    def _choose_action_with_lowest_revisit_penalty(
        self,
        creature: Creature,
        pos: Position,
        legal: list[int],
    ) -> int:
        if not legal:
            return Action.IDLE

        recent_positions = [step_pos for step_pos, _, _, _ in creature.recent_steps[-MAX_RECENT_STEPS:]]
        trace_positions = recent_positions + [pos]
        best_penalty: Optional[float] = None
        best_actions: list[int] = []
        for action in legal:
            penalty = self._calculate_revisit_penalty_for_action(
                creature,
                pos,
                action,
                recent_positions,
                trace_positions,
            )
            if best_penalty is None or penalty < best_penalty:
                best_penalty = penalty
                best_actions = [action]
            elif penalty == best_penalty:
                best_actions.append(action)
        return self.rng.choice(best_actions)

    def _calculate_revisit_penalty_for_action(
        self,
        creature: Creature,
        pos: Position,
        action: int,
        recent_positions: list[Position],
        trace_positions: list[Position],
    ) -> float:
        candidate = self.world.move_pos(pos, action)
        base_penalty = self._reverse_pheromone_strength(creature, candidate)
        loop_penalty = 0.0

        candidate_key = (candidate.row, candidate.col)

        if recent_positions:
            previous_key = (recent_positions[-1].row, recent_positions[-1].col)
            if candidate_key == previous_key:
                loop_penalty += REVERSE_PHEROMONE_OSCILLATION_PENALTY

        repeated_hits = sum(
            1
            for recent_pos in recent_positions
            if recent_pos.row == candidate.row and recent_pos.col == candidate.col
        )
        if repeated_hits > 0:
            loop_penalty += repeated_hits * REVERSE_PHEROMONE_REPEATED_HIT_PENALTY

        penalty = base_penalty + loop_penalty
        if creature.follow_pheromone_trail:
            penalty -= (
                self._other_pheromone_strength(creature, candidate)
                * OTHER_PHEROMONE_ATTRACTION_WEIGHT
            )
        if self._recent_progress_ratio(trace_positions) < REVERSE_PHEROMONE_STAGNATION_RATIO:
            penalty *= REVERSE_PHEROMONE_STAGNATION_MULTIPLIER

        return penalty

    def _reverse_pheromone_strength(self, creature: Creature, pos: Position) -> float:
        total = 0.0
        for (row, col), strength in creature.reverse_pheromone.items():
            manhattan_distance = abs(pos.row - row) + abs(pos.col - col)
            if manhattan_distance == 0:
                total += strength
            elif manhattan_distance == 1:
                total += strength * REVERSE_PHEROMONE_NEIGHBOR_WEIGHT
            elif manhattan_distance == 2:
                total += strength * REVERSE_PHEROMONE_DISTANCE2_WEIGHT
        return total

    def _other_pheromone_strength(self, creature: Creature, pos: Position) -> float:
        """Return visible pheromone strength on a tile excluding this creature's own trail."""
        key = (pos.row, pos.col)
        visible = self.pheromone_trail.get(key, 0.0)
        own = creature.visible_pheromone.get(key, 0.0)
        return max(0.0, visible - own)

    def _recent_progress_ratio(self, positions: list[Position]) -> float:
        if not positions:
            return 1.0
        unique_positions = {
            (position.row, position.col)
            for position in positions
        }
        return len(unique_positions) / len(positions)

    def _detect_recent_loop(self, creature: Creature) -> Optional[list[tuple[Position, list[int], int, Optional[int]]]]:
        recent = creature.recent_steps[-MAX_RECENT_STEPS:]
        if len(recent) < 2:
            return None

        max_pattern_len = min(MAX_LOOP_PATTERN_LEN, len(recent) // 2)
        for pattern_len in range(max_pattern_len, 0, -1):
            suffix = recent[-(pattern_len * 2):]
            if self._has_repeated_suffix_pattern(suffix, include_action=True):
                return suffix
            if self._has_repeated_suffix_pattern(suffix, include_action=False):
                return suffix

        return None

    def _has_repeated_suffix_pattern(
        self,
        steps: list[tuple[Position, list[int], int, Optional[int]]],
        include_action: bool,
    ) -> bool:
        half = len(steps) // 2
        if half == 0:
            return False

        left = [self._step_signature(step, include_action) for step in steps[:half]]
        right = [self._step_signature(step, include_action) for step in steps[half:]]
        return left == right

    def _step_signature(
        self,
        step: tuple[Position, list[int], int, Optional[int]],
        include_action: bool,
    ) -> tuple[int, ...]:
        pos, _, action, _ = step
        if include_action:
            return (pos.row, pos.col, action)
        return (pos.row, pos.col)

    def _enter_loop_recovery(
        self,
        creature: Creature,
        loop_steps: list[tuple[Position, list[int], int, Optional[int]]],
    ) -> None:
        loop_positions: list[Position] = []
        seen_positions: set[tuple[int, int]] = set()
        implicated_memories: set[int] = set()

        for pos, _, _, mem_idx in loop_steps:
            key = (pos.row, pos.col)
            if key not in seen_positions:
                seen_positions.add(key)
                loop_positions.append(Position(pos.row, pos.col))
            if mem_idx is not None:
                implicated_memories.add(mem_idx)

        current_key = (creature.position.row, creature.position.col)
        if current_key not in seen_positions:
            loop_positions.append(Position(creature.position.row, creature.position.col))

        self._penalize_loop_memories(creature, implicated_memories)
        creature.last_replay_fail_reason = "movement loop - recovery explore"
        creature.recovery_steps_remaining = RECOVERY_EXPLORE_STEPS
        creature.recovery_loop_positions = loop_positions
        creature.active_memory_idx = None
        creature.active_step_idx = None
        creature.last_replayed_memory_idx = None

    def _penalize_loop_memories(self, creature: Creature, memory_indices: set[int]) -> None:
        to_delete: set[int] = set()

        for mem_idx in memory_indices:
            strikes = creature.memory_loop_strikes.get(mem_idx, 0) + 1
            creature.memory_loop_strikes[mem_idx] = strikes
            creature.memory_cooldowns[mem_idx] = max(
                creature.memory_cooldowns.get(mem_idx, 0),
                MEMORY_LOOP_COOLDOWN_TICKS,
            )
            if strikes >= MEMORY_LOOP_DELETE_STRIKES:
                to_delete.add(mem_idx)

        if to_delete:
            self._delete_memories(creature, to_delete)

    def _delete_memories(self, creature: Creature, memory_indices: set[int]) -> None:
        remaining_memories = []
        index_map: dict[int, int] = {}

        for old_idx, memory in enumerate(creature.memories):
            if old_idx in memory_indices:
                continue
            index_map[old_idx] = len(remaining_memories)
            remaining_memories.append(memory)

        creature.memories = remaining_memories
        creature.memory_cooldowns = {
            index_map[old_idx]: ticks
            for old_idx, ticks in creature.memory_cooldowns.items()
            if old_idx in index_map and ticks > 0
        }
        creature.memory_loop_strikes = {
            index_map[old_idx]: strikes
            for old_idx, strikes in creature.memory_loop_strikes.items()
            if old_idx in index_map
        }
        creature.recent_steps = [
            (pos, sense_vector, action, index_map.get(mem_idx))
            for pos, sense_vector, action, mem_idx in creature.recent_steps
        ]

        if creature.active_memory_idx is not None:
            creature.active_memory_idx = index_map.get(creature.active_memory_idx)
        if creature.last_replayed_memory_idx is not None:
            creature.last_replayed_memory_idx = index_map.get(creature.last_replayed_memory_idx)
        if creature.active_memory_idx is None:
            creature.active_step_idx = None

    def _recovery_explore(self, creature: Creature, sense: list[int], pos: Position) -> None:
        legal = self.world.get_legal_moves(pos)
        creature.recovery_steps_remaining = max(0, creature.recovery_steps_remaining - 1)
        if not legal:
            self._execute_move(creature, Action.IDLE, sense, CreatureMode.EXPLORE)
            return

        legal = self._prefer_non_reversal_moves(legal, creature.current_action)

        recent_positions = {
            (step_pos.row, step_pos.col)
            for step_pos, _, _, _ in creature.recent_steps[-MAX_RECENT_STEPS:]
        }
        recent_positions.add((pos.row, pos.col))
        loop_positions = {
            (loop_pos.row, loop_pos.col)
            for loop_pos in creature.recovery_loop_positions
        }
        current_loop_distance = self._min_loop_distance(pos, loop_positions)

        best_score: Optional[tuple[int, int, int]] = None
        best_actions: list[int] = []
        for action in legal:
            new_pos = self.world.move_pos(pos, action)
            new_key = (new_pos.row, new_pos.col)
            loop_distance = self._min_loop_distance(new_pos, loop_positions)
            score = (
                1 if new_key not in recent_positions else 0,
                loop_distance - current_loop_distance,
                loop_distance,
            )
            if best_score is None or score > best_score:
                best_score = score
                best_actions = [action]
            elif score == best_score:
                best_actions.append(action)

        candidate_actions = best_actions if best_actions else legal
        action = self._choose_action_with_lowest_revisit_penalty(
            creature,
            pos,
            candidate_actions,
        )
        self._execute_move(creature, action, sense, CreatureMode.EXPLORE)

        if creature.recovery_steps_remaining == 0:
            creature.recovery_loop_positions = []

    def _prefer_non_reversal_moves(self, legal: list[int], last_action: Optional[int]) -> list[int]:
        reversal: dict[int, int] = {
            Action.LEFT: Action.RIGHT,
            Action.RIGHT: Action.LEFT,
            Action.UP: Action.DOWN,
            Action.DOWN: Action.UP,
        }
        if last_action is None or last_action not in reversal:
            return legal

        non_reversal = [move for move in legal if move != reversal[last_action]]
        return non_reversal or legal

    def _min_loop_distance(self, pos: Position, loop_positions: set[tuple[int, int]]) -> int:
        if not loop_positions:
            return 0

        return min(
            abs(pos.row - loop_row) + abs(pos.col - loop_col)
            for loop_row, loop_col in loop_positions
        )

    def _explore(self, creature: Creature, sense: list[int], pos: Position) -> None:
        legal = self.world.get_legal_moves(pos)
        if not legal:
            self._execute_move(creature, Action.IDLE, sense, CreatureMode.EXPLORE)
            return

        # Avoid immediate reversal if another option exists
        legal = self._prefer_non_reversal_moves(legal, creature.current_action)

        if not creature.last_replay_fail_reason:
            creature.last_replay_fail_reason = "no match"
        action = self._choose_action_with_lowest_revisit_penalty(creature, pos, legal)
        self._execute_move(creature, action, sense, CreatureMode.EXPLORE)

    def _execute_move(
        self, creature: Creature, action: int, sense: list[int], mode: int
    ) -> None:
        # Preserve the previous current_action before updating it
        creature.last_action = creature.current_action
        creature.current_action = action

        # Update the mode and position
        creature.mode = mode
        pos = creature.position
        new_pos = self.world.move_pos(pos, action)

        if action != Action.IDLE:
            # Check if target tile is food (pickup via explore / memory replay)
            target_tile = self.world.get_tile(new_pos.row, new_pos.col)
            if target_tile == Tile.FOOD:
                creature.food_score += 1
                self.stats.food_consumed += 1
            self.world.set_tile(pos.row, pos.col, Tile.EMPTY)
            self.world.set_tile(new_pos.row, new_pos.col, Tile.CREATURE)
            creature.position = new_pos

        # Append the step to recent_steps
        creature.recent_steps.append((pos, list(sense), action, creature.active_memory_idx))
        if len(creature.recent_steps) > MAX_RECENT_STEPS:
            creature.recent_steps.pop(0)
        self._maybe_record_pheromone(creature)

    def _direction_to(self, src: Position, dst: Position) -> int:
        dr = dst.row - src.row
        dc = dst.col - src.col
        if dr == -1:
            return Action.UP
        if dr == 1:
            return Action.DOWN
        if dc == -1:
            return Action.LEFT
        if dc == 1:
            return Action.RIGHT
        return Action.IDLE

    def _moves_toward(self, pos: Position, target: tuple[int, int]) -> list[int]:
        tr, tc = target
        dr = tr - pos.row
        dc = tc - pos.col
        moves: list[int] = []
        if dr < 0:
            moves.append(Action.UP)
        elif dr > 0:
            moves.append(Action.DOWN)
        if dc < 0:
            moves.append(Action.LEFT)
        elif dc > 0:
            moves.append(Action.RIGHT)
        return moves

    def epoch_reset(self, offspring: Optional[list[Creature]] = None) -> None:
        self.stats.epoch += 1
        self.stats.tick = 0
        self.stats.food_consumed = 0
        self.history = []

        # Clear non-wall tiles
        for row in range(self.config.height):
            for col in range(self.config.width):
                if self.world.get_tile(row, col) not in (Tile.WALL,):
                    self.world.set_tile(row, col, Tile.EMPTY)

        if offspring:
            self.creatures = offspring

        # Reset runtime state (memories persist)
        for creature in self.creatures:
            creature.food_score = 0
            creature.mode = CreatureMode.EXPLORE
            creature.last_action = None
            creature.last_match_score = 0.0
            creature.last_replay_fail_reason = ""
            creature.recent_steps = []
            creature.active_memory_idx = None
            creature.active_step_idx = None
            creature.last_replayed_memory_idx = None
            creature.current_sense_vector = []
            creature.current_action = None
            creature.recovery_steps_remaining = 0
            creature.recovery_loop_positions = []
            creature.memory_cooldowns = {}
            creature.memory_loop_strikes = {}
            creature.reverse_pheromone = {}
            creature.visible_pheromone = {}
        self.pheromone_trail = {}
        self._dirty_pheromone_cells = set()

        if self.authored_map is not None:
            self._restore_authored_food()
        else:
            self._place_food()
        self._place_creatures_existing()
        self._seed_pheromones()
        self._update_stats()

    def take_dirty_cells(self) -> list[tuple[int, int]]:
        dirty = set(self.world.take_changed_cells()) | self._dirty_pheromone_cells
        self._dirty_pheromone_cells = set()
        return list(dirty)

    def _place_creatures_existing(self) -> None:
        empties = self._empty_positions()
        if self.authored_map is not None and self.authored_map.spawn_positions:
            preferred = [
                (pos.row, pos.col)
                for pos in self.authored_map.spawn_positions
                if self.world.get_tile(pos.row, pos.col) == Tile.EMPTY
            ]
            preferred_set = set(preferred)
            remainder = [pos for pos in empties if pos not in preferred_set]
            self.rng.shuffle(remainder)
            ordered_positions = preferred + remainder
        else:
            self.rng.shuffle(empties)
            ordered_positions = empties
        for i, creature in enumerate(self.creatures):
            if i < len(ordered_positions):
                r, c = ordered_positions[i]
                creature.position = Position(r, c)
                self.world.set_tile(r, c, Tile.CREATURE)

    def _restore_authored_food(self) -> None:
        if self.authored_map is None:
            return
        for row in range(self.authored_map.height):
            for col in range(self.authored_map.width):
                if self.authored_map.terrain[row][col] == MAP_FOOD:
                    self.world.set_tile(row, col, Tile.FOOD)
