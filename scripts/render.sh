#!/bin/bash
# Copyright © 2026 Thor H. Linløkken <thj@thj.no>
# License: CERN-OHL-S v2
#
# render.sh -- the README's board images, into build/ at the repository's root.
# Needs kicad-cli from KiCad 10 and Pillow (crop.py).
set -e
cd "$(dirname "$0")/.."
B=build
mkdir -p $B
PCB=noaidi-fpga-synth.kicad_pcb
kicad-cli pcb render --side top --rotate "-40,0,20" --perspective --width 2000 --height 1400 \
    --background opaque --quality high --floor --zoom 0.85 --pan "-0.9,1.47,0" -o $B/pcb-iso.png $PCB
# The same view from the other side, turned 180 degrees about the vertical: the
# sockets at the board's top edge are nearest the camera and face it.
kicad-cli pcb render --side top --rotate "-40,0,200" --perspective --width 2000 --height 1400 \
    --background opaque --quality high --floor --zoom 0.85 --pan "-0.83,1.27,0" -o $B/pcb-iso-rear.png $PCB
# At zoom 1 kicad-cli scales the board's longer side to the frame's height, so
# a square frame below zoom 1 holds an outline of any proportion.
kicad-cli pcb render --side top --width 2000 --height 2000 \
    --background opaque --quality high --floor --zoom 0.85 -o $B/pcb-top.png $PCB
kicad-cli pcb export svg --layers F.Cu,F.SilkS,F.Mask,Edge.Cuts --page-size-mode 2 \
    --exclude-drawing-sheet --mode-single -o $B/pcb-front.svg $PCB
kicad-cli pcb export svg --layers B.Cu,B.SilkS,Edge.Cuts --mirror --page-size-mode 2 \
    --exclude-drawing-sheet --mode-single -o $B/pcb-back.svg $PCB
scripts/crop.py $B/pcb-iso.png $B/pcb-iso.jpg
scripts/crop.py $B/pcb-iso-rear.png $B/pcb-iso-rear.jpg
scripts/crop.py $B/pcb-top.png $B/pcb-top.jpg
ls -l $B
