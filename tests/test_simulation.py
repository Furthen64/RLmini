import unittest
from unittest.mock import patch

from app.enums import Action, Tile, CreatureMode
from app.models import Creature, Position, WorldConfig
from app.simulation import Simulation
from app.world import World


class SimulationExploreTests(unittest.TestCase):
    def setUp(self) -> None:
        config = WorldConfig(
            width=5,
            height=5,
            creature_count=0,
            food_count=0,
            wall_count=0,
            seed=1,
            pheromone_drop_chance=0.0,
        )
        self.simulation = Simulation(config)

        for row in range(config.height):
            for col in range(config.width):
                tile = Tile.WALL if row in (0, config.height - 1) or col in (0, config.width - 1) else Tile.EMPTY
                self.simulation.world.set_tile(row, col, tile)

        self.creature = Creature(
            id=1,
            position=Position(2, 2),
            current_action=Action.RIGHT,
            last_action=Action.LEFT,
            pheromone={(3, 2): 10.0},
        )
        self.simulation.creatures = [self.creature]
        self.simulation.world.set_tile(2, 2, Tile.CREATURE)
        self.simulation.world.set_tile(1, 2, Tile.WALL)
        self.simulation.world.set_tile(2, 3, Tile.WALL)

    def test_explore_avoids_reversing_latest_move(self) -> None:
        sense = self.simulation.world.get_sense_vector(self.creature.position)

        self.simulation._explore(self.creature, sense, self.creature.position)

        self.assertEqual(self.creature.position, Position(3, 2))
        self.assertEqual(self.creature.current_action, Action.DOWN)
        self.assertEqual(self.creature.last_action, Action.RIGHT)

    def test_recovery_explore_avoids_reversing_latest_move(self) -> None:
        sense = self.simulation.world.get_sense_vector(self.creature.position)
        self.creature.recovery_steps_remaining = 2
        self.creature.recovery_loop_positions = [Position(2, 1), Position(2, 2)]

        self.simulation._recovery_explore(self.creature, sense, self.creature.position)

        self.assertEqual(self.creature.position, Position(3, 2))
        self.assertEqual(self.creature.current_action, Action.DOWN)
        self.assertEqual(self.creature.last_action, Action.RIGHT)
        self.assertEqual(self.creature.recovery_steps_remaining, 1)

    def test_following_creature_prefers_other_visible_pheromone(self) -> None:
        follower = Creature(
            id=2,
            position=Position(2, 2),
            follow_pheromone_trail=True,
        )
        self.simulation.pheromone_trail[(2, 1)] = 2.0

        toward_pheromone = self.simulation._calculate_revisit_penalty_for_action(
            follower,
            follower.position,
            Action.LEFT,
            [],
            [follower.position],
        )
        away_from_pheromone = self.simulation._calculate_revisit_penalty_for_action(
            follower,
            follower.position,
            Action.DOWN,
            [],
            [follower.position],
        )

        self.assertLess(toward_pheromone, away_from_pheromone)

    def test_execute_move_can_leave_visible_pheromone(self) -> None:
        config = WorldConfig(
            width=5,
            height=5,
            creature_count=0,
            food_count=0,
            wall_count=0,
            seed=1,
            pheromone_drop_chance=1.0,
        )
        simulation = Simulation(config)
        creature = Creature(id=3, position=Position(2, 2))
        simulation.creatures = [creature]
        simulation.world.set_tile(2, 2, Tile.CREATURE)

        sense = simulation.world.get_sense_vector(creature.position)
        simulation._execute_move(creature, Action.DOWN, sense, creature.mode)

        self.assertGreater(simulation.pheromone_trail.get((3, 2), 0.0), 0.0)
        self.assertGreater(creature.pheromone.get((3, 2), 0.0), 0.0)
        self.assertGreater(creature.pheromone_ui.get((3, 2), 0.0), 0.0)
        self.assertIn((3, 2), simulation.take_dirty_cells())

    def test_execute_move_skips_pheromone_when_probability_misses(self) -> None:
        config = WorldConfig(
            width=5,
            height=5,
            creature_count=0,
            food_count=0,
            wall_count=0,
            seed=1,
            pheromone_drop_chance=0.0,
        )
        simulation = Simulation(config)
        creature = Creature(id=4, position=Position(2, 2))
        simulation.creatures = [creature]
        simulation.world.set_tile(2, 2, Tile.CREATURE)

        sense = simulation.world.get_sense_vector(creature.position)
        simulation._execute_move(creature, Action.DOWN, sense, creature.mode)

        self.assertEqual(simulation.pheromone_trail.get((3, 2), 0.0), 0.0)
        self.assertEqual(creature.pheromone.get((3, 2), 0.0), 0.0)
        self.assertEqual(creature.pheromone_ui.get((3, 2), 0.0), 0.0)

    def test_detect_recent_loop_catches_position_revisit(self) -> None:
        """A 6-step cycle that isn't a simple suffix repetition is caught by position-revisit detection."""
        # Reproduces the bug: (7,13)→(7,12)→(7,11)→(7,12)→(7,13)→(6,13)
        # (7,12) and (7,13) each appear twice, but there is no repeated suffix pattern.
        steps = [
            (Position(7, 13), [], 3, None),   # LEFT
            (Position(7, 12), [], 3, None),   # LEFT
            (Position(7, 11), [], 2, 0),      # RIGHT (memory 0)
            (Position(7, 12), [], 2, None),   # RIGHT
            (Position(7, 13), [], 0, None),   # UP
            (Position(6, 13), [], 1, 0),      # DOWN (memory 0)
        ]
        self.creature.recent_steps = steps

        result = self.simulation._detect_recent_loop(self.creature)

        self.assertIsNotNone(result)

    def test_detect_recent_loop_no_false_positive_unique_positions(self) -> None:
        """A sequence with all unique positions should NOT trigger loop detection."""
        steps = [
            (Position(1, 1), [], 2, None),
            (Position(1, 2), [], 2, None),
            (Position(1, 3), [], 1, None),
            (Position(2, 3), [], 3, None),
            (Position(3, 3), [], 3, None),
            (Position(3, 2), [], 3, None),
        ]
        self.creature.recent_steps = steps

        result = self.simulation._detect_recent_loop(self.creature)

        self.assertIsNone(result)

    def test_second_vision_updates_only_every_tenth_tick(self) -> None:
        config = WorldConfig(
            width=7,
            height=7,
            creature_count=2,
            food_count=0,
            wall_count=0,
            seed=1,
            pheromone_drop_chance=0.0,
        )
        simulation = Simulation(config)

        with patch("app.simulation.update_second_vision") as update_mock:
            for _ in range(9):
                simulation.tick()

            self.assertEqual(update_mock.call_count, 0)

            simulation.tick()

            self.assertEqual(update_mock.call_count, len(simulation.creatures))

            for _ in range(9):
                simulation.tick()

            self.assertEqual(update_mock.call_count, len(simulation.creatures))

            simulation.tick()

            self.assertEqual(update_mock.call_count, len(simulation.creatures) * 2)


class WorldLineOfSightTests(unittest.TestCase):
    def setUp(self) -> None:
        # 7-wide, 7-tall world; sense_radius=3 so food anywhere inside is in range
        self.world = World(7, 7, sense_radius=3)

    def test_clear_path_horizontal(self) -> None:
        self.assertTrue(self.world.has_line_of_sight(3, 1, 3, 5))

    def test_clear_path_vertical(self) -> None:
        self.assertTrue(self.world.has_line_of_sight(1, 3, 5, 3))

    def test_clear_path_diagonal(self) -> None:
        self.assertTrue(self.world.has_line_of_sight(1, 1, 5, 5))

    def test_wall_blocks_horizontal(self) -> None:
        self.world.set_tile(3, 3, Tile.WALL)
        self.assertFalse(self.world.has_line_of_sight(3, 1, 3, 5))

    def test_wall_blocks_vertical(self) -> None:
        self.world.set_tile(3, 3, Tile.WALL)
        self.assertFalse(self.world.has_line_of_sight(1, 3, 5, 3))

    def test_adjacent_cell_always_visible(self) -> None:
        # No intermediate cells — always line of sight
        self.world.set_tile(3, 4, Tile.WALL)
        self.assertTrue(self.world.has_line_of_sight(3, 3, 3, 4))

    def test_get_visible_food_excludes_wall_blocked_food(self) -> None:
        creature_pos = Position(3, 1)
        self.world.set_tile(3, 1, Tile.CREATURE)
        self.world.set_tile(3, 3, Tile.WALL)   # wall between creature and food
        self.world.set_tile(3, 5, Tile.FOOD)   # food behind wall

        visible = self.world.get_visible_food(creature_pos)

        self.assertNotIn((3, 5), visible)

    def test_get_visible_food_includes_unblocked_food(self) -> None:
        creature_pos = Position(3, 1)
        self.world.set_tile(3, 1, Tile.CREATURE)
        self.world.set_tile(3, 4, Tile.FOOD)   # food with clear path

        visible = self.world.get_visible_food(creature_pos)

        self.assertIn((3, 4), visible)

    def test_get_visible_food_same_row_wall_between(self) -> None:
        creature_pos = Position(3, 1)
        self.world.set_tile(3, 1, Tile.CREATURE)
        self.world.set_tile(3, 2, Tile.WALL)
        self.world.set_tile(3, 3, Tile.FOOD)

        visible = self.world.get_visible_food(creature_pos)

        self.assertNotIn((3, 3), visible)


class ExplorationScoringTests(unittest.TestCase):
    """Tests for frontier/novelty-bias explore-mode scoring."""

    def _make_sim(self, **extra_config) -> Simulation:
        """Return a small, deterministic, wall-bordered 5x5 simulation."""
        config = WorldConfig(
            width=5,
            height=5,
            creature_count=0,
            food_count=0,
            wall_count=0,
            seed=1,
            pheromone_drop_chance=0.0,
            **extra_config,
        )
        sim = Simulation(config)
        # Ensure border walls, interior empty
        for row in range(config.height):
            for col in range(config.width):
                tile = (
                    Tile.WALL
                    if row in (0, config.height - 1) or col in (0, config.width - 1)
                    else Tile.EMPTY
                )
                sim.world.set_tile(row, col, tile)
        return sim

    def _place_creature(self, sim: Simulation, row: int, col: int) -> Creature:
        creature = Creature(id=99, position=Position(row, col))
        sim.world.set_tile(row, col, Tile.CREATURE)
        sim.creatures = [creature]
        return creature

    # ------------------------------------------------------------------

    def test_explore_prefers_unvisited_tile_over_visited(self) -> None:
        """Score-based _explore must choose a never-visited tile over a heavily visited one."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)

        # Mark (2,1) as visited many times; (2,3) and others are fresh
        creature.visit_count_by_pos[(2, 1)] = 50
        # Block UP and DOWN so only LEFT and RIGHT are legal
        sim.world.set_tile(1, 2, Tile.WALL)
        sim.world.set_tile(3, 2, Tile.WALL)

        sense = sim.world.get_sense_vector(creature.position)
        sim._explore(creature, sense, creature.position)

        # Should have moved RIGHT (to unvisited (2,3)) not LEFT (to heavily visited (2,1))
        self.assertEqual(creature.position, Position(2, 3))

    def test_explore_recent_position_penalty_discourages_loops(self) -> None:
        """Tiles in recent_positions should be penalised, causing the creature to avoid them."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)

        # Mark (3,2) as a recent position; (1,2) is fresh
        creature.recent_positions = [(3, 2)]
        # Block LEFT/RIGHT so only UP and DOWN are legal
        sim.world.set_tile(2, 1, Tile.WALL)
        sim.world.set_tile(2, 3, Tile.WALL)

        sense = sim.world.get_sense_vector(creature.position)
        sim._explore(creature, sense, creature.position)

        # (3,2) is penalised; creature should go UP to fresh (1,2)
        self.assertEqual(creature.position, Position(1, 2))

    def test_explore_reverse_penalty_discourages_backtrack(self) -> None:
        """Immediate reversal should be penalised and avoided when alternatives exist."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)

        # Creature last moved RIGHT (Action.RIGHT); reversing would be LEFT
        creature.current_action = Action.RIGHT
        # Block DOWN so only LEFT and UP are legal from (2,2)
        sim.world.set_tile(3, 2, Tile.WALL)
        sim.world.set_tile(2, 3, Tile.WALL)  # RIGHT is also blocked
        # UP (1,2) and LEFT (2,1) are available; LEFT is the reversal

        sense = sim.world.get_sense_vector(creature.position)
        sim._explore(creature, sense, creature.position)

        # Should prefer UP (not the reversal LEFT)
        self.assertEqual(creature.position, Position(1, 2))

    def test_explore_scores_stored_for_debug(self) -> None:
        """last_explore_scores must be populated after an explore step."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)

        sense = sim.world.get_sense_vector(creature.position)
        sim._explore(creature, sense, creature.position)

        self.assertGreater(len(creature.last_explore_scores), 0)
        # Each entry: (action, pos_key, score, new_tile, in_recent, is_reversal)
        for entry in creature.last_explore_scores:
            action, key, score, new_tile, in_recent, is_rev = entry
            self.assertIsInstance(score, float)
            self.assertIsInstance(new_tile, bool)
            self.assertIsInstance(in_recent, bool)
            self.assertIsInstance(is_rev, bool)

    def test_adjacent_food_overrides_exploration(self) -> None:
        """Adjacent food must be eaten immediately, overriding explore scoring."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)
        # Place food directly below
        sim.world.set_tile(3, 2, Tile.FOOD)

        sim._tick_creature(creature)

        self.assertEqual(creature.position, Position(3, 2))
        self.assertEqual(creature.food_score, 1)
        self.assertEqual(creature.mode, CreatureMode.FOOD_DIRECT)

    def test_visible_food_overrides_exploration(self) -> None:
        """Visible food (sense-radius reachable) must override pure explore mode."""
        sim = self._make_sim(sense_radius=2)
        # Larger world so food can be within sense radius but not adjacent
        config = WorldConfig(
            width=9, height=9,
            creature_count=0, food_count=0, wall_count=0,
            seed=1, pheromone_drop_chance=0.0, sense_radius=2,
        )
        sim2 = Simulation(config)
        for row in range(9):
            for col in range(9):
                tile = (
                    Tile.WALL
                    if row in (0, 8) or col in (0, 8)
                    else Tile.EMPTY
                )
                sim2.world.set_tile(row, col, tile)
        creature = Creature(id=1, position=Position(4, 4))
        sim2.world.set_tile(4, 4, Tile.CREATURE)
        sim2.creatures = [creature]
        # Food two steps right, within sense radius but not adjacent
        sim2.world.set_tile(4, 6, Tile.FOOD)

        sim2._tick_creature(creature)

        # Creature should have moved toward (4,6): must be at (4,5) or (4,6)
        self.assertIn(creature.position, [Position(4, 5), Position(4, 6)])
        self.assertEqual(creature.mode, CreatureMode.FOOD_DIRECT)

    def test_epoch_reset_clears_exploration_state(self) -> None:
        """epoch_reset must zero visit_count_by_pos, recent_positions, and last_explore_scores."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)

        # Populate explore state manually
        creature.visit_count_by_pos = {(2, 2): 5, (2, 3): 2}
        creature.recent_positions = [(2, 2), (2, 3), (2, 2)]
        creature.last_explore_scores = [(Action.RIGHT, (2, 3), 8.0, True, False, False)]

        sim.epoch_reset()

        self.assertEqual(creature.visit_count_by_pos, {})
        self.assertEqual(creature.recent_positions, [])
        self.assertEqual(creature.last_explore_scores, [])

    def test_visit_count_increments_on_move(self) -> None:
        """visit_count_by_pos should increment each time a creature occupies a tile."""
        sim = self._make_sim()
        creature = self._place_creature(sim, 2, 2)
        # Block all but RIGHT
        sim.world.set_tile(1, 2, Tile.WALL)
        sim.world.set_tile(3, 2, Tile.WALL)
        sim.world.set_tile(2, 1, Tile.WALL)

        sense = sim.world.get_sense_vector(creature.position)
        sim._execute_move(creature, Action.RIGHT, sense, CreatureMode.EXPLORE)

        # Creature is now at (2,3); that tile should have been visited once
        self.assertEqual(creature.visit_count_by_pos.get((2, 3), 0), 1)
        self.assertIn((2, 3), creature.recent_positions)


if __name__ == "__main__":
    unittest.main()
