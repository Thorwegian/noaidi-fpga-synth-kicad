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
a front panel board, which is the central one, and an iPad app. The
front panel board will have a full colour display of its own, probably
with an ARM processor to drive the user interface.

## What the board must do

1. **Carry the two modules on headers:** the Tang Nano 20K (the sound
   engine) and the ESP32-S3-DevKitC (MIDI, voices, presets, console).
2. **Two MIDI inputs** on DIN sockets, each isolated by an
   optocoupler: one for the keyboard, one for the development host.
3. **Analog audio out** through the Adafruit PCM510x DAC module, with
   its left, right and ground on a pin header (J13).
4. **The 96 kHz S/PDIF stream on a coaxial output** (FPGA pin 27, RCA
   socket J3): the listening path, into the Focusrite interface. It
   delivers 0.5 to 0.6 V into a 75 Ω receiver, through a divider of
   220 Ω in series and 120 Ω to ground.
5. **The 48 kHz S/PDIF stream for the lab's optical capture** (FPGA
   pin 86): it drives an LED into the optical input of the lab
   computer's USB audio interface, which the automated tests record
   from. On the prototype that is 68 Ω and a red LED in parallel with
   the output. The schematic also gives this stream a coaxial output
   (J4) with the same divider; it may not need to be one.
6. **Both S/PDIF signals straight from the FPGA pins on pin headers**
   (J5, J6), ahead of the dividers, so the lab jig's LED can hang
   there.
7. **A USB connection to a computer** as a USB MIDI class device, on
   the ESP32's own USB data pair, through a USB-C socket of its own.
   That socket's supply pin feeds no rail.
8. **Buses on pin headers, for developing the front panel board:**
   the second SPI bus (J10), the two I2C buses (J8, J11), UART0 (J12)
   and I2S (J7).
9. **Test points** on the buses and the supply rails.

The S/PDIF outputs are there because they are very useful in the lab.
They will not necessarily be kept in a final design.

## Power

- **The main power connector is a USB-C socket of its own**, at 5 V,
  without Power Delivery: the path the schematic already has, with a
  5.1 kΩ resistor on each CC pin, from the socket's supply to each
  module's 5 V rail through an ideal diode of its own. A USB-C source
  can offer up to 3 A this way, 15 W.
- **The USB MIDI socket is a second USB-C socket** (requirement 7).
  It carries data only, so the board has one power entry.
- **The front panel board is powered from the base board:** power is
  forwarded to it board to board from the main power connector. It
  has no supply or power connector of its own, and it may draw quite
  a bit of current.
- **Several sources at once must not conflict.** On the prototype the
  power comes from the two modules' own USB ports, and with the full
  lab jig connected those ports and the board's power socket can all
  be powered at the same time.

The budget is a guess until parts are picked and the prototype is
measured: about 1 A for the base board and about 1 A for the front
panel board, 10 W together, both upper bounds. A USB 2.0 port supplies
500 mA by default, so a computer's port does not run the instrument.

## How it is made

- Fabricated by JLCPCB, who also place the surface-mount parts.
- The modules, the DIN and RCA sockets and the pin headers are
  through-hole and soldered by hand: those connectors take a beating,
  and surface-mount versions are neither as durable nor as available.
- Everything else is surface-mount where a part exists.

## Not required of this board

- The front panel, or any control on the board itself.
- An optical transmitter on the board: the lab jig's LED hangs on the
  header of requirement 6.
- A fit to an enclosure, until the enclosure is defined.

## Open

- **Power:** the measured budget, and the board-to-board path that
  forwards power to the front panel board. The pin headers of
  requirement 8 carry signals and ground only; the supply rails reach
  test points, not headers.
- **What the board does on a weak supply.** Through a USB-A to USB-C
  cable, or from a computer's port, the source may offer only 0.5 to
  1.5 A.
- **The USB-C sockets' part.** The one drawn (GCT USB4085,
  through-hole) may not be one JLCPCB can make or supply, and is
  expected to be replaced.
- **Whether the 48 kHz stream keeps its coaxial output (J4).** With
  the divider and the jig's LED both on FPGA pin 86, the divider adds
  12.4 mA to the LED's current; the pin's largest drive setting is
  24 mA (GW2AR data sheet, `thirdparty/DS226-2.7E`, table 3-11), and
  the prototype's LED circuit is noted at about 28 mA peaks.
- **The fixed positions:** which connectors sit at which edge, the
  board's outline and its mounting holes wait for the enclosure.
