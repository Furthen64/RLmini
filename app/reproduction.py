import random

from app.models import Creature, MemorySequence, Position
from app.config import ReproductionConfig


def select_parents(creatures: list[Creature], top_n: int) -> list[Creature]:
    sorted_c = sorted(creatures, key=lambda c: c.food_score, reverse=True)
    return sorted_c[: max(1, top_n)]


def create_offspring(
    parents: list[Creature],
    target_count: int,
    next_id_start: int,
    rng: random.Random,
) -> list[Creature]:
    offspring = []
    for i in range(target_count):
        parent = rng.choice(parents)
        child = Creature(
            id=next_id_start + i,
            position=Position(parent.position.row, parent.position.col),
            memories=[
                MemorySequence(steps=list(seq.steps))
                for seq in parent.memories
            ],
            follow_pheromone_trail=parent.follow_pheromone_trail,
        )
        offspring.append(child)
    return offspring


def reproduce(
    creatures: list[Creature],
    target_count: int,
    next_id_start: int,
    rng: random.Random,
    top_fraction: float = ReproductionConfig.TOP_FRACTION,
) -> list[Creature]:
    top_n = max(1, int(len(creatures) * top_fraction))
    parents = select_parents(creatures, top_n)
    return create_offspring(parents, target_count, next_id_start, rng)
