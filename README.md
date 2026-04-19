# RLmini

RLmini is a PySide6 desktop simulation of creatures moving through a 2D grid world with walls, food, local memory, pheromone trails, and between-epoch inheritance.

The codebase is built for inspectability rather than opaque model training. Creatures behave through explicit rules, local sensing, stored memory sequences, and simple inheritance across epochs.

## What This App Is

This project is closer to an interactive simulation sandbox than a conventional machine learning training stack.

- The UI is a native Qt Widgets desktop app.
- The simulation engine is handwritten Python code.
- Creature behavior is rule-based and memory-driven.
- Epoch resets keep learned memory sequences while resetting runtime state.
- A built-in map editor supports authored scenarios.

There are no neural networks, gradient updates, or external RL frameworks in the current implementation.

## Launch

Run the main simulation app:

```bash
./launch.sh
```

Run the standalone map editor:

```bash
./launch_editor.sh
```

You can also pass a map file directly to the editor:

```bash
./launch_editor.sh maps/sample_basic.map
```

The launch scripts create or reuse `.venv`, install the minimal dependencies from `requirements.txt`, and then run the appropriate module entry point.

## How It Works

### Runtime flow

The main window creates a `Simulation` object and drives it with a Qt timer. Each timer tick advances the world by one simulation step, updates the stats graph, refreshes the grid widget, and updates the details panel for the selected creature.

At a high level:

1. `app.main` starts the Qt application.
2. `app.ui.main_window.MainWindow` loads settings, restores any selected map, and creates the initial simulation.
3. `app.simulation.Simulation` owns the world state, creatures, tick history, and pheromone trail.
4. UI widgets render and inspect that state live.

### Simulation loop

Each creature decides what to do in this priority order:

1. Adjacent food override: if food is next to the creature, move onto it immediately.
2. Visible food pursuit: if food is in sensed range and not blocked by walls, move toward it.
3. Memory replay: match the current sense vector against stored memories and replay the best valid step.
4. Explore: if nothing better applies, choose a move that favors novelty and avoids loops.

The world is tile-based and uses integer enums for:

- empty cells
- walls
- food
- creatures

Creatures track:

- current position
- food score
- recent steps
- stored memory sequences
- active replay state
- visit counts and recent positions for exploration scoring
- local pheromone history and visible pheromone trail state

### Memory and learning model

RLmini does not train a policy network. Instead, creatures learn short memory sequences from successful recent behavior.

- A memory step stores a sensed neighborhood plus an action.
- A memory sequence stores 1 to 4 such steps.
- Low-value memories are filtered out if they are repetitive, empty, or obviously loop-prone.
- During replay, the app chooses the best matching memory step above a configurable threshold.
- If replay appears to create loops, the app cools down or deletes problematic memories and forces temporary recovery exploration.

### Exploration behavior

Exploration prefers moves that:

- lead to never-visited tiles
- revisit low-visit tiles rather than heavily repeated ones
- avoid the recent position window
- avoid immediate reversals when possible

The details window exposes the last explore candidate scores so the behavior can be debugged visually.

### Epoch resets and inheritance

The app runs in epochs of configurable length.

- During an epoch, creatures accumulate food score.
- At epoch end, top performers are selected as parents.
- Offspring inherit the parents' memory sequences.
- Runtime-only state such as current action, cooldowns, pheromones, and recent paths is reset.
- Food and creature placement are regenerated for the next epoch.

This gives the app an inheritance loop without introducing a heavyweight ML training system.

## Code Layout

Main modules:

- `app/main.py`: simulator entry point
- `app/editor_main.py`: standalone map editor entry point
- `app/ui/main_window.py`: application orchestration and menus
- `app/simulation.py`: main simulation loop and creature behavior
- `app/world.py`: grid representation, sensing, legal moves, and line of sight
- `app/memory.py`: memory matching and memory creation rules
- `app/reproduction.py`: parent selection and offspring generation
- `app/map_format.py`: map parsing, validation, serialization, and metadata
- `app/settings_store.py`: persistent JSON-backed app settings
- `tests/test_simulation.py`: simulation-focused automated tests

There is a more explicit stack summary in `TECHSTACK.md`.

## Maps

Map files are plain text.

- Optional metadata lines come first and start with `#`.
- After that, each non-empty line is one map row.
- Rows must all have the same width.
- Border cells must be walls.

Supported V1 tokens:

- `0` empty
- `1` wall
- `2` food
- `3` creature spawn marker

Spawn markers are editor and authored-map concepts only. When RLmini loads a map, spawn markers become initial creature positions on empty floor rather than persistent `CREATURE` tiles.

Example:

```text
# name: sample_basic
# version: 1

1111111111
1000000001
1030200001
1000110001
1000003001
1111111111
```

## Workflow

- Use the standalone editor for map authoring.
- Use `File -> Load Map...` inside RLmini to run the simulation on a saved map.
- Use `File -> Open Map Editor` inside RLmini to snapshot the current map state, edit it, and apply it back directly without saving a file first.
- When an authored map is loaded, the simulator uses its walls, food layout, and optional spawn positions.

## Settings and Persistence

RLmini stores persistent settings as JSON under the user's config directory.

These settings include values such as:

- world dimensions
- counts for creatures, food, and walls
- epoch length and tick interval
- visualization toggles
- exploration tuning values
- loaded map path and recent maps
- window geometry for the main window, details window, and editor

## Testing

The repository includes automated tests for simulation behavior, especially around exploration, line of sight, loop detection, and pheromone-related behavior.

Run tests from the project root with:

```bash
PYTHONPATH=. .venv/bin/pytest -q .
```

## Sample Maps

- [maps/sample_basic.map](/home/fayt64/github/RLmini/maps/sample_basic.map)
