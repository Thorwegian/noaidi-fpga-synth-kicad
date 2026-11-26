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

from global_nets import (ESP_3V3, ESP_5V, EXT_5V, GND, I2C0_SCL, I2C0_SDA, I2C1_SCL, I2C1_SDA,
                         MIDI1_RX, MIDI2_RX, PANEL_UART_RX, PANEL_UART_TX, SPI2_CS_N,
                         SPI2_MISO, SPI2_MOSI, SPI2_SCLK, SPI3_CS_N, SPI3_MISO,
                         SPI3_MOSI, SPI3_SCLK, USB_D_MINUS, USB_D_PLUS)
from parts import PROJECT, capacitor, jlcpcb_part, pin_header, resistor, test_point


@subcircuit
def midi_input(name, uart_rx, supply, gnd, socket_ref, series_ref, clamp_ref, opto_ref,
               pullup_ref, bypass_ref, test_point_ref):
    """A DIN MIDI input: the current loop through an H11L1 optocoupler onto a
    UART receive pin. The H11L1's output is an open collector that pulls low
    while the LED is lit. Its pins have no names in the symbol: 1 is the LED's
    anode, 2 its cathode, 4 the output, 5 ground and 6 the supply; 3 is not
    connected inside the part.

    The socket's shielding contact is not connected: the MIDI specification
    (CA-033) allows no DC path from it to the receiver's ground on a MIDI In
    jack, so that a cable whose shield reaches the plug's barrel cannot join
    the sender's ground to this board's around the optocoupler."""
    socket = Part(PROJECT, "Lumberg_0105_05", ref=socket_ref, tag="socket",
                  footprint=f"{PROJECT}:Lumberg_0105_05")
    series = resistor(ref=series_ref, value="220", tag="series")
    clamp = jlcpcb_part(Part("Diode", "1N4148W", ref=clamp_ref, tag="clamp",
                             footprint="Diode_SMD:D_SOD-123"), "C81598")
    opto = jlcpcb_part(Part("Isolator", "H11L1", ref=opto_ref, tag="opto",
                            footprint="Package_DIP:SMDIP-6_W9.53mm"), "C78589")
    pullup = resistor(ref=pullup_ref, value="470", tag="pullup")
    bypass = capacitor(ref=bypass_ref, value="100n", tag="bypass")

    source = Net(f"{name}_SOURCE")
    led_anode = Net(f"{name}_LED_A")
    led_cathode = Net(f"{name}_LED_K")

    source += socket[4], series[1]
    led_anode += series[2], clamp["K"], opto[1]
    led_cathode += socket[5], clamp["A"], opto[2]
    uart_rx += opto[4], pullup[2]
    supply += opto[6], pullup[1], bypass[1]
    gnd += opto[5], bypass[2]
    socket[1, 2, 3] += NC
    opto[3] += NC
    test_point(uart_rx, test_point_ref)


@subcircuit
def i2c_port(scl, sda, supply, gnd, header_ref, scl_pullup_ref, sda_pullup_ref,
             scl_test_point_ref, sda_test_point_ref):
    """An I2C bus on a three-pin header, with its pull-ups. The header reads
    ground, clock, data: the clock sits next to ground."""
    header = pin_header(3, ref=header_ref, tag="header")
    scl_pullup = resistor(ref=scl_pullup_ref, value="4.7k", tag="scl_pullup")
    sda_pullup = resistor(ref=sda_pullup_ref, value="4.7k", tag="sda_pullup")

    gnd += header[1]
    scl += header[2], scl_pullup[2]
    sda += header[3], sda_pullup[2]
    supply += scl_pullup[1], sda_pullup[1]
    test_point(scl, scl_test_point_ref)
    test_point(sda, sda_test_point_ref)


@subcircuit
def led_chain(data, supply, gnd, buffer_ref, input_series_ref, pull_down_ref, series_ref,
              bulk_ref, led_refs, capacitor_refs):
    """Four RGBW pixels in a chain, for the light in the case.

    The chain hangs on the power socket's own rail, not on the module's 5 V:
    that rail reaches the module's USB sockets through a Schottky each
    (docs/esp32s3_hw678.md), so a chain on it is fed by whichever port is
    plugged in, the computer running the console included.

    The two rails can then disagree, and two parts keep that harmless. A 10 k
    pull-down holds the buffer's input at ground while the rail is live and the
    module is unpowered: an AHCT input must not float, or the pixels latch
    whatever they see at power-up. A 1 k in series limits what a live GPIO
    pushes into an unpowered buffer to about 2.6 mA, and the divider it makes
    with the pull-down leaves 3.0 V at the input, well over the 2.0 V an AHCT
    input needs.

    The buffer itself is what lifts the ESP32's 3.3 V to the pixels' domain.
    A pixel's input threshold is 0.65 x VDD (data sheet, section 9): 3.25 V at
    5.0 V and 3.41 V at 5.25 V, so a 3.3 V pin is inside the limit at nominal
    and outside it at the top of a USB port's range. KiCad's symbol for the
    buffer names none of its pins: 1 is the output enable, 2 the input, 3
    ground, 4 the output, 5 the supply.

    Each pixel reshapes what it receives and forwards it, so one buffer drives
    the whole chain. The 470 ohm resistor sits at the first input, where
    section 14 of the data sheet asks for it, and the last pixel's output is
    left open.
    """
    buffer = jlcpcb_part(Part("74xGxx", "74AHCT1G125", ref=buffer_ref, tag="level_shifter",
                              footprint="Package_TO_SOT_SMD:SOT-23-5"), "C7484")
    input_series = resistor(ref=input_series_ref, value="1k", tag="input_series")
    pull_down = resistor(ref=pull_down_ref, value="10k", tag="pull_down")
    series = resistor(ref=series_ref, value="470", tag="series")
    bulk = capacitor(ref=bulk_ref, value="10u", tag="bulk")

    buffer_input = Net("LED_BUFFER_IN")
    buffer_input += input_series[2], pull_down[1], buffer[2]
    data += input_series[1]
    pull_down[2] += gnd
    buffer[1] += gnd
    buffer[3] += gnd
    buffer[5] += supply
    supply += bulk[1]
    gnd += bulk[2]

    line = Net("LED_DATA_5V")
    line += buffer[4], series[1]
    pixel_input = Net("LED_DIN")
    pixel_input += series[2]

    for number, (led_ref, capacitor_ref) in enumerate(zip(led_refs, capacitor_refs), 1):
        led = jlcpcb_part(Part(PROJECT, "LED_SK6812MINIRGBW", ref=led_ref, tag=f"led_{number}",
                               footprint=f"{PROJECT}:LED_SK6812MINIRGBW_3.5x3.5mm"), "C7423106")
        decoupling = capacitor(ref=capacitor_ref, value="100n", tag=f"decoupling_{number}")

        led[1] += NC
        led[2] += gnd
        led[3] += pixel_input
        led[4] += supply
        led[6] += supply
        supply += decoupling[1]
        gnd += decoupling[2]
        if number == len(led_refs):
            led[5] += NC
        else:
            pixel_input = Net(f"LED_{number}_DOUT")
            pixel_input += led[5]


with SubCircuit("esp32", tag="esp32"):
    esp = Part(PROJECT, "ESP32-S3-DevKitC", ref="U1", tag="esp", pin_splitters="/",
               footprint=f"{PROJECT}:ESP32-S3-DevKitC")
    esp[:] += NC

    ESP_5V += esp["5V"]
    test_point(ESP_5V, "TP9")
    ESP_3V3 += esp["3V3"]
    GND += esp["GND"]

    USB_D_MINUS += esp["GPIO19"]
    USB_D_PLUS += esp["GPIO20"]

    SPI2_CS_N += esp["GPIO10"]
    SPI2_MOSI += esp["GPIO11"]
    SPI2_SCLK += esp["GPIO12"]
    SPI2_MISO += esp["GPIO13"]
    test_point(SPI2_CS_N, "TP1")
    test_point(SPI2_SCLK, "TP2")
    test_point(SPI2_MOSI, "TP3")
    test_point(SPI2_MISO, "TP4")

    spi3_header = pin_header(5, ref="J10", tag="spi3_header")
    GND += spi3_header[1]
    SPI3_CS_N += esp["GPIO6"], spi3_header[2]
    SPI3_SCLK += esp["GPIO8"], spi3_header[3]
    SPI3_MOSI += esp["GPIO7"], spi3_header[4]
    SPI3_MISO += esp["GPIO9"], spi3_header[5]
    test_point(SPI3_CS_N, "TP20")
    test_point(SPI3_SCLK, "TP21")
    test_point(SPI3_MOSI, "TP22")
    test_point(SPI3_MISO, "TP23")

    I2C0_SCL += esp["GPIO5"]
    I2C0_SDA += esp["GPIO4"]
    I2C1_SCL += esp["GPIO14"]
    I2C1_SDA += esp["GPIO17"]
    i2c_port(I2C0_SCL, I2C0_SDA, ESP_3V3, GND, header_ref="J8",
             scl_pullup_ref="R11", sda_pullup_ref="R12", scl_test_point_ref="TP25",
             sda_test_point_ref="TP24", tag="i2c0_port")
    i2c_port(I2C1_SCL, I2C1_SDA, ESP_3V3, GND, header_ref="J11",
             scl_pullup_ref="R15", sda_pullup_ref="R16", scl_test_point_ref="TP26",
             sda_test_point_ref="TP27", tag="i2c1_port")

    panel_uart_header = pin_header(4, ref="J12", tag="panel_uart_header")
    GND += panel_uart_header[1]
    PANEL_UART_TX += esp["GPIO15"], panel_uart_header[2]
    PANEL_UART_RX += esp["GPIO16"], panel_uart_header[3]
    # The panel board's supply, on the pin after the UART so that a three-pin
    # cable still fits the first three.
    ESP_5V += panel_uart_header[4]
    test_point(PANEL_UART_RX, "TP28")
    test_point(PANEL_UART_TX, "TP29")

    led_data = Net("LED_DATA")
    led_data += esp["GPIO21"]
    led_chain(led_data, EXT_5V, GND, buffer_ref="U8", input_series_ref="R20",
              pull_down_ref="R21", series_ref="R19", bulk_ref="C5",
              led_refs=("D3", "D4", "D5", "D6"), capacitor_refs=("C6", "C7", "C8", "C9"),
              tag="led_chain")

    # Whether the power socket is in, read as a voltage rather than as a logic
    # level, so the firmware can tell a charger from a computer's port: 1.52 V
    # at 4.75 V, 1.60 V at 5.0 V and 1.68 V at 5.25 V, at 340 uA.
    sense_top = resistor(ref="R22", value="10k", tag="sense_top")
    sense_bottom = resistor(ref="R23", value="4.7k", tag="sense_bottom")
    ext_5v_sense = Net("EXT_5V_SENSE")
    EXT_5V += sense_top[1]
    ext_5v_sense += sense_top[2], sense_bottom[1], esp["GPIO2"]
    GND += sense_bottom[2]

    MIDI1_RX += esp["GPIO18"]
    MIDI2_RX += esp["GPIO1"]
    midi_input("MIDI1", MIDI1_RX, ESP_3V3, GND, socket_ref="J1", series_ref="R1",
               clamp_ref="D1", opto_ref="U3", pullup_ref="R3", bypass_ref="C3",
               test_point_ref="TP16", tag="midi1_input")
    midi_input("MIDI2", MIDI2_RX, ESP_3V3, GND, socket_ref="J2", series_ref="R2",
               clamp_ref="D2", opto_ref="U4", pullup_ref="R4", bypass_ref="C4",
               test_point_ref="TP30", tag="midi2_input")

if __name__ == "__main__":
    generate_netlist(file_="esp32.net")
