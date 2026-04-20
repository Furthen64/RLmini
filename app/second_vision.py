"""Second Vision Layer — raycasting, tile discovery, and area detection.

This module is purely observational: it does not influence creature AI in any
way.  It is only used for debug/visualisation purposes.
"""
from collections import deque

from app.enums import Action, Tile
from app.models import Creature, SecondVisionData
from app.world import World

# The 8 fixed compass directions: (row_delta, col_delta)
_COMPASS_DIRS: list[tuple[int, int]] = [
    (-1,  0),   # N
    (-1,  1),   # NE
    ( 0,  1),   # E
    ( 1,  1),   # SE
    ( 1,  0),   # S
    ( 1, -1),   # SW
    ( 0, -1),   # W
    (-1, -1),   # NW
]

# Map Action → (row_delta, col_delta) for the 9th (forward) ray
_ACTION_DELTA: dict[int, tuple[int, int]] = {
    Action.UP:    (-1,  0),
    Action.DOWN:  ( 1,  0),
    Action.LEFT:  ( 0, -1),
    Action.RIGHT: ( 0,  1),
}


def _cast_single_ray(
    world: World,
    start_row: int,
    start_col: int,
    dr: int,
    dc: int,
    ray_length: int,
    discovered: dict[tuple[int, int], int],
) -> tuple[int, int]:
    """Cast one ray from (start_row, start_col) in direction (dr, dc).

    Every non-wall cell along the path is recorded in *discovered*.
    The first wall cell hit is also recorded.
    Returns the (row, col) endpoint: either the wall cell or the last in-bounds
    cell reached within *ray_length* steps.
    """
    r, c = start_row, start_col
    endpoint = (r, c)
    for _ in range(ray_length):
        r += dr
        c += dc
        if not world.in_bounds(r, c):
            # Treat out-of-bounds as a wall; endpoint is the last valid pos
            break
        tile = world.get_tile(r, c)
        discovered[(r, c)] = tile
        endpoint = (r, c)
        if tile == Tile.WALL:
            break
    return endpoint


def cast_rays(
    creature: Creature,
    world: World,
    ray_length: int,
) -> tuple[list[tuple[int, int]], dict[tuple[int, int], int]]:
    """Cast 9 rays from the creature's current position.

    Returns:
        endpoints  – list of 9 (row, col) endpoint positions
        discovered – mapping of (row, col) → Tile for all cells observed
    """
    discovered: dict[tuple[int, int], int] = {}
    endpoints: list[tuple[int, int]] = []

    r0, c0 = creature.position.row, creature.position.col

    # 8 compass rays
    for dr, dc in _COMPASS_DIRS:
        ep = _cast_single_ray(world, r0, c0, dr, dc, ray_length, discovered)
        endpoints.append(ep)

    # 9th ray: forward (creature's last action direction, default N)
    fwd_delta = _ACTION_DELTA.get(creature.last_action, (-1, 0))
    ep = _cast_single_ray(world, r0, c0, fwd_delta[0], fwd_delta[1], ray_length, discovered)
    endpoints.append(ep)

    return endpoints, discovered


def _recompute_areas(sv: SecondVisionData) -> None:
    """Flood-fill (BFS, 4-directional) over non-wall discovered tiles.

    Each connected component of walkable cells gets a unique integer area_id.
    The result is stored in sv.area_map (previous contents are replaced).
    """
    walkable = {
        pos
        for pos, tile in sv.discovered_tiles.items()
        if tile != Tile.WALL
    }

    sv.area_map = {}
    area_id = 0
    visited: set[tuple[int, int]] = set()

    for seed in walkable:
        if seed in visited:
            continue
        # BFS from seed
        queue: deque[tuple[int, int]] = deque([seed])
        visited.add(seed)
        while queue:
            r, c = queue.popleft()
            sv.area_map[(r, c)] = area_id
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (r + dr, c + dc)
                if nb in walkable and nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        area_id += 1

    sv._dirty = False


def update_second_vision(
    creature: Creature,
    world: World,
    ray_length: int,
) -> None:
    """Update the creature's Second Vision layer for the current tick.

    1. Casts 9 rays to discover tiles at range.
    2. Merges the ray observations with the near-field sense_vector data.
    3. Stores the ray endpoints.
    4. Re-runs the flood-fill area computation if new tiles were discovered.
    """
    sv = creature.second_vision

    # --- ray observations ---
    endpoints, ray_discovered = cast_rays(creature, world, ray_length)
    sv.ray_endpoints = endpoints

    tiles = sv.discovered_tiles
    changed = False

    # Merge ray observations
    for pos, tile in ray_discovered.items():
        if tiles.get(pos) != tile:
            changed = True
            tiles[pos] = tile

    # Also record the creature's own position
    own_key = (creature.position.row, creature.position.col)
    own_tile = world.get_tile(creature.position.row, creature.position.col)
    if tiles.get(own_key) != own_tile:
        changed = True
        tiles[own_key] = own_tile

    # Merge near-field sense vector (already computed this tick)
    if creature.current_sense_vector:
        from app.world import get_sense_offsets
        offsets = get_sense_offsets(world.sense_radius)
        r0, c0 = creature.position.row, creature.position.col
        for (dr, dc), tile in zip(offsets, creature.current_sense_vector):
            key = (r0 + dr, c0 + dc)
            if tiles.get(key) != tile:
                changed = True
                tiles[key] = tile

    # Recompute areas only when something changed
    if changed:
        sv._dirty = True
        _recompute_areas(sv)
