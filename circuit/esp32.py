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

import designators
from global_nets import (ESP_3V3, ESP_5V, EXT_5V, GND, I2C0_SCL, I2C0_SDA, I2C1_SCL, I2C1_SDA,
                         MIDI1_RX, MIDI2_RX, PANEL_UART_RX, PANEL_UART_TX, SPI2_CS_N,
                         SPI2_MISO, SPI2_MOSI, SPI2_SCLK, SPI3_CS_N, SPI3_MISO,
                         SPI3_MOSI, SPI3_SCLK, USB_D_MINUS, USB_D_PLUS, USB_DATA_VBUS)
from parts import PROJECT, capacitor, hand_soldered_part, jlcpcb_part, pin_header, resistor, test_point


@subcircuit
def midi_input(name, uart_rx, supply, gnd):
    """A DIN MIDI input: the current loop through an H11L1 optocoupler onto a
    UART receive pin. The H11L1's output is an open collector that pulls low
    while the LED is lit. Its pins have no names in the symbol: 1 is the LED's
    anode, 2 its cathode, 4 the output, 5 ground and 6 the supply; 3 is not
    connected inside the part.

    The socket's shielding contact is not connected: the MIDI specification
    (CA-033) allows no DC path from it to the receiver's ground on a MIDI In
    jack, so that a cable whose shield reaches the plug's barrel cannot join
    the sender's ground to this board's around the optocoupler."""
    socket = Part(PROJECT, "Lumberg_0105_05", tag="socket",
                  footprint=f"{PROJECT}:Lumberg_0105_05")
    series = resistor(value="220", tag="series")
    clamp = jlcpcb_part(Part("Diode", "1N4148W", tag="clamp",
                             footprint="Diode_SMD:D_SOD-123"), "C81598")
    opto = jlcpcb_part(Part("Isolator", "H11L1", tag="opto",
                            footprint="Package_DIP:SMDIP-6_W9.53mm"), "C78589")
    pullup = resistor(value="470", tag="pullup")
    bypass = capacitor(value="100n", tag="bypass")

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
    test_point(uart_rx)


@subcircuit
def i2c_port(scl, sda, supply, gnd):
    """An I2C bus on a three-pin header, with its pull-ups. The header reads
    ground, clock, data: the clock sits next to ground."""
    header = pin_header(3, tag="header")
    scl_pullup = resistor(value="4.7k", tag="scl_pullup")
    sda_pullup = resistor(value="4.7k", tag="sda_pullup")

    gnd += header[1]
    scl += header[2], scl_pullup[2]
    sda += header[3], sda_pullup[2]
    supply += scl_pullup[1], sda_pullup[1]
    test_point(scl)
    test_point(sda)


@subcircuit
def led_chain(data, supply, gnd, pixels):
    """RGBW pixels in a chain, for the light in the case.

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
    buffer = jlcpcb_part(Part("74xGxx", "74AHCT1G125", tag="level_shifter",
                              footprint="Package_TO_SOT_SMD:SOT-23-5"), "C7484")
    input_series = resistor(value="1k", tag="input_series")
    pull_down = resistor(value="10k", tag="pull_down")
    series = resistor(value="470", tag="series")
    bulk = capacitor(value="10u", tag="bulk")

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

    for number in range(1, pixels + 1):
        # Soldered by hand: JLCPCB reviews an order that places an addressable
        # LED after it is paid, and names the fee only then.
        led = hand_soldered_part(Part(PROJECT, "LED_SKC6812RGBW", tag=f"led_{number}",
                                      footprint=f"{PROJECT}:LED_SKC6812RGBW_5.0x4.85mm"))
        decoupling = capacitor(value="100n", tag=f"decoupling_{number}")

        led["GND"] += gnd
        led["DIN"] += pixel_input
        led["VDD"] += supply
        supply += decoupling[1]
        gnd += decoupling[2]
        if number == pixels:
            led["DOUT"] += NC
        else:
            pixel_input = Net(f"LED_{number}_DOUT")
            pixel_input += led["DOUT"]


@subcircuit
def supply_sense(supply, sense, gnd, top_value, bottom_value):
    """A supply divided down onto a pin, for the firmware to read whether it
    is in. The top resistor is all that stands between the supply and the pin
    while the module is unpowered, so its value bounds what flows into it."""
    divider_top = resistor(value=top_value, tag="divider_top")
    divider_bottom = resistor(value=bottom_value, tag="divider_bottom")

    supply += divider_top[1]
    sense += divider_top[2], divider_bottom[1]
    gnd += divider_bottom[2]


with SubCircuit("esp32", tag="esp32"):
    esp = Part(PROJECT, "ESP32-S3-DevKitC", tag="esp", pin_splitters="/",
               footprint=f"{PROJECT}:ESP32-S3-DevKitC")
    esp[:] += NC

    ESP_5V += esp["5V"]
    test_point(ESP_5V)
    ESP_3V3 += esp["3V3"]
    GND += esp["GND"]

    USB_D_MINUS += esp["GPIO19"]
    USB_D_PLUS += esp["GPIO20"]

    SPI2_CS_N += esp["GPIO10"]
    SPI2_MOSI += esp["GPIO11"]
    SPI2_SCLK += esp["GPIO12"]
    SPI2_MISO += esp["GPIO13"]
    for line in (SPI2_CS_N, SPI2_SCLK, SPI2_MOSI, SPI2_MISO):
        test_point(line)

    spi3_header = pin_header(5, tag="spi3_header")
    GND += spi3_header[1]
    SPI3_CS_N += esp["GPIO6"], spi3_header[2]
    SPI3_SCLK += esp["GPIO8"], spi3_header[3]
    SPI3_MOSI += esp["GPIO7"], spi3_header[4]
    SPI3_MISO += esp["GPIO9"], spi3_header[5]
    for line in (SPI3_CS_N, SPI3_SCLK, SPI3_MOSI, SPI3_MISO):
        test_point(line)

    I2C0_SCL += esp["GPIO5"]
    I2C0_SDA += esp["GPIO4"]
    I2C1_SCL += esp["GPIO14"]
    I2C1_SDA += esp["GPIO17"]
    i2c_port(I2C0_SCL, I2C0_SDA, ESP_3V3, GND, tag="i2c0_port")
    i2c_port(I2C1_SCL, I2C1_SDA, ESP_3V3, GND, tag="i2c1_port")

    panel_uart_header = pin_header(4, tag="panel_uart_header")
    GND += panel_uart_header[1]
    PANEL_UART_TX += esp["GPIO15"], panel_uart_header[2]
    PANEL_UART_RX += esp["GPIO16"], panel_uart_header[3]
    # The panel board's supply, on the pin after the UART so that a three-pin
    # cable still fits the first three.
    ESP_5V += panel_uart_header[4]
    test_point(PANEL_UART_RX)
    test_point(PANEL_UART_TX)

    led_data = Net("LED_DATA")
    led_data += esp["GPIO21"]
    led_chain(led_data, EXT_5V, GND, pixels=4, tag="led_chain")

    # Whether the power socket is in, read as a voltage rather than as a logic
    # level, so the firmware can tell a charger from a computer's port: 1.52 V
    # at 4.75 V, 1.60 V at 5.0 V and 1.68 V at 5.25 V, at 340 uA.
    ext_5v_sense = Net("EXT_5V_SENSE")
    ext_5v_sense += esp["GPIO2"]
    supply_sense(EXT_5V, ext_5v_sense, GND, top_value="10k", bottom_value="4.7k",
                 tag="ext_5v_sense")

    # Whether a host supplies the data socket, read as a logic level. The board
    # has a supply of its own, and such a device has to know: it may pull D+ up
    # only while the host's supply is there (USB 2.0, sections 7.1.5.1 and
    # 7.2.1). Espressif asks for 0.75 x VDD on the pin at 4.4 V, which is
    # 2.48 V; 100 k over 150 k passes 0.6 of the supply: 2.64 V at 4.4 V, 3.00 V
    # at 5.0 V and 3.30 V at 5.5 V, the most a USB-C source gives. The module
    # is unpowered whenever the computer is plugged in and the charger is not,
    # and the 100 k then lets at most 55 uA into the dead pin.
    usb_data_vbus_sense = Net("USB_DATA_VBUS_SENSE")
    usb_data_vbus_sense += esp["GPIO47"]
    supply_sense(USB_DATA_VBUS, usb_data_vbus_sense, GND, top_value="100k", bottom_value="150k",
                 tag="usb_data_vbus_sense")

    MIDI1_RX += esp["GPIO18"]
    MIDI2_RX += esp["GPIO1"]
    midi_input("MIDI1", MIDI1_RX, ESP_3V3, GND, tag="midi1_input")
    midi_input("MIDI2", MIDI2_RX, ESP_3V3, GND, tag="midi2_input")

if __name__ == "__main__":
    designators.assign(designators.read(), every_line=False)
    generate_netlist(file_="esp32.net")
