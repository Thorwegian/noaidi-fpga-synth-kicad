#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""usb.py -- the usb sheet: the USB-C socket that brings in EXT_5V and the
ESP32's USB data pair."""
from skidl import *

from global_nets import EXT_5V, GND, USB_D_MINUS, USB_D_PLUS
from parts import PROJECT, resistor

with SubCircuit("usb", tag="usb"):
    power_in = Part(PROJECT, "USB_C_Receptacle_USB2.0_16P", ref="J9", tag="power_in",
                    footprint=f"{PROJECT}:GCT_USB4085-GF-A_REVB")
    cc1_pulldown = resistor(ref="R13", value="5.1k", tag="cc1_pulldown")
    cc2_pulldown = resistor(ref="R14", value="5.1k", tag="cc2_pulldown")
    shield_bead = Part("Device", "FerriteBead", ref="FB2", tag="shield_bead",
                       footprint="Inductor_SMD:L_0805_2012Metric_Pad1.05x1.20mm_HandSolder")

    usb_cc1, usb_cc2, usb_shield = Net("USB_CC1"), Net("USB_CC2"), Net("USB_SHIELD")

    EXT_5V += power_in["VBUS"]
    GND += power_in["GND"], cc1_pulldown[2], cc2_pulldown[2], shield_bead[2]
    USB_D_PLUS += power_in["D+"]
    USB_D_MINUS += power_in["D-"]
    usb_cc1 += power_in["CC1"], cc1_pulldown[1]
    usb_cc2 += power_in["CC2"], cc2_pulldown[1]
    usb_shield += power_in["SHIELD"], shield_bead[1]
    power_in["SBU1", "SBU2"] += NC

if __name__ == "__main__":
    generate_netlist(file_="usb.net")
