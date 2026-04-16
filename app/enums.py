from enum import IntEnum


class Tile(IntEnum):
    EMPTY = 0
    WALL = 1
    FOOD = 2
    CREATURE = 3


class Action(IntEnum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    IDLE = 4


class CreatureMode(IntEnum):
    FOOD_DIRECT = 0
    MEMORY_REPLAY = 1
    EXPLORE = 2
