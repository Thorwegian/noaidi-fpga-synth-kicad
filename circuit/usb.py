#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""usb.py -- the usb sheet: two USB-C sockets. One brings in EXT_5V, which
feeds each module's 5 V rail through an ideal diode of its own, and carries
no data; the other carries the ESP32's USB data pair, and its supply pins
feed no rail."""
from skidl import *

from global_nets import ESP_5V, EXT_5V, GND, NANO_5V, USB_D_MINUS, USB_D_PLUS
from parts import PROJECT, ideal_diode_supply, jlcpcb_part, resistor, test_point


@subcircuit
def usb_c_socket(name, gnd, socket_ref, cc1_pulldown_ref, cc2_pulldown_ref, supply=None,
                 supply_test_point_ref=None, rails=()):
    """A USB-C socket on a device: 5.1 kΩ from each CC pin to ground is what
    makes a USB-C source switch its 5 V on. The shell is on ground. Returns
    the socket, for the sheet to connect its supply and data pins. rails
    lists the rails the socket's supply feeds, each through an ideal diode
    of its own, as (rail, the designators ideal_diode_supply takes)."""
    socket = jlcpcb_part(Part("Connector", "USB_C_Receptacle_USB2.0_16P", ref=socket_ref,
                              tag="socket",
                              footprint=f"{PROJECT}:USB_C_Receptacle_HRO_TYPE-C-31-M-12"),
                         "C165948")
    cc1_pulldown = resistor(ref=cc1_pulldown_ref, value="5.1k", tag="cc1_pulldown")
    cc2_pulldown = resistor(ref=cc2_pulldown_ref, value="5.1k", tag="cc2_pulldown")

    cc1, cc2 = Net(f"{name}_CC1"), Net(f"{name}_CC2")

    gnd += socket["GND"], socket["SHIELD"], cc1_pulldown[2], cc2_pulldown[2]
    cc1 += socket["CC1"], cc1_pulldown[1]
    cc2 += socket["CC2"], cc2_pulldown[1]
    socket["SBU1", "SBU2"] += NC
    if supply is not None:
        supply += socket["VBUS"]
        test_point(supply, supply_test_point_ref)
    for rail, designators in rails:
        ideal_diode_supply(supply, rail, gnd, **designators)
    return socket


with SubCircuit("usb", tag="usb"):
    power_socket = usb_c_socket("USB_POWER", GND, socket_ref="J9", cc1_pulldown_ref="R13",
                                cc2_pulldown_ref="R14", supply=EXT_5V,
                                supply_test_point_ref="TP8",
                                rails=((ESP_5V, dict(diode_ref="U6", capacitor_ref="C2",
                                                     gnd_test_point_ref="TP18", tag="esp_5v_supply")),
                                       (NANO_5V, dict(diode_ref="U7", capacitor_ref="C1", tag="nano_5v_supply"))),
                                tag="power_socket")
    power_socket["D+", "D-"] += NC

    data_socket = usb_c_socket("USB_DATA", GND, socket_ref="J14", cc1_pulldown_ref="R17",
                               cc2_pulldown_ref="R18", tag="data_socket")
    USB_D_PLUS += data_socket["D+"]
    USB_D_MINUS += data_socket["D-"]
    # The data socket's supply pins feed no rail. They are one net all the
    # same: the footprint's pads for them lie on each other in pairs.
    Net("USB_DATA_VBUS").connect(data_socket["VBUS"])

if __name__ == "__main__":
    generate_netlist(file_="usb.net")
