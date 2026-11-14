#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""esp32.py -- the esp32 sheet: the ESP32-S3 module, the two DIN MIDI inputs
and the bus headers.

The module's pins are named by GPIO number; the symbol's longer names
(GPIO4/ADC1_CH3) are split at the slash.
"""
from skidl import *

from global_nets import (ESP_3V3, ESP_5V, ESP_UART0_RX, ESP_UART0_TX, ESP_UART1_RX,
                         ESP_UART2_RX, EXT_5V, GND, I2C0_SCL, I2C0_SDA, I2C1_SCL, I2C1_SDA,
                         SPI2_CS_N, SPI2_MISO, SPI2_MOSI, SPI2_SCLK, SPI3_CS_N, SPI3_MISO,
                         SPI3_MOSI, SPI3_SCLK, USB_D_MINUS, USB_D_PLUS)
from parts import PROJECT, ideal_diode_supply, pin_header, resistor


@subcircuit
def midi_input(name, uart_rx, supply, gnd, socket_ref, series_ref, clamp_ref, opto_ref,
               base_ref, pullup_ref):
    """A DIN MIDI input: the current loop through a 6N138 optocoupler onto a
    UART receive pin. On the 6N138, pin 2 is the LED's anode and pin 3 its
    cathode (the symbol calls them C1 and C2)."""
    socket = Part("Connector", "DIN-5_180degree", ref=socket_ref, tag="socket",
                  footprint=f"{PROJECT}:Lumberg_0105_05")
    series = resistor(ref=series_ref, value="220", tag="series")
    clamp = Part("Diode", "1N4148", ref=clamp_ref, value="D", tag="clamp",
                 footprint="Diode_THT:D_DO-35_SOD27_P10.16mm_Horizontal")
    opto = Part("Isolator", "6N138", ref=opto_ref, tag="opto",
                footprint="Package_DIP:DIP-8_W7.62mm")
    base = resistor(ref=base_ref, value="4.7k", tag="base")
    pullup = resistor(ref=pullup_ref, value="220", tag="pullup")

    source = Net(f"{name}_SOURCE")
    led_anode = Net(f"{name}_LED_A")
    led_cathode = Net(f"{name}_LED_K")
    vo1 = Net(f"{name}_VO1")

    source += socket[4], series[1]
    led_anode += series[2], clamp["K"], opto[2]
    led_cathode += socket[5], clamp["A"], opto[3]
    vo1 += opto["VO1"], base[1]
    uart_rx += opto["VO2"], pullup[2]
    supply += opto["VCC"], pullup[1]
    gnd += opto["GND"], base[2]
    socket[1, 2, 3] += NC
    opto[1, 4] += NC


@subcircuit
def i2c_port(scl, sda, supply, gnd, header_ref, scl_pin, sda_pin, scl_pullup_ref,
             sda_pullup_ref):
    """An I2C bus on a three-pin header (pin 1 is ground), with its pull-ups."""
    header = pin_header(3, ref=header_ref, tag="header")
    scl_pullup = resistor(ref=scl_pullup_ref, value="4.7k", tag="scl_pullup")
    sda_pullup = resistor(ref=sda_pullup_ref, value="4.7k", tag="sda_pullup")

    gnd += header[1]
    scl += header[scl_pin], scl_pullup[2]
    sda += header[sda_pin], sda_pullup[2]
    supply += scl_pullup[1], sda_pullup[1]


with SubCircuit("esp32", tag="esp32"):
    esp = Part(PROJECT, "ESP32-S3-DevKitC", ref="U1", tag="esp", pin_splitters="/",
               footprint="PCM_Espressif:ESP32-S3-DevKitC")
    esp[:] += NC

    ideal_diode_supply(EXT_5V, ESP_5V, GND, diode_ref="U6", capacitor_ref="C1",
                       tag="esp_5v_supply")
    ESP_5V += esp["5V"]
    ESP_3V3 += esp["3V3"]
    GND += esp["GND"]

    USB_D_MINUS += esp["GPIO19"]
    USB_D_PLUS += esp["GPIO20"]

    SPI2_CS_N += esp["GPIO10"]
    SPI2_MOSI += esp["GPIO11"]
    SPI2_SCLK += esp["GPIO12"]
    SPI2_MISO += esp["GPIO13"]

    spi3_header = pin_header(5, ref="J10", tag="spi3_header")
    GND += spi3_header[1]
    SPI3_CS_N += esp["GPIO6"], spi3_header[2]
    SPI3_SCLK += esp["GPIO8"], spi3_header[3]
    SPI3_MOSI += esp["GPIO7"], spi3_header[4]
    SPI3_MISO += esp["GPIO9"], spi3_header[5]

    I2C0_SCL += esp["GPIO4"]
    I2C0_SDA += esp["GPIO5"]
    I2C1_SCL += esp["GPIO14"]
    I2C1_SDA += esp["GPIO17"]
    i2c_port(I2C0_SCL, I2C0_SDA, ESP_3V3, GND, header_ref="J8", scl_pin=3, sda_pin=2,
             scl_pullup_ref="R12", sda_pullup_ref="R11", tag="i2c0_port")
    i2c_port(I2C1_SCL, I2C1_SDA, ESP_3V3, GND, header_ref="J11", scl_pin=2, sda_pin=3,
             scl_pullup_ref="R15", sda_pullup_ref="R16", tag="i2c1_port")

    uart0_header = pin_header(3, ref="J12", tag="uart0_header")
    GND += uart0_header[1]
    ESP_UART0_TX += esp["GPIO15"], uart0_header[2]
    ESP_UART0_RX += esp["GPIO16"], uart0_header[3]

    ESP_UART1_RX += esp["GPIO18"]
    ESP_UART2_RX += esp["GPIO1"]
    midi_input("MIDI1", ESP_UART1_RX, ESP_3V3, GND, socket_ref="J1", series_ref="R1",
               clamp_ref="D1", opto_ref="U3", base_ref="R5", pullup_ref="R3", tag="midi1_input")
    midi_input("MIDI2", ESP_UART2_RX, ESP_3V3, GND, socket_ref="J2", series_ref="R2",
               clamp_ref="D2", opto_ref="U4", base_ref="R6", pullup_ref="R4", tag="midi2_input")

if __name__ == "__main__":
    generate_netlist(file_="esp32.net")
