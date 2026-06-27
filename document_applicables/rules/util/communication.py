'''Utilities related to the module's I/O'''

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Color:
    red: int
    green: int
    blue: int

    def __post_init__(self):
        for color in self.red, self.green, self.blue:
            if color > 255 or color < 0:
                raise ValueError("Color must be between 0 and 255")
