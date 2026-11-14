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
- **ESP32-S3-DevKitC** (U1) on headers: MIDI, voices, patches and the
  console. The prototype runs an ESP32-C3 Super Mini; the board moves to
  the S3 (the firmware port is tracked in the synth repository,
  `docs/esp32s3_hw678.md`).
- **Two DIN MIDI inputs** (J1, J2) through 6N138 optocouplers (U3, U4):
  one for the keyboard, one for the dev host.
- **Audio out**: an Adafruit PCM510x I2S DAC module (U5) for analog, two
  RCA sockets (J3, J4) for S/PDIF.
- **USB-C** (J9) for power, into each module's 5 V rail through an
  LM66100 ideal diode (U6, U7), and the data pair to the ESP32.
- Pin headers for the second SPI bus, two I2C buses, UART0, I2S and
  S/PDIF, and 29 test points.

Two layers, 130.85 × 121.25 mm, through-hole apart from the two LM66100
(SC-70) and the ferrite bead.

## Layout

![The top of the board, rendered in 3D](https://thj.no/synth/images/pcb-top.jpg)

Front copper and silkscreen:

![Front copper and silkscreen](https://thj.no/synth/images/pcb-front.svg)

Back copper, mirrored:

![Back copper, mirrored](https://thj.no/synth/images/pcb-back.svg)

The connector and module bodies render as footprints only: their 3D
models are not part of the project.

## Schematic

[pcb-schematic.pdf](https://thj.no/synth/images/pcb-schematic.pdf), all
five sheets: the root, `esp32`, `tang_nano_20k`, `usb` and `test_points`.

## Files

- `noaidi-fpga-synth.kicad_pro`, `.kicad_sch` and the four sheet files,
  `.kicad_pcb`, `.kicad_dru`
- `noaidi-fpga-synth.kicad_sym` and `noaidi-fpga-synth.pretty/`: the
  project's own symbols and footprints (the two modules, the DAC, the
  DIN sockets, the RCA and USB-C connectors)
- `render.sh`: regenerates the images above into `build/` with
  `kicad-cli` (KiCad 10); `crop.py` trims the 3D renders to the board
- `docs/requirements.md`: what the board has to do; the schematic and
  the layout are checked against it.
- `docs/esp32s3_hw678.md`: what the two HW-678 copies of the
  ESP32-S3-DevKitC-1 are, measured: the pins the module takes, the
  free pins, the USB bridge and the open USB-OTG pads. A copy of the
  synth repository's file, which is where it is maintained.
- `docs/thirdparty/`: the vendors' documents the board is drawn from.
  Mechanical: the Tang Nano 20K's dimension drawing (`.pdf`, `.dxf`) and
  3D model (`.step`), and the Adafruit PCM510x's fab print with its
  dimensions. Electrical: the Tang Nano 20K's schematic and pinout, the
  GW2AR data sheet, the ESP32-S3-DevKitC-1 user guide and pinouts, the
  Adafruit PCM510x guide and schematic, the 6N138 MIDI input circuit and
  the TOTX1950A optical transmitter's data sheet. The board's own parts,
  from the links in the schematic's Datasheet fields: the LM66100 ideal
  diode (U6, U7), the 6N138 optocoupler (U3, U4), the Lumberg 0105 DIN
  socket (J1, J2), the Kycon KLPX RCA socket (J3, J4) and the GCT
  USB4085 USB-C receptacle (J9; specification and drawing).

Copyright © 2026 Thor H. Linløkken <thj@thj.no>
License: [CERN-OHL-S v2](LICENSE.txt)
