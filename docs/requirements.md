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
   The ESP32's place takes Espressif's board, whose two pin rows are
   22.86 mm apart, and the HW-678 (`docs/esp32s3_hw678.md`), whose rows
   are 25.4 mm apart.
2. **Two MIDI inputs** on DIN sockets, each isolated by an
   optocoupler: one for the keyboard, one for the development host.
3. **Analog audio out** through the Adafruit PCM510x DAC module, with
   its left, right and ground on a pin header (J13).
4. **The 96 kHz S/PDIF stream on a coaxial output** (FPGA pin 27, RCA
   socket J3): the listening path, into the Focusrite interface. It
   delivers 0.5 to 0.6 V into a 75 Ω receiver, through a divider of
   220 Ω in series and 120 Ω to ground. A 100 nF capacitor in series
   at the pin keeps DC off the cable, as AKM draws it for a transmitter
   (AK4114 data sheet MS0098-E-04, page 22, figure 22:
   https://media.digikey.com/pdf/Data%20Sheets/AKM%20Semiconductor%20Inc.%20PDFs/AK4114.pdf).
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
   capacitor and divider, and the 48 kHz stream for the lab jig's LED.
7. **A USB connection to a computer** as a USB MIDI class device, on
   the ESP32's own USB data pair, through a USB-C socket of its own.
   That socket's supply pin feeds no rail. A divider on GPIO47 tells
   the firmware whether a host supplies it: a device with a supply of
   its own may pull D+ up only while the host's supply is there (USB
   2.0, sections 7.1.5.1 and 7.2.1), and Espressif's USB device stack
   reads that from a pin
   (https://docs.espressif.com/projects/esp-usb/en/latest/esp32s3/usb_device.html,
   Self-Powered Device).
8. **Buses on pin headers, for developing the front panel board:**
   the second SPI bus (J10), the two I2C buses (J8, J11), a UART (J12)
   and I2S (J7). The UART's header carries the ESP32 module's 5 V
   beside it, on the pin after the UART's three, for the panel board to
   run from.
9. **Test points** on the buses and the supply rails.
10. **A light in the case:** four warm-white addressable RGBW LEDs in a
    chain, driven from one ESP32 pin through a buffer, on the power
    socket's 5 V, so that the charger pays for it and not the computer
    the console runs on. They draw at most 240 mA between them, at full
    white. A divider on GPIO2 tells the firmware whether that rail is
    in, and the data pin is driven only while it is: the buffer is dead
    with the rail, and a live pin would feed it through its input.

The S/PDIF outputs are there because they are very useful in the lab.
They will not necessarily be kept in a final design.

## Power

- **The main power connector is a USB-C socket of its own**, at 5 V,
  without Power Delivery: the path the circuit already has, with a
  5.1 kΩ resistor on each CC pin, from the socket's supply to each
  module's 5 V rail through an ideal diode of its own. A USB-C source
  can offer up to 3 A this way, 15 W.
- **The USB MIDI socket is a second USB-C socket** (requirement 7).
  It carries data only, and its supply pin is read and not drawn
  from, so the board has one power entry.
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
- The four LEDs are surface-mount and soldered by hand all the same:
  JLCPCB reviews an order that places an addressable LED after it is
  paid, and names its fee only then.
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

- **Two copper layers,** the front and the back of a 1.6 mm board.
  Each carries signals, with ground filled around them. The supplies
  run as tracks 0.4 mm wide.
- **Ground is one net everywhere.** A fill on a layer that also takes
  tracks is cut into pieces by them. The two ground fills are tied
  together by a via every 10 mm and by every through-hole ground pad,
  so that a piece of one is joined through the other.
- **A bypass capacitor is joined to the pins it serves by a track,**
  pad to pad on the front: the way from pin to capacitor does not run
  through a via, a fill and another via.
  Analog Devices' MT-101 (figure 6) has the capacitor at the supply pin
  with both connections as short as possible
  (https://www.analog.com/media/en/training-seminars/tutorials/MT-101.pdf),
  and Texas Instruments' notes on decoupling have it joined to the
  planes by vias and to the device's rail by a short thick track
  (https://www.ti.com/content/dam/videos/external-videos/en-us/9/3816841626001/6313253251112.mp4/subassets/notes-decoupling_capacitors.pdf).
- **The USB data pair is 0.3 mm tracks 0.2 mm apart.** With the back of
  the board 1.5 mm below, that comes to about 143 Ω between the two
  lines by the microstrip approximation JLCPCB prints
  (https://jlcpcb.com/blog/standard-pcb-thickness), with their
  dielectric constant of 4.6. Espressif's hardware design guidelines
  for the ESP32-S3 ask for 90 Ω ±10 % (Open).
- **The USB data pair is laid as a pair:** its two tracks side by side
  on the front from the socket to the module, equally long, without a
  via, straight from the one to the other. Espressif's guidelines ask
  for the pair in parallel at equal lengths, with as few vias as
  possible
  (https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html,
  USB).
- **No copper is filled under the ESP32 module's antenna,** on either
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
- **Related parts sit together.** Two large parts with many connections
  between them are neighbours. A part that is not at the board's edge
  sits in the cluster of the part at an edge that its block of the
  circuit has: around that part, the larger parts first, each beside
  what it connects to. A cluster is laid out before the board has a
  size, with the board's edge that part is at as a wall, and the outline
  follows from the clusters. A test point is in the block of what it
  probes, and so in that cluster. Where a part sits otherwise is free,
  and the small parts need no order of their own as long as they are
  packed well around the large ones.
- **A part at the board's edge stays at its edge and may sit anywhere
  along it,** where nothing below says otherwise. An order between two
  parts is stated as a constraint in `circuit/fixed_positions.toml`
  (one below, above, left of or right of the other); how far apart they
  end up is not.
- **The board has a section along each side.** The two MIDI sockets
  are at the top edge. Below them the ESP32 module lies across the
  board from the left edge; below it the two USB sockets are at the
  left edge, the power socket with the two ideal diodes that feed the
  modules' 5 V beside it, and, at the right edge, the Tang Nano with
  the DAC module below it. The S/PDIF socket is at the bottom edge, so
  that the Tang Nano and the two audio outputs are one section.
- **Related connectors at an edge sit together, and a group reads in
  its order from that edge.** Connectors that form a group (port 1 and
  port 2, port A and port B, input L and input R) are next to each
  other, in that order from left to right for a person facing the edge
  from outside the board: MIDI 1 (J1) is left of MIDI 2 (J2) seen from
  the top edge.
- **The ESP32 module's USB ports face the board's edge, so its antenna
  lies over the board.** The module has its ports at one end and its
  antenna at the other, and a plug has to reach the ports. Espressif's
  hardware design guidelines for the ESP32-S3 ask for a module's
  antenna outside the base board, or else its feed point as close to
  the board's edge as possible
  (https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html,
  Positioning a module on a base board). Three things make up for it:
  the module sits on headers, away from the board; no copper is filled
  under the antenna on either layer (The layers); and what the guidelines
  want kept away from the antenna is kept away from it.
- **The USB data pair and its socket stay 15 mm or more from the
  antenna's area.** The same guidelines (RF): "the USB port,
  USB-to-serial chip, UART signal lines (including traces, vias, test
  points, header pins, etc.) must be as far away from the antenna as
  possible". They give no distance for it; 15 mm is the clearance they
  recommend around the antenna inside a housing, taken here as the
  least. `circuit/antennas.toml` states the nets and the distance,
  `scripts/board_from_circuit.py` puts no part of those nets nearer,
  and KiCad's DRC reports a pad, a track or a via of them that is
  (`noaidi-fpga-synth.kicad_dru`).
- **The two USB sockets sit at the left edge, below the ESP32 module,**
  at the end of the module its own USB ports are at and the far end
  from its antenna. The USB MIDI socket (J14) is the upper one, next to
  the module's USB pins its data pair ends in; the power socket (J9) is
  below it and carries no data.

## Not required of this board

- The front panel, or any control on the board itself.
- An optical transmitter on the board: the lab jig's LED hangs on the
  header of requirement 6.
- A fit to an enclosure, until the enclosure is defined.

## Open

- **Power:** the measured budget. The front panel board is fed from
  `ESP_5V` on J12, the UART header; the headers of requirement 8 other
  than J12 carry signals and ground only, and the supply rails reach
  test points, not headers.
- **What the board does on a weak supply.** Through a USB-A to USB-C
  cable, or from a computer's port, the source may offer only 0.5 to
  1.5 A.
- **The USB data pair's impedance:** about 143 Ω by the approximation
  in The layers, where Espressif asks for 90 Ω ±10 %. The link is
  full-speed USB, 12 Mbit/s (`docs/thirdparty/esp-dev-kits-en-master-esp32s3.pdf`:
  "full-speed USB OTG interface, compliant with the USB 1.1
  specification"), over 25 mm of track. Whether the difference has an
  effect on it is not measured.
- **A transformer at the S/PDIF socket.** AKM and Cirrus draw one
  after the divider (AK4114 data sheet, figure 22; CS8406 data sheet
  DS580F3, page 35, figure 14:
  https://www.farnell.com/datasheets/88462.pdf), and the board has
  none: its ground reaches the receiver's through the cable's shield.
  Whether that loop is heard through the Focusrite interface is not
  measured.
- **The fixed positions:** which connectors sit at which edge, the
  board's outline and where its four mounting holes sit wait for the
  enclosure.
- **The radio's range with the antenna over the board** is not
  measured. Espressif's guidelines ask for the end product to be
  tested for throughput and communication range.
