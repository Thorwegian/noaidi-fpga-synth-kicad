#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""test_points.py -- the test_points sheet: the test points on supply nets
that are in no block, one on ESP_3V3 and one on ground. A supply net is
no one part's, so these two stand outside the blocks of the other sheets,
where every other test point is made beside what it probes."""
from skidl import *

import designators
from global_nets import ESP_3V3, GND

from parts import test_point

for rail in (ESP_3V3, GND):
    test_point(rail)

if __name__ == "__main__":
    designators.assign(designators.read(), every_line=False)
    generate_netlist(file_="test_points.net")
