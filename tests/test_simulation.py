import unittest

from app.enums import Action, Tile
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
            reverse_pheromone={(3, 2): 10.0},
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
        self.assertGreater(creature.reverse_pheromone.get((3, 2), 0.0), 0.0)
        self.assertGreater(creature.visible_pheromone.get((3, 2), 0.0), 0.0)
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
        self.assertEqual(creature.reverse_pheromone.get((3, 2), 0.0), 0.0)
        self.assertEqual(creature.visible_pheromone.get((3, 2), 0.0), 0.0)

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


if __name__ == "__main__":
    unittest.main()
