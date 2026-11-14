#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""usb.py -- the usb sheet as a SKiDL description (a trial).

Run from build/skidl/ with the environment of scripts/requirements.txt:

    KICAD10_SYMBOL_DIR=/usr/share/kicad/symbols ../../skidl/usb.py

Writes usb.net, usb.svg and a KiCad schematic into the current directory.
"""
import os
from skidl import *

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
lib_search_paths[KICAD10].append(REPO)

power_in = Part("noaidi-fpga-synth", "USB_C_Receptacle_USB2.0_16P", ref="J9",
                footprint="noaidi-fpga-synth:GCT_USB4085-GF-A_REVB")
cc1_pulldown = Part("Device", "R", ref="R13", value="5.1k",
                    footprint="Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal")
cc2_pulldown = Part("Device", "R", ref="R14", value="5.1k",
                    footprint="Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal")
shield_bead = Part("Device", "FerriteBead", ref="FB2",
                   footprint="Inductor_SMD:L_0805_2012Metric_Pad1.05x1.20mm_HandSolder")

ext_5v = Net("EXT_5V")
gnd = Net("GND")
usb_d_plus = Net("USB_D+")
usb_d_minus = Net("USB_D-")

ext_5v += power_in["VBUS"]
gnd += power_in["GND"], cc1_pulldown[2], cc2_pulldown[2], shield_bead[2]
usb_d_plus += power_in["D+"]
usb_d_minus += power_in["D-"]
power_in["CC1"] += cc1_pulldown[1]
power_in["CC2"] += cc2_pulldown[1]
power_in["SHIELD"] += shield_bead[1]
power_in["SBU1", "SBU2"] += NC

generate_netlist(file_="usb.net")
generate_svg(file_="usb")
# Without auto_stub the router gives up on this sheet (RoutingFailure).
generate_schematic(filepath=".", top_name="usb", auto_stub=True, retries=5)
