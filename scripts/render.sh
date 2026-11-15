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

# view <name> <the camera's options>: build/<name>.jpg, the 3D view cropped to
# the board and the parts on it. The view is rendered twice: as the picture,
# with the floor and its shadows, and with a transparent background and no
# floor, which is opaque only where the board and its parts are. crop.py takes
# the frame from the second and the pixels from the first.
view() {
    local name=$1
    shift
    kicad-cli pcb render "$@" --background opaque --quality high --floor -o $B/$name.png $PCB
    kicad-cli pcb render "$@" --background transparent --quality basic -o $B/$name-mask.png $PCB
    scripts/crop.py $B/$name.png $B/$name-mask.png $B/$name.jpg
}

view pcb-iso --side top --rotate "-40,0,20" --perspective --width 2000 --height 1400 \
    --zoom 0.85 --pan "-0.9,1.47,0"
# The same view from the other side, turned 180 degrees about the vertical: the
# sockets at the board's top edge are nearest the camera and face it.
view pcb-iso-rear --side top --rotate "-40,0,200" --perspective --width 2000 --height 1400 \
    --zoom 0.85 --pan "-0.83,1.27,0"
# At zoom 1 kicad-cli scales the board's longer side to the frame's height, so
# a square frame below zoom 1 holds an outline of any proportion.
view pcb-top --side top --width 2000 --height 2000 --zoom 0.85
kicad-cli pcb export svg --layers F.Cu,F.SilkS,F.Mask,Edge.Cuts --page-size-mode 2 \
    --exclude-drawing-sheet --mode-single -o $B/pcb-front.svg $PCB
kicad-cli pcb export svg --layers B.Cu,B.SilkS,Edge.Cuts --mirror --page-size-mode 2 \
    --exclude-drawing-sheet --mode-single -o $B/pcb-back.svg $PCB
ls -l $B
