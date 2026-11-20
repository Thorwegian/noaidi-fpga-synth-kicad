#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""global_nets.py -- the nets that cross sheets.

Every sheet imports its nets from here. SKiDL joins nets by object, not by
name: a second Net("GND") made elsewhere would become GND1 and stay apart.
"""
from skidl import *

from net_classes import SUPPLY, USB_DATA_PAIR

EXT_5V = Net("EXT_5V")
ESP_5V = Net("ESP_5V")
NANO_5V = Net("NANO_5V")
ESP_3V3 = Net("ESP_3V3")
NANO_3V3 = Net("NANO_3V3")
PCM_3V3 = Net("PCM_3V3")
GND = Net("GND")
for supply in (EXT_5V, ESP_5V, NANO_5V, ESP_3V3, NANO_3V3, PCM_3V3, GND):
    supply.drive = POWER
    supply.netclasses = SUPPLY

# KiCad takes the two for a differential pair by their names: one base name, ending in + and -.
USB_D_PLUS = Net("USB_D+")
USB_D_MINUS = Net("USB_D-")
for line in (USB_D_PLUS, USB_D_MINUS):
    line.netclasses = USB_DATA_PAIR

SPI2_CS_N = Net("SPI2_CS_N")
SPI2_SCLK = Net("SPI2_SCLK")
SPI2_MOSI = Net("SPI2_MOSI")
SPI2_MISO = Net("SPI2_MISO")

SPI3_CS_N = Net("SPI3_CS_N")
SPI3_SCLK = Net("SPI3_SCLK")
SPI3_MOSI = Net("SPI3_MOSI")
SPI3_MISO = Net("SPI3_MISO")

I2C0_SCL = Net("I2C0_SCL")
I2C0_SDA = Net("I2C0_SDA")
I2C1_SCL = Net("I2C1_SCL")
I2C1_SDA = Net("I2C1_SDA")

PANEL_UART_TX = Net("PANEL_UART_TX")
PANEL_UART_RX = Net("PANEL_UART_RX")

MIDI1_RX = Net("MIDI1_RX")
MIDI2_RX = Net("MIDI2_RX")

I2S_WS = Net("I2S_WS")
I2S_BCK = Net("I2S_BCK")
I2S_DATA = Net("I2S_DATA")

SPDIF0 = Net("SPDIF0")
SPDIF1 = Net("SPDIF1")
