#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""board.py -- the whole board: the four sheets, checked and written out.

Run from build/skidl/ with the environment of scripts/requirements.txt:

    KICAD10_SYMBOL_DIR=/usr/share/kicad/symbols ../../circuit/board.py

Writes board.net there and rewrites docs/pins.md. Each sheet can be run the
same way on its own and writes <sheet>.net.
"""
from skidl import *

import esp32
import tang_nano_20k
import test_points
import usb
import pin_map

ERC()
generate_netlist(file_="board.net")
pin_map.write()
