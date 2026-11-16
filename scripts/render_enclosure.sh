#!/bin/bash
# Copyright © 2026 Thor H. Linløkken <thj@thj.no>
# License: CERN-OHL-S v2
#
# render_enclosure.sh -- build/enclosure.png: the board in a clear acrylic
# enclosure, lit by LEDs inside the acrylic, in the dark.
#
#     scripts/render_enclosure.sh [width px, default 960] [samples, default 256]
#
# kicad-cli writes the board with its parts and its copper as a 3D model, and
# Blender builds the enclosure around it and renders the picture
# (scripts/enclosure_scene.py, which says how). The defaults are the preview:
# small, at the full quality of the light. The render is a path tracer's and
# takes its time: run it in the background.
# Needs kicad-cli from KiCad 10 and Blender 4 with Cycles.
set -e
cd "$(dirname "$0")/.."
B=build
mkdir -p $B
kicad-cli pcb export glb --force --subst-models --include-silkscreen --include-soldermask \
    --include-pads --include-tracks --include-zones -o $B/board.glb noaidi-fpga-synth.kicad_pcb
blender -b --python-exit-code 1 --python scripts/enclosure_scene.py -- \
    $B/board.glb $B/enclosure.png "${1:-960}" "${2:-256}"
ls -l $B/enclosure.png
