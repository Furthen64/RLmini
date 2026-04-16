import random
from typing import Optional

from app.enums import Tile, Action, CreatureMode
from app.models import Position, Creature, WorldConfig, SimulationStats
from app.world import World, CARDINAL_OFFSETS
from app.memory import find_best_memory_match, try_create_memory


class Simulation:
    def __init__(self, config: WorldConfig, rng_seed: Optional[int] = None) -> None:
        self.config = config
        self.rng = random.Random(rng_seed)
        self.world = World(config.width, config.height)
        self.creatures: list[Creature] = []
        self.stats = SimulationStats()
        self._next_creature_id = 0
        self._initialize()

    def _initialize(self) -> None:
        self._place_walls()
        self._place_food()
        self._place_creatures()
        self._update_stats()

    def _place_walls(self) -> None:
        for row in range(self.config.height):
            for col in range(self.config.width):
                if (
                    row == 0
                    or row == self.config.height - 1
                    or col == 0
                    or col == self.config.width - 1
                ):
                    self.world.set_tile(row, col, Tile.WALL)

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
            creature = Creature(id=self._next_creature_id, position=Position(r, c))
            self._next_creature_id += 1
            self.world.set_tile(r, c, Tile.CREATURE)
            self.creatures.append(creature)

    def _update_stats(self) -> None:
        self.stats.food_remaining = self.world.count_food()
        self.stats.creature_count = len(self.creatures)

    def tick(self) -> None:
        order = list(self.creatures)
        self.rng.shuffle(order)
        for creature in order:
            self._tick_creature(creature)
        self.stats.tick += 1
        self._update_stats()

    def _tick_creature(self, creature: Creature) -> None:
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
            creature.recent_steps.append((pos, list(sense), action))
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
            return

        # 2. Visible food pursuit (diagonal counts)
        visible_food = self.world.get_visible_food(pos)
        if visible_food:
            target = self.rng.choice(visible_food)
            best_moves = self._moves_toward(pos, target)
            legal = self.world.get_legal_moves(pos)
            toward_legal = [m for m in best_moves if m in legal]
            if toward_legal:
                action = self.rng.choice(toward_legal)
                creature.mode = CreatureMode.FOOD_DIRECT
                creature.active_memory_idx = None
                creature.active_step_idx = None
                self._execute_move(creature, action, sense, CreatureMode.FOOD_DIRECT)
                return

        # 3. Memory replay
        match = find_best_memory_match(creature, sense, self.config.match_threshold)
        if match is not None:
            mem_idx, step_idx, score = match
            mem_seq = creature.memories[mem_idx]
            action = mem_seq.steps[step_idx].action
            new_pos = self.world.move_pos(pos, action)
            target_tile = self.world.get_tile(new_pos.row, new_pos.col)

            if action != Action.IDLE and target_tile == Tile.WALL:
                creature.last_replay_fail_reason = "blocked by wall"
                creature.active_memory_idx = None
                creature.active_step_idx = None
                self._explore(creature, sense, pos)
                return
            elif action != Action.IDLE and target_tile == Tile.CREATURE:
                creature.last_replay_fail_reason = "blocked by creature"
                creature.active_memory_idx = None
                creature.active_step_idx = None
                self._explore(creature, sense, pos)
                return

            creature.last_match_score = score
            creature.last_replay_fail_reason = ""
            creature.active_memory_idx = mem_idx
            creature.active_step_idx = step_idx
            self._execute_move(creature, action, sense, CreatureMode.MEMORY_REPLAY)
            return

        # 4. Explore
        creature.active_memory_idx = None
        creature.active_step_idx = None
        self._explore(creature, sense, pos)

    def _explore(self, creature: Creature, sense: list[int], pos: Position) -> None:
        legal = self.world.get_legal_moves(pos)
        if not legal:
            self._execute_move(creature, Action.IDLE, sense, CreatureMode.EXPLORE)
            return

        # Avoid immediate reversal if another option exists
        reversal: dict[int, int] = {
            Action.LEFT: Action.RIGHT,
            Action.RIGHT: Action.LEFT,
            Action.UP: Action.DOWN,
            Action.DOWN: Action.UP,
        }
        last = creature.last_action
        if last is not None and last in reversal:
            non_reversal = [m for m in legal if m != reversal[last]]
            if non_reversal:
                legal = non_reversal

        if not creature.last_replay_fail_reason:
            creature.last_replay_fail_reason = "no match"
        action = self.rng.choice(legal)
        self._execute_move(creature, action, sense, CreatureMode.EXPLORE)

    def _execute_move(
        self, creature: Creature, action: int, sense: list[int], mode: int
    ) -> None:
        pos = creature.position
        new_pos = self.world.move_pos(pos, action)

        if action != Action.IDLE:
            self.world.set_tile(pos.row, pos.col, Tile.EMPTY)
            self.world.set_tile(new_pos.row, new_pos.col, Tile.CREATURE)
            creature.position = new_pos

        creature.mode = mode
        creature.current_action = action
        creature.last_action = action

        creature.recent_steps.append((pos, list(sense), action))
        if len(creature.recent_steps) > 4:
            creature.recent_steps.pop(0)

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
            creature.current_sense_vector = []
            creature.current_action = None

        self._place_food()
        self._place_creatures_existing()
        self._update_stats()

    def _place_creatures_existing(self) -> None:
        empties = self._empty_positions()
        self.rng.shuffle(empties)
        for i, creature in enumerate(self.creatures):
            if i < len(empties):
                r, c = empties[i]
                creature.position = Position(r, c)
                self.world.set_tile(r, c, Tile.CREATURE)
