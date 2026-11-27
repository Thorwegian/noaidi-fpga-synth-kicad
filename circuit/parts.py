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

# The parts JLCPCB places, by LCSC number. A value that is not listed here
# has no part chosen for it, and asking for it is an error.
RESISTOR_LCSC = {"0": "C17477", "120": "C17437", "220": "C17557", "470": "C17710",
                 "1k": "C17513", "4.7k": "C17673", "5.1k": "C27834", "10k": "C17414",
                 "100k": "C149504", "150k": "C17470"}
CAPACITOR_LCSC = {"100n": "C49678", "1u": "C28323", "10u": "C15850"}

# 0805 on the footprints with longer pads, so that a board can be repaired by hand.
resistor_template = Part("Device", "R", dest=TEMPLATE,
                         footprint="Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder")
capacitor_template = Part("Device", "C", dest=TEMPLATE,
                          footprint="Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder")
ideal_diode = Part("Power_Management", "LM66100DCK", dest=TEMPLATE,
                   footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6")
test_point_template = Part("Connector", "TestPoint", dest=TEMPLATE,
                           footprint="TestPoint:TestPoint_THTPad_D3.0mm_Drill1.5mm")
mounting_hole_template = Part("Mechanical", "MountingHole", dest=TEMPLATE,
                              footprint="MountingHole:MountingHole_3.2mm_M3")


def test_point(net):
    """A test point on the net, in the block of the circuit it is called in,
    and named after the net: spi2_cs_n_test_point.

    A test point is a bare pad: there is no part to buy for it and none to
    place, and KiCad's footprint for it says so with the two attributes."""
    point = test_point_template(tag=f"{net.name.lower()}_test_point")
    point.exclude_from_bom = True
    point.exclude_from_pos_files = True
    net += point[1]


def mounting_hole(tag):
    """A hole through the board for an M3 bolt, in the block of the circuit it
    is called in.

    It reaches no pin and no net, and there is no part to buy for it: it is
    KiCad's footprint of the hole and nothing else, so it is in neither the
    BOM nor the position files."""
    hole = mounting_hole_template(tag=tag)
    hole.exclude_from_bom = True
    hole.exclude_from_pos_files = True
    return hole


def jlcpcb_part(part, lcsc_number):
    """Mark a part as one JLCPCB places: its LCSC number goes in the LCSC field."""
    part.fields["LCSC"] = lcsc_number
    return part


def resistor(value, **attributes):
    return jlcpcb_part(resistor_template(value=value, **attributes), RESISTOR_LCSC[value])


def capacitor(value, **attributes):
    return jlcpcb_part(capacitor_template(value=value, **attributes), CAPACITOR_LCSC[value])


def pin_header(pins, **attributes):
    return Part("Connector", f"Conn_01x{pins:02d}_Pin",
                footprint=f"Connector_PinHeader_2.54mm:PinHeader_1x{pins:02d}_P2.54mm_Vertical",
                **attributes)


@subcircuit
def ideal_diode_supply(source, rail, gnd, gnd_test_point=False):
    """A supply onto a module's own rail through an LM66100 ideal diode.

    CE is tied to VOUT, the data sheet's always-on reverse current blocking:
    the diode opens when the rail is below the source and closes when the rail
    is held above it, as when the module runs from its own USB port.
    """
    diode = jlcpcb_part(ideal_diode(tag="diode"), "C2869734")
    input_capacitor = capacitor(value="1u", tag="input_capacitor")

    source += diode["VIN"], input_capacitor[1]
    rail += diode["VOUT"], diode["~{CE}"]
    gnd += diode["GND"], diode["ST"], input_capacitor[2]
    diode["NC"] += NC
    if gnd_test_point:
        test_point(gnd)
