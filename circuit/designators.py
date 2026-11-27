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

The sheets carry the designators too, where each part is made, and check()
holds the table against them.
"""
import collections
import os
import tomllib

from skidl import *
from skidl.node import HIER_SEP

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "designators.toml")


def tag_path(part):
    return part.hiername.lstrip(HIER_SEP)


def more_than_once(items):
    return sorted(item for item, count in collections.Counter(items).items() if count > 1)


def check():
    """Stop the build unless the table and the circuit name the same parts
    by the same designators, each path and each designator once."""
    with open(TABLE, "rb") as file:
        table = tomllib.load(file)
    parts = [(tag_path(part), str(part.ref)) for part in default_circuit.parts]
    circuit = dict(parts)

    faults = [f"{path} names more than one part in the circuit"
              for path in more_than_once(path for path, _ in parts)]
    faults += [f"{designator} is on more than one line of the table"
               for designator in more_than_once(table.values())]
    faults += [f"{path} is {circuit[path]} in the circuit and has no line in the table"
               for path in sorted(circuit.keys() - table.keys())]
    faults += [f"{path} is {table[path]} in the table and no part of the circuit"
               for path in sorted(table.keys() - circuit.keys())]
    faults += [f"{path} is {circuit[path]} in the circuit and {table[path]} in the table"
               for path in sorted(circuit.keys() & table.keys()) if circuit[path] != table[path]]
    if faults:
        raise SystemExit("designators.toml and the circuit disagree:\n  " + "\n  ".join(faults))
