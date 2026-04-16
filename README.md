# RLmini

RLmini is a PySide6 desktop simulation of creatures moving through a 2D grid world with walls, food, local memory, and between-epoch inheritance.

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

## Map Format

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

## Sample Maps

- [maps/sample_basic.map](/home/fayt64/github/RLmini/maps/sample_basic.map)
