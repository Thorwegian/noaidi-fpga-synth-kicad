#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""esp32_minimal.py -- the ESP32-S3-WROOM-1 module with the least that
belongs to it: what stands between the bare module and a board that can be
programmed over four wires. Anything a board can do without is outside it.

The circuit is that of Espressif's ESP32-S3-DevKitC-1 v1.1, part for part
(docs/thirdparty/ESP32-S3-DevKitC-1_Reference_Design/), with the board's own
chip parts in place of Espressif's 0402s. What that board has beside the
module is left out: its regulator, its USB sockets with their ESD diodes, its
USB-to-UART bridge, its buttons and its LEDs.

No sheet uses the circuit: the board carries a bought DevKitC-1 as U1
(esp32.py). Run on its own, this file writes the circuit alone as
esp32_minimal.net, under the designators the parts have on Espressif's
board, so that the netlist can be held against that board.
"""
from skidl import *

from parts import capacitor, jlcpcb_part, resistor

# The variant is not decided: it is chosen when the module goes onto the
# board, from what JLCPCB has then. This one matches the boards in hand,
# 16 MB of flash and 8 MB of PSRAM (docs/esp32s3_hw678.md). Its PSRAM is
# octal and takes GPIO35, 36 and 37, which a variant without it leaves free.
MODULE_VARIANT = "ESP32-S3-WROOM-1-N16R8"
MODULE_LCSC = "C2913202"

# The GPIOs a sheet can ask for. The module has no pad for GPIO22 to 34, and
# GPIO0, 43 and 44 are the circuit's own: they come out as gpio0, u0txd and
# u0rxd.
SHEET_GPIOS = (*range(1, 22), *range(35, 43), *range(45, 49))

# The symbol names a pin IO<n>, but for these four, which it names by their
# first function.
PIN_OF_GPIO = {19: "USB_D-", 20: "USB_D+", 43: "TXD0", 44: "RXD0"}


def gpio_pin(module, number):
    return module[PIN_OF_GPIO.get(number, f"IO{number}")]


def switch_transistor(ref, tag):
    """An NPN that pulls a 10 kΩ pull-up low: any small one does, and the
    SS8050 is the 8050 in JLCPCB's basic library (Espressif fits LRC's L8050)."""
    return jlcpcb_part(Part("Transistor_BJT", "SS8050", ref=ref, tag=tag,
                            footprint="Package_TO_SOT_SMD:SOT-23"), "C2150")


@subcircuit
def esp32_minimal(gpios, module_ref, supply_link_ref, bulk_ref, bypass_ref, enable_pullup_ref,
                  enable_delay_ref, reset_switch_ref, reset_base_ref, reset_link_ref,
                  boot_switch_ref, boot_base_ref, boot_link_ref):
    """The module on a 3.3 V supply, programmed through four lines: UART0's
    two and a serial adapter's DTR and RTS. Returns what a sheet connects to,
    as SKiDL's documentation has a subcircuit do (Hierarchy, method 1):

        supply, gnd      the 3.3 V supply
        u0txd, u0rxd     UART0: the console, and the way into the flash
        dtr, rts         the serial adapter's two control lines
        en, gpio0        the two pins those lines pull, for a button
        gpio<n>          each GPIO whose number is in gpios

    The sheet names the GPIOs it uses because SKiDL puts every pin an
    interface holds on a net of its own, and a pin on a net cannot be marked
    as not connected: a GPIO that is not in gpios is marked so here, and one
    that is and gets nothing connected to it is an ERC warning.

    The supply reaches the module through a 0 Ω link, with 10 µF and 100 nF
    on the rail's side of it.

    EN is pulled up through 10 kΩ and held down by 1 µF while the supply
    rises. The two transistors need the same capacitor: esptool's
    documentation (Boot Mode Selection, Automatic Bootloader) asks for 1 µF
    to 10 µF from EN to ground for them to work reliably.

    The transistors turn DTR and RTS into EN and GPIO0, so that the program
    that writes the flash also resets the module into its download mode.
    Each has its base on one line and its emitter on the other, and conducts
    only while its base line is high and its emitter line low:

        DTR  RTS    EN    GPIO0
         1    1     1      1
         0    0     1      1
         1    0     0      1      reset
         0    1     1      0      download mode at the next reset

    A program that pulls both lines low as it opens the port therefore does
    nothing to the module, which wired straight to EN and GPIO0 it would hold
    in reset. The 0 Ω links stand between the collectors and the two pins.
    GPIO0 has no pull-up on the board, as on Espressif's: the chip's
    internal one holds it high.
    """
    not_on_the_module = sorted(set(gpios) - set(SHEET_GPIOS))
    if not_on_the_module:
        raise ValueError(f"esp32_minimal has no GPIO {not_on_the_module} for a sheet")

    module = jlcpcb_part(Part("RF_Module", "ESP32-S3-WROOM-1", ref=module_ref, tag="module",
                              value=MODULE_VARIANT, footprint="RF_Module:ESP32-S3-WROOM-1"),
                         MODULE_LCSC)
    supply_link = resistor(ref=supply_link_ref, value="0", tag="supply_link")
    bulk = capacitor(ref=bulk_ref, value="10u", tag="bulk")
    bypass = capacitor(ref=bypass_ref, value="100n", tag="bypass")
    enable_pullup = resistor(ref=enable_pullup_ref, value="10k", tag="enable_pullup")
    enable_delay = capacitor(ref=enable_delay_ref, value="1u", tag="enable_delay")
    reset_switch = switch_transistor(ref=reset_switch_ref, tag="reset_switch")
    reset_base = resistor(ref=reset_base_ref, value="10k", tag="reset_base")
    reset_link = resistor(ref=reset_link_ref, value="0", tag="reset_link")
    boot_switch = switch_transistor(ref=boot_switch_ref, tag="boot_switch")
    boot_base = resistor(ref=boot_base_ref, value="10k", tag="boot_base")
    boot_link = resistor(ref=boot_link_ref, value="0", tag="boot_link")

    module[:] += NC

    # The nets a sheet joins to its own carry no name here, so that they take the sheet's.
    supply, gnd, dtr, rts = Net(), Net(), Net(), Net()
    module_supply = Net("ESP_MODULE_3V3")
    module_supply.drive = POWER
    supply += supply_link[1], bulk[1], bypass[1]
    module_supply += supply_link[2], module["3V3"], enable_pullup[2]
    gnd += module["GND"], bulk[2], bypass[2], enable_delay[2]

    enable = Net("ESP_EN")
    enable += module["EN"], enable_pullup[1], enable_delay[1], reset_link[2]
    boot = Net("ESP_GPIO0")
    boot += gpio_pin(module, 0), boot_link[2]

    reset_base_drive = Net("ESP_RESET_BASE")
    reset_collector = Net("ESP_RESET_COLLECTOR")
    boot_base_drive = Net("ESP_BOOT_BASE")
    boot_collector = Net("ESP_BOOT_COLLECTOR")
    dtr += reset_base[1], boot_switch["E"]
    rts += boot_base[1], reset_switch["E"]
    reset_base_drive += reset_base[2], reset_switch["B"]
    reset_collector += reset_switch["C"], reset_link[1]
    boot_base_drive += boot_base[2], boot_switch["B"]
    boot_collector += boot_switch["C"], boot_link[1]

    return Interface(supply=supply, gnd=gnd,
                     u0txd=gpio_pin(module, 43), u0rxd=gpio_pin(module, 44),
                     dtr=dtr, rts=rts, en=enable, gpio0=boot,
                     **{f"gpio{number}": gpio_pin(module, number) for number in gpios})


if __name__ == "__main__":
    esp = esp32_minimal(gpios=(), module_ref="U4", supply_link_ref="R24", bulk_ref="C1",
                        bypass_ref="C2", enable_pullup_ref="R5", enable_delay_ref="C6",
                        reset_switch_ref="Q1", reset_base_ref="R10", reset_link_ref="R8",
                        boot_switch_ref="Q2", boot_base_ref="R12", boot_link_ref="R13",
                        tag="esp32_minimal")
    supply, gnd = Net("VCC_3V3"), Net("GND")
    supply += esp.supply
    gnd += esp.gnd
    for rail in (supply, gnd):
        rail.drive = POWER
    for port in ("u0txd", "u0rxd", "dtr", "rts"):
        line = Net(port.upper())
        line += esp[port]
    ERC()
    generate_netlist(file_="esp32_minimal.net")
