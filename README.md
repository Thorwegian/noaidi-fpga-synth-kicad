# Noaidi FPGA Synth: the board

![A 3D render of the board from above at an angle](https://thj.no/synth/images/pcb-iso.jpg)

The KiCad project for the Noaidi synthesizer's circuit board, in
progress. The gateware and firmware that run on it live in
[Thorwegian/noaidi-fpga-synth](https://github.com/Thorwegian/noaidi-fpga-synth),
and the synth itself is presented at [thj.no/synth](https://thj.no/synth/).

## What is on it

![The prototype: a Tang Nano 20K and an ESP32-C3 Super Mini on perfboard, two DIN MIDI inputs through optocouplers, audio out on optical](https://thj.no/synth/images/prototype-board.jpg)

The perfboard prototype the board is based on. The board is a carrier for
two off-the-shelf modules and the few parts around them:

- **Tang Nano 20K** (U2) on headers: the sound engine.
- **ESP32-S3-DevKitC** (U1) on headers: MIDI, voices, presets and the
  console. The prototype runs an ESP32-C3 Super Mini; the board moves to
  the S3 (the firmware port is tracked in the synth repository,
  `docs/esp32s3_hw678.md`).
- **Two DIN MIDI inputs** (J1, J2) through H11L1 optocouplers (U3, U4):
  one for the keyboard, one for the dev host.
- **Audio out**: an Adafruit PCM510x I2S DAC module (U5) for analog, an
  RCA socket (J3) for S/PDIF.
- **Two USB-C sockets**: J9 for power, into each module's 5 V rail
  through an LM66100 ideal diode (U6, U7), and J14 for the ESP32's USB
  data pair, below the module's USB pins.
- Pin headers for the second SPI bus, two I2C buses, UART0, I2S and
  S/PDIF, and 29 test points.

Four layers, 130.85 × 121.25 mm. The modules, the DIN and RCA sockets,
the pin headers and the test points are through-hole; the other parts
are surface-mount.

The board is made from the circuit in text by script: see The circuit
in text, below.

## Layout

![The top of the board, rendered in 3D](https://thj.no/synth/images/pcb-top.jpg)

Front copper and silkscreen:

![Front copper and silkscreen](https://thj.no/synth/images/pcb-front.svg)

Back copper, mirrored:

![Back copper, mirrored](https://thj.no/synth/images/pcb-back.svg)

The three modules are rendered from 3D models of them, each standing in
a socket of two rows of female pin headers: the Tang Nano 20K from
Sipeed's model (`docs/thirdparty/Tang_Nano_20K_3921.step`), the ESP32
module from the model of the ESP32-S3-DevKitC-1-N8R2
(`docs/thirdparty/ESP32-S3-DEVKITC-1-N8R2.STEP`), the DAC module from
Adafruit's model (`docs/thirdparty/6250 PCM510x I2S DAC.step`). The
first two models have the module's pin headers; Adafruit's has none,
and KiCad's model of a pin header stands in under each of its rows.
Each module's underside is 11.04 mm above the base board: the 8.5 mm of
the socket, from KiCad's model of it, and the 2.54 mm body of the
module's pin headers.

The DIN sockets are rendered from Lumberg's model of the 8-pole
version of the socket, the 0105 08-1, with the solder pins of poles 6,
7 and 8 removed (`docs/thirdparty/lumberg_0105_05_from_08-1.stp`): the
5-pole 0105 05 has the same body and the other seven pins. The model's
pins are where Lumberg's drawing and the footprint have them, which
those of Lumberg's own model of the 0105 05 are not. The RCA socket
renders as a footprint only: the project has no 3D model of it.

The ESP32 module's model is from DigiKey's page for the part, the DAC
module's from Adafruit's repository of CAD files on GitHub
([adafruit/Adafruit_CAD_Parts](https://github.com/adafruit/Adafruit_CAD_Parts)),
and the 8-pole DIN socket's from
[Lumberg's page for the 0105](https://www.lumberg.com/en/products/product/0105).

## Files

The root folder holds the KiCad project, this README, `AGENTS.md` and
the licence. Scripts go in `scripts/`, documents in `docs/`.

- `AGENTS.md`: the rules for AI agents working in this repository, who
  does what, and where to start reading.
- `noaidi-fpga-synth.kicad_pro`, `.kicad_pcb`, `.kicad_dru`: the KiCad
  project, which holds the board and its design rules. It has no
  schematic: the circuit is in `circuit/`.
- `noaidi-fpga-synth.kicad_sym` and `noaidi-fpga-synth.pretty/`: the
  project's own symbols and footprints (the two modules, the DAC, the
  DIN sockets, the RCA and USB-C connectors). The ESP32 module's
  footprint is Espressif's, from
  [espressif/kicad-libraries](https://github.com/espressif/kicad-libraries)
  (CC-BY-SA 4.0 with the exception KiCad's own libraries have), with a
  keep-out for copper fills under the antenna.
- `scripts/render.sh`: regenerates the images above into `build/` with
  `kicad-cli` (KiCad 10); `scripts/crop.py` trims the 3D renders to the
  board
- `circuit/`: the circuit described in Python with SKiDL, one file
  per sheet (`usb.py`, `esp32.py`, `tang_nano_20k.py`, `test_points.py`),
  the nets that cross sheets in `global_nets.py`, the parts used on more
  than one sheet in `parts.py`, and `board.py` for the whole board. See
  The circuit in text, below.
- `scripts/netlist_summary.py`: compares netlists and the board by
  connectivity.
- `scripts/check.sh`: checks that the board is the circuit in text,
  counts the findings of KiCad's DRC with `scripts/rule_counts.py`, and
  measures the print against the pads with
  `scripts/silkscreen_clearance.py`.
- `scripts/board_from_circuit.py`: brings the board up to the circuit
  in text: removes, swaps and adds footprints, sets every pad's net and
  writes the net classes into the KiCad project.
- `circuit/net_classes.py`: the net classes, each with its track
  width, clearance and via.
- `circuit/fixed_positions.toml`: the constraints on where the parts
  sit (a part's edge, its side of another part, the part it moves as
  one with, the pads it sits level with), for
  `scripts/squeeze_board.py` and `scripts/board_from_circuit.py`.
- `circuit/layers.toml`: the copper layers and the fill of each, for
  `scripts/board_from_circuit.py`.
- `circuit/antennas.toml`: which nets stay away from the ESP32 module's
  antenna, and how far, for `scripts/board_from_circuit.py`,
  `scripts/squeeze_board.py` and the rule in
  `noaidi-fpga-synth.kicad_dru` that KiCad's DRC checks it by.
- `scripts/squeeze_board.py`: places the parts and draws the outline,
  from the constraints in `circuit/fixed_positions.toml`
  (`scripts/squeeze_board.py build/check/skidl/board.net
  noaidi-fpga-synth.kicad_pcb 3`, then `scripts/route.sh`). Each part at
  an edge gets its cluster, the parts of its block of the circuit laid
  out around it, and the clusters are packed along the edges into the
  smallest outline: one number says how many millimetres are kept
  between two clusters, and a second, if given, how wide the board may
  be.
- `scripts/route.sh`: lays the board's signals anew with Freerouting and
  prints what KiCad's DRC finds; `scripts/route_board.py` writes the
  board for the router and reads its result back.
- `circuit/pair_paths.toml`: the pads and the layer of each differential
  pair, and its path where it has to go around something, and
  `scripts/lay_pairs.py`, which lays the pair's two tracks side by side
  for the router to work around.
- `scripts/lay_fill_vias.py`: gives each surface-mount pad on the net
  of a fill on another layer its via and the track to it, and a track
  to the pad of its net beside it on another part of its block of the
  circuit (a bypass capacitor to the pins it serves), before the router
  runs, for the router to work around.
- `scripts/join_fills.py`: ties the fills of one net together with
  vias, joins the pads the fills do not reach, and ties back a piece of
  a fill that tracks have cut off from the rest of its net.
- `scripts/place_designators.py`: puts each part's designator at the
  free place nearest its part, where no part covers it and no pad, hole
  or other print cuts it.
- `scripts/silkscreen_clearance.py`: measures every print on the
  silkscreen against every pad's solder mask opening and lists the ones
  nearer than JLCPCB's 0.15 mm, which KiCad's DRC does not report;
  `scripts/check.sh` runs it.
- `scripts/layout_pictures.py`: pictures of the board's copper and print to judge
  a layout by: the whole board, its quarters, tiles small enough for an
  agent to see every track, each layer with its fill, and the fills
  laid over each other.
- `scripts/fab_files.py`: writes what JLCPCB's order page takes into
  `build/fab/`: the Gerber and drill files as one archive, the list of
  the parts JLCPCB places, and the list of where each of them sits.
- `scripts/cost_estimate.py`: prints what an order of the board costs at
  JLCPCB, delivered to Norway with VAT: the parts and the assembly fees
  fetched from JLCPCB as it runs, the bare boards and shipping at the
  prices read from JLCPCB's quote page.
- `docs/pins.md`: which pin of which module carries what, the
  connectors, the test points, and each part's name in the code.
  Written by `circuit/board.py`; not edited by hand.
- `docs/requirements.md`: what the board has to do; the circuit and
  the layout are checked against it.
- `docs/esp32s3_hw678.md`: what the two HW-678 copies of the
  ESP32-S3-DevKitC-1 are, measured: the pins the module takes, the
  free pins, the USB bridge and the open USB-OTG pads, and the header
  pins read from two photos of the board, `docs/esp32s3_hw678_top.jpg`
  and `docs/esp32s3_hw678_bottom.jpg`. The synth repository carries the
  same file without the Header pins section.
- `docs/thirdparty/`: the vendors' documents the board is drawn from.
  Mechanical: the Tang Nano 20K's dimension drawing (`.pdf`, `.dxf`) and
  3D model (`.step`), the ESP32-S3-DevKitC-1-N8R2's 3D model (`.STEP`),
  the Adafruit PCM510x's 3D model (`.step`) and fab print with its
  dimensions, and a 3D model of the Lumberg 0105 05 DIN socket made
  from Lumberg's model of the 0105 08-1 (`.stp`).
  Electrical: the Tang Nano 20K's schematic and pinout, the
  GW2AR data sheet, the ESP32-S3-DevKitC-1 user guide, pinouts and
  schematic (v1.1), the
  Adafruit PCM510x guide and schematic, the 6N138 MIDI input circuit and
  the TOTX1950A optical transmitter's data sheet. The board's own parts,
  from the links in their symbols' Datasheet fields: the LM66100 ideal
  diode (U6, U7), the H11L1 optocoupler (U3, U4; onsemi's data sheet,
  which the symbol names, and Everlight's, whose part is the one
  chosen), the 1N4148W diode (D1, D2), the Lumberg 0105 DIN socket
  (J1, J2), the Kycon KLPX RCA socket (J3) and the Hroparts
  TYPE-C-31-M-12 USB-C socket (J9, J14; drawing). Two parts that are
  not on the board: the 6N138 optocoupler and the GCT USB4085 USB-C
  receptacle (specification and drawing).

## Build tools

`kicad-cli` (KiCad 10), `pdftoppm` (poppler-utils) and
`java` (25, for Freerouting, whose jar `scripts/route.sh` fetches into
`build/tools/`) come from the system's packages, and so does the Python
with KiCad's `pcbnew` module and Pillow (python3-pil) that the scripts
which read the board file run under. The other Python
tools are listed in
`scripts/requirements.txt` and live in a virtual environment, `.venv/`
at the root, which is not committed:

    python3 -m venv .venv
    .venv/bin/pip install -r scripts/requirements.txt
    source .venv/bin/activate

- `skidl`: circuits described in Python. It is not in Ubuntu's packages.
  It finds KiCad's symbol libraries through the environment variable
  `KICAD10_SYMBOL_DIR` (`/usr/share/kicad/symbols` on Ubuntu).
- `pillow`: for `scripts/crop.py`.

## The circuit in text

`circuit/` describes the board's circuit in Python, and it is where the
circuit is designed. It holds the parts chosen for fabrication: 0805
resistors and capacitors, H11L1 optocouplers, two surface-mount USB-C
sockets (one for power, one for the ESP32's USB data), no ferrite
bead, and one S/PDIF coaxial output (J3, the 96 kHz stream; the 48 kHz
stream is on its header only). The board is made from it:
`scripts/board_from_circuit.py` sets its parts, nets and net classes and
`scripts/route.sh` lays its copper, and `scripts/check.sh` says whether
the board agrees with it. Parts have a descriptive name in the code and
a regular designator on the board.

Copyright © 2026 Thor H. Linløkken <thj@thj.no>
License: [CERN-OHL-S v2](LICENSE.txt)
