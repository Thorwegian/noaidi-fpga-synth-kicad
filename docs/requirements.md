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
   the ESP32's own USB data pair.
8. **Buses on pin headers, for developing the front panel board:**
   the second SPI bus (J10), the two I2C buses (J8, J11), UART0 (J12)
   and I2S (J7).
9. **Test points** on the buses and the supply rails.

The S/PDIF outputs are there because they are very useful in the lab.
They will not necessarily be kept in a final design.

## Power

Not settled; this part of the board may need a redesign.

- **Today** the prototype draws its power from two sources, the USB
  ports of the two modules.
- **Wanted, if the power budget permits:** the board works as a USB
  peripheral, powered from the same computer port that carries USB
  MIDI. The schematic does this: the USB-C socket's supply goes to
  each module's 5 V rail through an ideal diode of its own.
- **Several sources at once must not conflict.** With the full lab jig
  connected, the modules' own USB ports and the board's USB socket can
  all be powered at the same time.
- **The front panel board** may draw quite a bit of current and
  probably gets a power connector of its own, leaving the USB socket
  as the USB MIDI connection. Where its power comes from is undecided.

What is known of the budget: a USB 2.0 port supplies 500 mA by
default. The ESP32-S3 alone peaks at 340 mA while its radio transmits
(Espressif's data sheet). The Tang Nano 20K's draw has not been
measured.

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

- **Power**, as above: the budget, the sources and how they coexist,
  and the front panel board's supply. The pin headers of requirement 8
  carry signals and ground only; the supply rails reach test points,
  not headers.
- **The USB socket.** The part drawn (GCT USB4085, through-hole) may
  not be one JLCPCB can make or supply, and is expected to be
  replaced.
- **Whether the 48 kHz stream keeps its coaxial output (J4).** With
  the divider and the jig's LED both on FPGA pin 86, the divider adds
  12.4 mA to the LED's current; the pin's largest drive setting is
  24 mA (GW2AR data sheet, `thirdparty/DS226-2.7E`, table 3-11), and
  the prototype's LED circuit is noted at about 28 mA peaks.
- **The fixed positions:** which connectors sit at which edge, the
  board's outline and its mounting holes wait for the enclosure.
