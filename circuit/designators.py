#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""designators.py -- each part's designator on the board, by the path of tags
that leads to the part.

designators.toml is the table: "esp32.midi1_input.opto" = "U3". The path is
a part's name in the circuit: the tags of the sheet and the blocks it is made
in, then its own. SKiDL makes the part's tstamp from it, and it stays when a
part is renumbered. The designator is what is printed on the board, and what
KiCad links a footprint to its part by.

The sheets give no part a designator. assign() sets every part's from the
table, once the circuit is built and before anything is written from it.
Before that, update() gives a part that has no line the next free number,
and retires the designator of a line that has no part.
"""
import collections
import itertools
import os
import re
import tomllib

from skidl import *
from skidl.node import HIER_SEP

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "designators.toml")


def tag_path(part):
    return part.hiername.lstrip(HIER_SEP)


def letters_of(part):
    """The letters a part's designator begins with. The project's own
    symbols hold a whole designator where KiCad's hold the letters (U1)."""
    return part.ref_prefix.rstrip("0123456789")


def natural(designator):
    letters, digits = re.fullmatch(r"(\D*)(\d*)", designator).groups()
    return letters, int(digits or 0)


def load():
    with open(TABLE, "rb") as file:
        return tomllib.load(file)


def read():
    """The board's table: each part's designator by its path."""
    return load()["parts"]


def write(parts, retired):
    """The table with these lines, under the heading the file has."""
    with open(TABLE, encoding="utf-8") as file:
        heading = "".join(itertools.takewhile(lambda line: line.startswith("#"), file))
    retired_lines = "".join(f'    "{designator}",\n' for designator in sorted(retired, key=natural))
    with open(TABLE, "w", encoding="utf-8") as file:
        file.write(heading + f"\nretired = [{chr(10) + retired_lines if retired else ''}]\n\n[parts]\n"
                   + "".join(f'"{path}" = "{parts[path]}"\n' for path in sorted(parts)))


def more_than_once(items):
    return sorted(item for item, count in collections.Counter(items).items() if count > 1)


def update():
    """Bring the board's table up to the circuit, where that takes no decision.

    A part with no line gets the next free number of its letters: one above
    the highest that a part has or has had. A line with no part goes, and its
    designator is retired. With both at once the build stops: a part whose
    tag has changed looks like one part removed and another added, and it
    keeps its designator only if its line is given the new path by hand.
    """
    table = load()
    parts, retired = table["parts"], table["retired"]
    circuit = {tag_path(part): part for part in default_circuit.parts}
    added = [path for path in circuit if path not in parts]
    removed = sorted(parts.keys() - circuit.keys())
    in_use_and_retired = sorted(set(parts.values()) & set(retired), key=natural)
    if in_use_and_retired:
        raise SystemExit(f"designators.toml: {', '.join(in_use_and_retired)} is retired and on a part's line")
    if added and removed:
        raise SystemExit(
            "designators.toml and the circuit differ both ways:\n"
            + "".join(f"  {path} is {parts[path]} in the table and no part of the circuit\n" for path in removed)
            + "".join(f"  {path} is a part of the circuit and has no line in the table\n" for path in added)
            + "A part whose tag has changed keeps its designator when its line is given the new path.\n"
              "A part that is gone has its line removed and its designator added to retired.")
    if not added and not removed:
        return

    for path in removed:
        retired.append(parts.pop(path))
        print(f"designators.toml: {retired[-1]} is retired, {path} being gone")
    for path in added:
        letters = letters_of(circuit[path])
        numbers = [natural(designator)[1] for designator in (*parts.values(), *retired)
                   if re.fullmatch(re.escape(letters) + r"\d+", designator)]
        parts[path] = f"{letters}{max(numbers, default=0) + 1}"
        print(f"designators.toml: {path} is {parts[path]}")
    write(parts, retired)


def assign(table, every_line=True):
    """Give every part of the circuit its designator from the table.

    Stops unless each part has a line, no path names two parts and no
    designator is on two lines. every_line asks that each line has a part
    as well, which holds for the circuit the table is of and not for one
    sheet of it run on its own.
    """
    paths = [tag_path(part) for part in default_circuit.parts]
    faults = [f"{path} names more than one part of the circuit" for path in more_than_once(paths)]
    faults += [f"{designator} is on more than one line of the table"
               for designator in more_than_once(table.values())]
    faults += [f"{path} is a part of the circuit and has no line in the table"
               for path in sorted(set(paths) - table.keys())]
    if every_line:
        faults += [f"{path} is {table[path]} in the table and no part of the circuit"
                   for path in sorted(table.keys() - set(paths))]
    if faults:
        raise SystemExit("the table of designators and the circuit disagree:\n  "
                         + "\n  ".join(faults))

    # SKiDL has numbered every part as it was made, and its setter alters a
    # designator that another part still holds: all are cleared before any
    # is set.
    for part in default_circuit.parts:
        del part.ref
    for part, path in zip(default_circuit.parts, paths):
        part.ref = table[path]
        if part.ref != table[path]:
            raise SystemExit(f"{path} is {table[path]} in the table and SKiDL made it {part.ref}")
