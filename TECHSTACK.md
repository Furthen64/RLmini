# TECHSTACK

## Overview

RLmini is a Python desktop application that simulates creatures moving through a 2D grid world. It uses a rule-based, memory-driven behavior model with between-epoch inheritance. Despite the name, this is not a deep learning or neural network project. There is no PyTorch, TensorFlow, or model training pipeline in this repository.

## Core Runtime

- Built and tested on Python 3.12.
- The application code is organized as a plain Python package under `app/`.
- The project relies heavily on Python standard library modules such as `dataclasses`, `enum`, `json`, `pathlib`, `random`, and `typing`.

## Desktop UI

- PySide6 provides the desktop application framework.
- The UI uses Qt Widgets rather than QML or a web frontend.
- The two main entry points are:
  - `python -m app.main` for the main simulator
  - `python -m app.editor_main` for the standalone map editor

Main UI modules:

- `app/ui/main_window.py`: main simulation window, menu actions, timers, and app orchestration
- `app/ui/grid_widget.py`: custom widget that paints the world grid, creatures, and pheromone overlays
- `app/ui/details_window.py`: live debug panel for a selected creature's state, memory, and exploration scores
- `app/ui/settings_panel.py`: editable simulation configuration
- `app/ui/controls_panel.py`: run, pause, step, and reset controls
- `app/ui/map_editor_window.py`: standalone and in-app map editor window
- `app/ui/map_editor_widget.py`: map painting surface for the editor

## Visualization

- `pyqtgraph` is used for the live stats graph.
- The graph displays per-tick values such as food remaining, best score, and average score.
- Qt painting is used directly for the grid view instead of a game engine or OpenGL scene.

## Simulation Model

The simulation logic is custom application code, not a reinforcement learning framework.

- `app/world.py` stores the grid, legal movement rules, sense vector generation, and line-of-sight checks.
- `app/simulation.py` runs the tick loop, food seeking, memory replay, explore behavior, pheromone handling, and epoch resets.
- `app/memory.py` handles memory matching, similarity scoring, and filtering out low-value or looping memories.
- `app/reproduction.py` selects high-performing creatures and clones their memory sequences into offspring for the next epoch.
- `app/models.py` defines the dataclasses that carry state across the app.
- `app/enums.py` contains the tile, action, and creature mode enums.

Behavior is algorithmic and deterministic given the RNG seed. The main decision order per creature tick is:

1. Move to adjacent food if available.
2. Move toward visible food when line of sight exists.
3. Replay a matching stored memory sequence.
4. Explore using novelty and revisit-penalty scoring.

## Data and Persistence

- App settings are stored as JSON under the user's config directory.
- `app/settings_store.py` handles loading and saving persistent settings.
- Maps are stored as plain text files with metadata headers and a numeric grid.
- `app/map_format.py` parses, validates, serializes, and normalizes map files.

Map token format:

- `0`: empty
- `1`: wall
- `2`: food
- `3`: spawn marker

Spawn markers are authoring-time data. When a map is loaded into the simulator, spawns become initial creature positions on otherwise empty terrain.

## Debuggability

The codebase is designed to be inspectable while running.

- The details window exposes the currently selected creature's mode, actions, sense vector, recent steps, and stored memories.
- The grid can highlight selected creatures and render pheromone trails.
- The stats graph shows per-epoch progress and best-time markers for authored maps.
- The project includes a VS Code `launch.json` for debugging the main app, the map editor, and tests.

## Testing

- Tests are written with Python's built-in `unittest` framework.
- The current automated coverage focuses on simulation behavior such as exploration, line of sight, pheromone behavior, and loop detection.
- The main test file is `tests/test_simulation.py`.

Typical test command:

```bash
PYTHONPATH=. .venv/bin/pytest -q .
```

`pytest` is used as the test runner, while the assertions and test structure are based on `unittest.TestCase`.

## Launch and Environment

- `launch.sh` bootstraps `.venv`, installs requirements, and runs `python -m app.main`.
- `launch_editor.sh` does the same for `python -m app.editor_main`.
- Dependencies are intentionally minimal:
  - `PySide6`
  - `pyqtgraph`

## What This Stack Is Not

To avoid confusion, this repository does not currently use:

- PyTorch
- TensorFlow
- NumPy-heavy training code
- Gymnasium environments
- distributed training
- replay buffers in the usual deep RL sense
- a web frontend or backend API server

The project is better described as a desktop simulation and experimentation tool with RL-inspired memory and inheritance mechanics.
