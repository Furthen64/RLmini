# Fixes

## app/simulation.py

Optimize `_tick_creature` to handle invalid indices returned by `find_best_memory_match`.

## app/world.py

Add input validation to `set_tile` and `get_tile` in `app/world.py` to ensure row and column indices are within bounds.

Add exception handling in `_tick_creature` and `_explore` to prevent runtime errors and infinite loops.

## app/reproduction.py

Replace hardcoded values like `top_fraction=0.5` in `app/reproduction.py` with configurable parameters.

## memory.py

Refactor redundant checks in `try_create_memory` in `app/memory.py` to consolidate logic.

## ui/main_window.py

Refactor `_auto_tick` in `app/ui/main_window.py` to use threading or asynchronous calls to ensure the UI remains responsive during long-running ticks.
