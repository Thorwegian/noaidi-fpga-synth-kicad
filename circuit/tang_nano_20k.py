#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""tang_nano_20k.py -- the tang_nano_20k sheet: the FPGA module, the DAC module,
the 96 kHz S/PDIF stream's coaxial output and the 48 kHz stream's header.

The FPGA's pins are named as on the symbol, chip pin number first
(27_IOB8A is chip pin 27), the number the gateware's constraints use.
"""
from skidl import *

from global_nets import (EXT_5V, GND, I2S_BCK, I2S_DATA, I2S_WS, NANO_3V3, NANO_5V, PCM_3V3,
                         SPDIF0, SPDIF1, SPI2_CS_N, SPI2_MISO, SPI2_MOSI, SPI2_SCLK)
from parts import PROJECT, ideal_diode_supply, pin_header, resistor


@subcircuit
def spdif_output(stream, gnd, series_ref, shunt_ref, socket_ref, tap_ref):
    """One S/PDIF stream to an RCA socket through a 220/120 divider, with the
    undivided signal on a header ahead of it."""
    series = resistor(ref=series_ref, value="220", tag="series")
    shunt = resistor(ref=shunt_ref, value="120", tag="shunt")
    socket = Part("Connector", "Conn_Coaxial", ref=socket_ref, tag="socket",
                  footprint=f"{PROJECT}:RCA_Kycon_KLPX-0848A")
    tap = pin_header(2, ref=tap_ref, tag="tap")
    coax = Net(f"{stream.name}_COAX")

    stream += series[1], tap[2]
    coax += series[2], shunt[1], socket["In"]
    gnd += shunt[2], socket["Ext"], tap[1]


with SubCircuit("tang_nano_20k", tag="tang_nano_20k"):
    fpga = Part(PROJECT, "Tang_Nano_20K", ref="U2", tag="fpga",
                footprint=f"{PROJECT}:DIP-40_TangNano20K")
    dac = Part(PROJECT, "Adafruit_PCM510x", ref="U5", tag="dac",
               footprint=f"{PROJECT}:Adafruit_PCM510x")
    fpga[:] += NC
    dac["DE", "MCK", "MU"] += NC

    ideal_diode_supply(EXT_5V, NANO_5V, GND, diode_ref="U7", capacitor_ref="C2",
                       tag="nano_5v_supply")
    NANO_5V += fpga["5V"], dac["VIN"]
    NANO_3V3 += fpga[25]
    PCM_3V3 += dac["3V"]
    GND += fpga["GND"], dac["GND"]

    SPI2_CS_N += fpga["28_IOB8B"]
    SPI2_SCLK += fpga["25_IOB6A"]
    SPI2_MOSI += fpga["26_IOB6B"]
    SPI2_MISO += fpga["29_IOB14A"]

    i2s_tap = pin_header(4, ref="J7", tag="i2s_tap")
    GND += i2s_tap[1]
    I2S_WS += fpga["55_IOR36B"], dac["WSEL"], i2s_tap[2]
    I2S_BCK += fpga["56_IOR36A"], dac["BCK"], i2s_tap[3]
    I2S_DATA += fpga["54_IOR38A"], dac["DIN"], i2s_tap[4]

    SPDIF0 += fpga["27_IOB8A"]
    SPDIF1 += fpga["86_IOT4A"]
    spdif_output(SPDIF0, GND, series_ref="R7", shunt_ref="R8", socket_ref="J3", tap_ref="J5",
                 tag="spdif0_output")
    # The 48 kHz stream has no coaxial output: its pin drives the lab's LED
    # from this header, and cannot drive a divider as well.
    lab_capture_tap = pin_header(2, ref="J6", tag="lab_capture_tap")
    GND += lab_capture_tap[1]
    SPDIF1 += lab_capture_tap[2]

    analog_out = pin_header(3, ref="J13", tag="analog_out")
    dac_out_g, dac_out_l, dac_out_r = Net("DAC_OUT_G"), Net("DAC_OUT_L"), Net("DAC_OUT_R")
    dac_out_g += dac["G"], analog_out[1]
    dac_out_l += dac["Lout"], analog_out[2]
    dac_out_r += dac["Rout"], analog_out[3]

    filter_jumper = Part("Jumper", "Jumper_2_Open", ref="JP1", tag="filter_jumper",
                         footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
    format_jumper = Part("Jumper", "Jumper_2_Open", ref="JP2", tag="format_jumper",
                         footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical")
    dac_fil, dac_fm = Net("DAC_FIL"), Net("DAC_FM")
    PCM_3V3 += filter_jumper["A"], format_jumper["A"]
    dac_fil += dac["FIL"], filter_jumper["B"]
    dac_fm += dac["FM"], format_jumper["B"]

if __name__ == "__main__":
    generate_netlist(file_="tang_nano_20k.net")
