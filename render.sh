#!/bin/bash
# Copyright © 2026 Thor H. Linløkken <thj@thj.no>
# License: CERN-OHL-S v2
#
# render.sh -- the README's board images and the schematic PDF, into build/.
# Needs kicad-cli from KiCad 10 and pdfunite (poppler-utils).
set -e
cd "$(dirname "$0")"
B=build
mkdir -p $B
PCB=noaidi-fpga-synth.kicad_pcb
kicad-cli pcb render --side top --rotate "-40,0,20" --perspective --width 2000 --height 1400 \
    --background opaque --quality high --floor -o $B/pcb-iso.png $PCB
kicad-cli pcb render --side top --width 2000 --height 1600 \
    --background opaque --quality high --floor --zoom 1.1 -o $B/pcb-top.png $PCB
kicad-cli pcb export svg --layers F.Cu,F.SilkS,F.Mask,Edge.Cuts --page-size-mode 2 \
    --exclude-drawing-sheet --mode-single -o $B/pcb-front.svg $PCB
kicad-cli pcb export svg --layers B.Cu,B.SilkS,Edge.Cuts --mirror --page-size-mode 2 \
    --exclude-drawing-sheet --mode-single -o $B/pcb-back.svg $PCB
for s in noaidi-fpga-synth esp32 tang_nano_20k usb test_points; do
    kicad-cli sch export pdf -o $B/sch-$s.pdf $s.kicad_sch
done
pdfunite $B/sch-noaidi-fpga-synth.pdf $B/sch-esp32.pdf $B/sch-tang_nano_20k.pdf \
    $B/sch-usb.pdf $B/sch-test_points.pdf $B/pcb-schematic.pdf
ls -l $B
