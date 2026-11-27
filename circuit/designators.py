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
"""
import collections
import os
import tomllib

from skidl import *
from skidl.node import HIER_SEP

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "designators.toml")


def tag_path(part):
    return part.hiername.lstrip(HIER_SEP)


def read():
    """The board's table, path to designator."""
    with open(TABLE, "rb") as file:
        return tomllib.load(file)


def more_than_once(items):
    return sorted(item for item, count in collections.Counter(items).items() if count > 1)


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
