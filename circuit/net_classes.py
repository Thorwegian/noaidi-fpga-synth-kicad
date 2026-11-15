#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""net_classes.py -- the classes of nets: what a net carries decides how its
copper is laid.

A class gives the tracks of its nets their width and clearance, and their
vias their size, in millimetres, under the names KiCad's project file has
for them. A net is put in a class where it is made (global_nets.py for the
nets that cross sheets); a net in no class is in Default.

The netlist names each net's class. board.py writes the classes themselves
to net_classes.json beside it, and scripts/board_from_circuit.py puts both
into the KiCad project, where the router and the DRC read them.
"""
import json

from skidl import *

DEFAULT = NetClass("Default", track_width=0.2, clearance=0.2, via_diameter=0.6, via_drill=0.3,
                   diff_pair_width=0.2, diff_pair_gap=0.25)

# Supply and ground carry every part's current.
SUPPLY = NetClass("Power", track_width=0.4, clearance=0.2, via_diameter=1.2, via_drill=0.6,
                  diff_pair_width=0.2, diff_pair_gap=0.25)

# The USB data pair is meant to be 90 ohm between its two lines (Espressif's
# hardware design guidelines for the ESP32-S3). 0.3 mm tracks 0.2 mm apart
# come to about 87 ohm over the inner layer 0.21 mm below them
# (docs/requirements.md, The layers). 0.3 mm is also the width of the
# socket's pads, and is kept the whole way so that the two lines stay alike.
USB_DATA_PAIR = NetClass("USB", track_width=0.3, clearance=0.2, via_diameter=0.6, via_drill=0.3,
                         diff_pair_width=0.3, diff_pair_gap=0.2)


def write():
    classes = {name: {key: value for key, value in vars(net_class).items() if key not in ("name", "priority")}
               for name, net_class in default_circuit.netclasses.items()}
    with open("net_classes.json", "w", encoding="utf-8") as file:
        json.dump(classes, file, indent=2)
        file.write("\n")
