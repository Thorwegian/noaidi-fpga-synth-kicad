#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""test_points.py -- the test_points sheet: one test point on each global
net, two on ground. There is no TP17."""
from skidl import *

from global_nets import (ESP_3V3, ESP_5V, ESP_UART0_RX, ESP_UART0_TX, ESP_UART1_RX,
                         ESP_UART2_RX, EXT_5V, GND, I2C0_SCL, I2C0_SDA, I2C1_SCL, I2C1_SDA,
                         I2S_BCK, I2S_DATA, I2S_WS, NANO_3V3, NANO_5V, PCM_3V3, SPDIF0, SPDIF1,
                         SPI2_CS_N, SPI2_MISO, SPI2_MOSI, SPI2_SCLK, SPI3_CS_N, SPI3_MISO,
                         SPI3_MOSI, SPI3_SCLK)

TEST_POINTS = (("TP10", ESP_3V3), ("TP19", GND))

test_point = Part("Connector", "TestPoint", dest=TEMPLATE,
                  footprint="TestPoint:TestPoint_THTPad_D3.0mm_Drill1.5mm")
for ref, net in TEST_POINTS:
    net += test_point(ref=ref, tag=ref.lower())[1]

if __name__ == "__main__":
    generate_netlist(file_="test_points.net")
