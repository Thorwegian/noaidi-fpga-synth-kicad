# Requirements for the base board

Copyright © 2026 Thor H. Linløkken <thj@thj.no>
License: CERN-OHL-S v2

What the board in this repository has to do, as agreed with Thor in
November 2026. The schematic and the layout are checked against this
file; a requirement that changes, changes here first.

## The instrument it belongs to

The synth is imagined as a desktop console unit with a front panel
that tilts a little toward the player. The **base board**, of which
this board is an early iteration, sits at the bottom of the enclosure.
A second board, attached to the tilted front panel, comes later.

The enclosure is not defined beyond that: it has no dimensions yet,
no decision on which edge the connectors sit at, and no mounting
points.

Control surfaces come later and are outside the scope of this board:
a front panel board, which is the central one, and an iPad app.

## What the board must do

1. **Carry the two modules on headers:** the Tang Nano 20K (the sound
   engine) and the ESP32-S3-DevKitC (MIDI, voices, presets, console).
2. **Two MIDI inputs** on DIN sockets, each isolated by an
   optocoupler: one for the keyboard, one for the development host.
3. **Analog audio out** through the Adafruit PCM510x DAC module, with
   its left, right and ground on a pin header (J13).
4. **Two S/PDIF coaxial outputs** on RCA sockets: the 96 kHz stream
   from FPGA pin 27 (J3) and the 48 kHz stream from FPGA pin 86 (J4).
   Each delivers 0.5 to 0.6 V into a 75 Ω receiver, through a divider
   of 220 Ω in series and 120 Ω to ground.
5. **The two S/PDIF signals straight from the FPGA pins on pin
   headers** (J5, J6), ahead of the dividers. The lab jig's USB audio
   interface has an optical input, and one of these signals may drive
   an LED there for the automated tests.
6. **Power from USB-C**, into each module's 5 V rail through its own
   ideal diode. The USB data pair goes to the ESP32.
7. **Buses on pin headers, for developing the front panel board:**
   the second SPI bus (J10), the two I2C buses (J8, J11), UART0 (J12)
   and I2S (J7).
8. **Test points** on the buses and the supply rails.

The S/PDIF outputs of requirements 4 and 5 are there because they are
very useful in the lab. They will not necessarily be kept in a final
design.

## How it is made

- Fabricated by JLCPCB, who also place the surface-mount parts.
- The modules, the DIN and RCA sockets and the pin headers are
  through-hole and soldered by hand: those connectors take a beating,
  and surface-mount versions are neither as durable nor as available.
- Everything else is surface-mount where a part exists.

## Not required of this board

- The front panel, or any control on the board itself.
- An optical output on the board: the lab jig takes its signal from
  the header of requirement 5.
- A fit to an enclosure, until the enclosure is defined.

## Open

- **Power for the front panel board.** The pin headers of requirement
  7 carry signals and ground only. The supply rails reach test points,
  not headers, so a board under development on those headers has no
  supply pin to take power from.
- **The current from FPGA pin 86** when the jig's LED hangs on its
  header at the same time as a receiver on the coaxial output. The
  divider alone draws 12.4 mA; the pin's largest drive setting is
  24 mA (GW2AR data sheet, `thirdparty/DS226-2.7E`, table 3-11).
- **The fixed positions:** which connectors sit at which edge, the
  board's outline and its mounting holes wait for the enclosure.
