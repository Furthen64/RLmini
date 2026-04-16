# TASK.md

This was the original TASK.md file that generated the absolute first version of the code.
Since then it's probably changed, so maybe delete this entire file.


## Project goal

Build a **Python 3.12** desktop application using **Qt Widgets** that simulates a 2D grid world with:
- walls
- food
- creatures
- empty walkable tiles

The focus of version 1 is:
1. clear visualization
2. easy debugging
3. episodic local memory per creature
4. between-epoch inheritance of memory
5. persistent app settings

Do **not** over-engineer this version. Prefer simple, explicit code over abstraction-heavy designs.

---

## Core design decisions already fixed

### World representation
Use exactly **one tile layer**.

Each tile must be exactly one of:

```python
EMPTY = 0
WALL = 1
FOOD = 2
CREATURE = 3
```

Out-of-bounds must always be treated as `WALL`.

### Creature sensing
Each creature senses the **8 neighboring tiles** around itself.

Use a fixed order for the sense vector and keep it consistent everywhere:

```text
NW, N, NE, W, E, SW, S, SE
```

The center tile is the creature itself and is **not** included in the sense vector.

So the sense vector is always length 8.

Example:

```python
[WALL, EMPTY, FOOD, EMPTY, EMPTY, WALL, CREATURE, EMPTY]
```

### Action set
For V1, use this action enum:

```python
UP = 0
DOWN = 1
LEFT = 2
RIGHT = 3
IDLE = 4
```

Do **not** store `EAT` as a learned memory action.

Food consumption is a **hard rule**, not a remembered action.

### Behavior priority order per tick
Each creature must decide in this order:

1. **Adjacent food override**
2. **Visible food pursuit**
3. **Memory replay**
4. **Explore**

### Matching rule
For V1, use **unweighted matching**.

```python
score = number_of_equal_cells / 8.0
```

Default threshold: `0.75`

### Memory structure
Each stored memory sequence contains **1 to 4 steps**.

### Action set
UP=0, DOWN=1, LEFT=2, RIGHT=3, IDLE=4

### Epoch model
Asexual reproduction between epochs. Top performers selected as parents.
