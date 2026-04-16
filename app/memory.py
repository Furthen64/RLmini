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
    n = len(a)
    if n == 0:
        return 0.0
    return sum(x == y for x, y in zip(a, b)) / n


def _is_empty_sense(step: MemoryStep) -> bool:
    return not any(step.sense_vector)


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

    # All steps have all-empty sense vectors (zero informational value)
    if all(_is_empty_sense(s) for s in steps):
        return True

    # Majority of steps have all-empty sense vectors
    empty_count = sum(1 for s in steps if _is_empty_sense(s))
    if empty_count > len(steps) // 2:
        return True

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
    recent_steps: list,  # list of (Position, list[int], int, Optional[int])
) -> Optional[MemorySequence]:
    candidate_steps_raw = recent_steps[-4:]
    if not candidate_steps_raw:
        return None

    # Snip any all-empty sense vector step and everything that preceded it.
    # An all-empty sense vector carries no positional information and is what
    # causes creatures to learn degenerate "go LEFT in open space" habits.
    last_empty_idx = -1
    for i, step in enumerate(candidate_steps_raw):
        sv = step[1]
        if not any(sv):
            last_empty_idx = i
    if last_empty_idx >= 0:
        candidate_steps_raw = candidate_steps_raw[last_empty_idx + 1:]

    if not candidate_steps_raw:
        return None

    positions = [step[0] for step in candidate_steps_raw]
    steps = [MemoryStep(sense_vector=list(step[1]), action=step[2]) for step in candidate_steps_raw]

    if is_junk_memory(steps, positions):
        return None

    new_seq = MemorySequence(steps=steps)

    for existing in creature.memories:
        if sequences_identical(existing, new_seq):
            return None

    return new_seq
