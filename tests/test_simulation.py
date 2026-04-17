import unittest

from app.enums import Action, Tile
from app.models import Creature, Position, WorldConfig
from app.simulation import Simulation


class SimulationExploreTests(unittest.TestCase):
    def setUp(self) -> None:
        config = WorldConfig(
            width=5,
            height=5,
            creature_count=0,
            food_count=0,
            wall_count=0,
            seed=1,
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


if __name__ == "__main__":
    unittest.main()
