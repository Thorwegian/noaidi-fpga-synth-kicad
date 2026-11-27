#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""board.py -- the whole board: the four sheets, checked and written out.

Run from build/skidl/ with the environment of scripts/requirements.txt:

    KICAD10_SYMBOL_DIR=/usr/share/kicad/symbols ../../circuit/board.py

Writes board.net and net_classes.json there and rewrites docs/pins.md, after
holding the designators the sheets give against designators.toml.
board.net is the netlist as KiCad's Import Netlist takes it without
proposing a change to the board (kicad_netlist.py). Each sheet can be run
the same way on its own and writes <sheet>.net, SKiDL's own netlist.
"""
from skidl import *

import esp32
import tang_nano_20k
import test_points
import usb
import designators
import kicad_netlist
import net_classes
import pin_map

from parts import mounting_hole

# The case bolts the board down through four holes of its own, which are no
# part of a sheet and carry no net.
with SubCircuit("mounting_holes", tag="mounting_holes"):
    for ref in ("H1", "H2", "H3", "H4"):
        mounting_hole(ref)

designators.check()
ERC()
kicad_netlist.write("board.net")
net_classes.write()
pin_map.write()
