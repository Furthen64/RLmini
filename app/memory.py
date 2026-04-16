import random
from typing import Optional

from app.enums import Action
from app.models import MemoryStep, MemorySequence, Creature, Position

REVERSAL_PAIRS: set[tuple[int, int]] = {
    (Action.LEFT, Action.RIGHT),
    (Action.RIGHT, Action.LEFT),
    (Action.UP, Action.DOWN),
    (Action.DOWN, Action.UP),
}


def sense_match_score(a: list[int], b: list[int]) -> float:
    return sum(x == y for x, y in zip(a, b)) / 8.0


def find_best_memory_match(
    creature: Creature,
    current_sense: list[int],
    threshold: float,
) -> Optional[tuple[int, int, float]]:
    """Return (memory_idx, step_idx, score) or None."""
    best_score = -1.0
    best_len = float("inf")
    best_candidates: list[tuple[int, int, float]] = []

    for mem_idx, mem_seq in enumerate(creature.memories):
        for step_idx, step in enumerate(mem_seq.steps):
            score = sense_match_score(current_sense, step.sense_vector)
            if score < threshold:
                continue
            seq_len = len(mem_seq.steps)
            if score > best_score:
                best_score = score
                best_len = seq_len
                best_candidates = [(mem_idx, step_idx, score)]
            elif score == best_score:
                if seq_len < best_len:
                    best_len = seq_len
                    best_candidates = [(mem_idx, step_idx, score)]
                elif seq_len == best_len:
                    best_candidates.append((mem_idx, step_idx, score))

    if not best_candidates:
        return None
    return random.choice(best_candidates)


def is_junk_memory(steps: list[MemoryStep], positions: list[Position]) -> bool:
    actions = [s.action for s in steps]

    # Immediate reversal check
    for i in range(len(actions) - 1):
        if (actions[i], actions[i + 1]) in REVERSAL_PAIRS:
            return True

    # More than one IDLE
    if actions.count(Action.IDLE) > 1:
        return True

    # Revisited position
    pos_set: set[tuple[int, int]] = set()
    for pos in positions:
        key = (pos.row, pos.col)
        if key in pos_set:
            return True
        pos_set.add(key)

    return False


def sequences_identical(a: MemorySequence, b: MemorySequence) -> bool:
    if len(a.steps) != len(b.steps):
        return False
    for sa, sb in zip(a.steps, b.steps):
        if sa.sense_vector != sb.sense_vector or sa.action != sb.action:
            return False
    return True


def try_create_memory(
    creature: Creature,
    recent_steps: list,  # list of (Position, list[int], int)
) -> Optional[MemorySequence]:
    candidate_steps_raw = recent_steps[-4:]
    if not candidate_steps_raw:
        return None

    positions = [p for p, sv, a in candidate_steps_raw]
    steps = [MemoryStep(sense_vector=list(sv), action=a) for p, sv, a in candidate_steps_raw]

    if is_junk_memory(steps, positions):
        return None

    new_seq = MemorySequence(steps=steps)

    for existing in creature.memories:
        if sequences_identical(existing, new_seq):
            return None

    return new_seq
