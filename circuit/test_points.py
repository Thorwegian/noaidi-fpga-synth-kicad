#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""test_points.py -- the test_points sheet: the test points on supply nets
that are in no block, TP10 on ESP_3V3 and TP19 on ground. A supply net is
no one part's, so these two stand outside the blocks of the other sheets,
where every other test point is made beside what it probes. There is no
TP17."""
from skidl import *

from global_nets import ESP_3V3, GND

from parts import test_point

TEST_POINTS = (("TP10", ESP_3V3), ("TP19", GND))

for ref, net in TEST_POINTS:
    test_point(net, ref)

if __name__ == "__main__":
    generate_netlist(file_="test_points.net")
