# Requirements for the base board

Copyright © 2026 Thor H. Linløkken <thj@thj.no>
License: CERN-OHL-S v2

What the board in this repository has to do, as agreed with Thor in
November 2026. The circuit and the layout are checked against this
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
   the output. This stream has no coaxial output: with a divider and
   the LED both on the pin, the divider adds 12.4 mA to the LED's
   current, the pin's largest drive setting is 24 mA (GW2AR data sheet,
   `thirdparty/DS226-2.7E`, table 3-11), and the prototype's LED
   circuit is noted at about 28 mA peaks.
6. **Both S/PDIF signals straight from the FPGA pins on pin headers**
   (J5, J6), to tap in the lab: the 96 kHz stream ahead of its
   divider, and the 48 kHz stream for the lab jig's LED.
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
  without Power Delivery: the path the circuit already has, with a
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
- The USB-C sockets are surface-mount and placed by JLCPCB. The
  through-hole rule is for the large connectors with a high insertion
  force; a USB-C socket is a small connector that is handled with care.
- Everything else is surface-mount where a part exists. The chip parts
  (resistors and capacitors) are 0805 on hand-solder footprints: JLCPCB
  places them, and the size keeps a board repairable by hand.

## What is printed on it

- **Every part's designator can be read on the assembled board.** It is
  outside every part's outline, on no pad, hole or via, clear of the
  other print, and beside its own part.
- **The lettering is 1.2 mm high with a 0.2 mm line.** JLCPCB prints
  characters from 1.0 mm high with a 0.15 mm line, calls smaller ones
  unidentifiable, and prefers a line a sixth of the height
  (https://jlcpcb.com/capabilities/pcb-capabilities, Legend).

## The layers

- **Four copper layers,** on JLCPCB's stackup JLC04161H-7628 for a
  1.6 mm board, which has 0.21 mm between each outer layer and the
  inner layer next to it (https://jlcpcb.com/impedance).
  `circuit/layers.toml` states what each carries:
  - front and back: the signals, with ground filled around them;
  - inner layer 1: `ESP_3V3`, one unbroken fill;
  - inner layer 2: `NANO_5V`, one unbroken fill.
- **Ground is one net everywhere.** A fill on a layer that also takes
  tracks is cut into pieces by them. The two ground fills are tied
  together by a via every 10 mm and by every through-hole ground pad,
  so that a piece of one is joined through the other.
- **A supply with a layer of its own reaches a pad through a via
  beside the pad,** and no track is laid for it.
- **The USB data pair is 0.3 mm tracks 0.2 mm apart,** which over a
  layer 0.21 mm below comes to about 87 Ω between the two lines by the
  microstrip approximation JLCPCB prints
  (https://jlcpcb.com/blog/standard-pcb-thickness), with their
  dielectric constant of 4.6. Espressif's hardware design guidelines
  for the ESP32-S3 ask for 90 Ω ±10 %. On a two-layer board, with the
  nearest layer 1.5 mm below, the same pair comes to about 143 Ω.
- **The USB data pair is laid as a pair:** its two tracks side by side
  on the front from the socket to the module, equally long, without a
  via, along the path `circuit/pair_paths.toml` states. Espressif's
  guidelines ask for the pair in parallel at equal lengths, with as few
  vias as possible
  (https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html,
  USB).
- **No copper is filled under the ESP32 module's antenna,** on any
  layer.

## Where the parts sit

- **A pin header sits near what it belongs to:** the connector, the
  pin or the part its signals come from, so that an engineer finds it
  by looking when probing or connecting during development. A place
  near the board's edge is a plus; no distance to the edge is
  specified.
- **A connector at the board's edge sits where its plug can be
  inserted.** The mechanics set its distance to the edge, not a
  figure. The DIN and RCA sockets and the modules are placed by eye to
  that end, and their positions carry no precision; a USB-C socket
  sits on its maker's board-edge line (`circuit/fixed_positions.toml`).
- **The USB MIDI socket (J14) sits next to the power socket (J9), at
  the same edge.**

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
- **The USB data pair's impedance,** by JLCPCB's own calculator for
  the stackup: the figure above is an approximation, and the layer under
  the pair is `ESP_3V3`, where Espressif recommends ground.
- **The fixed positions:** which connectors sit at which edge, the
  board's outline and its mounting holes wait for the enclosure.
