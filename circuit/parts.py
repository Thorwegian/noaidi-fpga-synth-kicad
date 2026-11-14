#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""parts.py -- where the parts come from, and the ones used on more than one sheet."""
import os

from skidl import *

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
lib_search_paths[KICAD10].append(REPO)

PROJECT = "noaidi-fpga-synth"

resistor = Part("Device", "R", dest=TEMPLATE,
                footprint="Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal")
capacitor = Part("Device", "C", dest=TEMPLATE,
                 footprint="Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")
ideal_diode = Part("Power_Management", "LM66100DCK", dest=TEMPLATE,
                   footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6")


def pin_header(pins, **attributes):
    return Part("Connector", f"Conn_01x{pins:02d}_Pin",
                footprint=f"Connector_PinHeader_2.54mm:PinHeader_1x{pins:02d}_P2.54mm_Vertical",
                **attributes)


@subcircuit
def ideal_diode_supply(source, rail, gnd, diode_ref, capacitor_ref):
    """A supply onto a module's own rail through an LM66100 ideal diode.

    CE is tied to VOUT, the data sheet's always-on reverse current blocking:
    the diode opens when the rail is below the source and closes when the rail
    is held above it, as when the module runs from its own USB port.
    """
    diode = ideal_diode(ref=diode_ref, tag="diode")
    input_capacitor = capacitor(ref=capacitor_ref, value="1u", tag="input_capacitor")

    source += diode["VIN"], input_capacitor[1]
    rail += diode["VOUT"], diode["~{CE}"]
    gnd += diode["GND"], diode["ST"], input_capacitor[2]
    diode["NC"] += NC
