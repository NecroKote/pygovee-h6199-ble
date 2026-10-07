"""
Color temperature table, 2000-9000 K.

Each kelvin step has two colors. The first one is the tint sent in a color
temperature frame, and a kelvin is looked up from either column when only a
color is known.
"""

from typing import TypeAlias

RGBColor: TypeAlias = tuple[int, int, int]

MIN_KELVIN = 2000
MAX_KELVIN = 9000

_TABLE: dict[int, tuple[str, str]] = {
    2000: ("FF8D0B", "FF8912"),
    2100: ("FF921D", "FF8E21"),
    2200: ("FF9829", "FF932C"),
    2300: ("FF9D33", "FF9836"),
    2400: ("FFA23C", "FF9D3F"),
    2500: ("FFA645", "FFA148"),
    2600: ("FFAA4D", "FFA54F"),
    2700: ("FFAE54", "FFA957"),
    2800: ("FFB25B", "FFAD5E"),
    2900: ("FFB662", "FFB165"),
    3000: ("FFB969", "FFB46B"),
    3100: ("FFBD6F", "FFB872"),
    3200: ("FFC076", "FFBB78"),
    3300: ("FFC37C", "FFBE7E"),
    3400: ("FFC682", "FFC184"),
    3500: ("FFC987", "FFC489"),
    3600: ("FFCB8D", "FFC78F"),
    3700: ("FFCE92", "FFC994"),
    3800: ("FFD097", "FFCC99"),
    3900: ("FFD39C", "FFCE9F"),
    4000: ("FFD5A1", "FFD1A3"),
    4100: ("FFD7A6", "FFD3A8"),
    4200: ("FFD9AB", "FFD5AD"),
    4300: ("FFDBAF", "FFD7B1"),
    4400: ("FFDDB4", "FFD9B6"),
    4500: ("FFDFB8", "FFDBBA"),
    4600: ("FFE1BC", "FFDDBE"),
    4700: ("FFE2C0", "FFDFC2"),
    4800: ("FFE4C4", "FFE1C6"),
    4900: ("FFE5C8", "FFE3CA"),
    5000: ("FFE7CC", "FFE4CE"),
    5100: ("FFE8D0", "FFE6D2"),
    5200: ("FFEAD3", "FFE8D5"),
    5300: ("FFEBD7", "FFE9D9"),
    5400: ("FFEDDA", "FFEBDC"),
    5500: ("FFEEDE", "FFECE0"),
    5600: ("FFEFE1", "FFEEE3"),
    5700: ("FFF0E4", "FFEFE6"),
    5800: ("FFF1E7", "FFF0E9"),
    5900: ("FFF3EA", "FFF2EC"),
    6000: ("FFF4ED", "FFF3EF"),
    6100: ("FFF5F0", "FFF4F2"),
    6200: ("FFF6F3", "FFF5F5"),
    6300: ("FFF7F7", "FFF6F8"),
    6400: ("FFF8F8", "FFF8FB"),
    6500: ("FFF9FB", "FFF9FD"),
    7000: ("F7F5FF", "F5F3FF"),
    7200: ("F3F3FF", "F0F1FF"),
    8000: ("E5E9FF", "E3E9FF"),
    8200: ("E3E8FF", "E0E7FF"),
    9000: ("D9E1FF", "D6E1FF"),
}


def _rgb(hex_color: str) -> RGBColor:
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


#: kelvin values of the table: every 100 K up to 6500, then 7000, 7200, 8000, 8200, 9000
COLOR_TEMPERATURES: tuple[int, ...] = tuple(sorted(_TABLE))

_FIRST = {k: _rgb(c1) for k, (c1, _) in _TABLE.items()}
_REVERSE: dict[RGBColor, int] = {}
for _kelvin in COLOR_TEMPERATURES:
    for _color in _TABLE[_kelvin]:
        _REVERSE.setdefault(_rgb(_color), _kelvin)


def nearest_color_temperature(kelvin: int) -> int:
    """
    Closest kelvin value of the table. Halfway values round down.

    :raises ValueError: outside 2000-9000
    """

    if not MIN_KELVIN <= kelvin <= MAX_KELVIN:
        raise ValueError(f"kelvin must be {MIN_KELVIN}-{MAX_KELVIN}")

    return min(COLOR_TEMPERATURES, key=lambda k: (abs(k - kelvin), k))


def tint_for_kelvin(kelvin: int) -> RGBColor:
    """The tint color sent with a kelvin value, which must be a table value"""

    try:
        return _FIRST[kelvin]
    except KeyError:
        raise ValueError(f"{kelvin} K is not a table value") from None


def kelvin_for_color(color: RGBColor) -> int | None:
    """Kelvin of a color that is in the table (either column), else `None`"""

    return _REVERSE.get(tuple(color))
