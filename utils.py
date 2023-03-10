import re

import markdown


def gen_placeholder(o: markdown.Component):
    placeholders = {}
    sections = o.get_parent_section().get_parents()
    for p in sections:
        placeholders[f's{p.level - 1}'] = p.number
    if hasattr(o, 'text'):
        placeholders['text'] = getattr(o, 'text')
    if hasattr(o, 'name'):
        placeholders['text'] = getattr(o, 'name')
    if hasattr(o, 'number'):
        placeholders['gi'] = getattr(o, 'number')
    return placeholders


def convert_color(name: str) -> str:
    value = name
    color_map = {
        "aqua": "#00ffff",
        "black": "#000000",
        "blue": "#0000ff",
        "fuchsia": "#ff00ff",
        "green": "#008000",
        "gray": "#808080",
        "lime": "#00ff00",
        "maroon": "#800000",
        "navy": "#000080",
        "olive": "#808000",
        "purple": "#800080",
        "red": "#ff0000",
        "silver": "#c0c0c0",
        "teal": "#008080",
        "white": "#ffffff",
        "yellow": "#ffff00",
    }
    name = name.lower()
    if name in color_map:
        value = color_map[name]
    if re.match(r'#[0-9a-fA-F]{6}', value) is None:
        raise Exception(f"unrecognized color {name}")
    return value
