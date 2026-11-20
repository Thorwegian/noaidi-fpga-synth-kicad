#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""test_points.py -- the test_points sheet: one test point on each global
net, two on ground. There is no TP17."""
from skidl import *

from global_nets import ESP_3V3, GND

from parts import test_point

TEST_POINTS = (("TP10", ESP_3V3), ("TP19", GND))

for ref, net in TEST_POINTS:
    test_point(net, ref)

if __name__ == "__main__":
    generate_netlist(file_="test_points.net")
