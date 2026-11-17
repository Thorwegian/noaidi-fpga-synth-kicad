#!/bin/bash
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
# route.sh -- lay the board's copper with an autorouter, and count what KiCad's DRC finds in it.
#
#     scripts/route.sh
#
# Removes every track and via from the board, so that a run starts from its
# pads (scripts/route_board.py clear), and lays the differential pairs along
# the paths circuit/pair_paths.toml states (scripts/lay_pairs.py). It has
# Freerouting lay the signals around them, to the net classes' widths and
# clearances, on the layers that take tracks:
# scripts/route_board.py writes the board for the router and reads its
# result back. Then, in the room the router leaves, scripts/lay_fill_vias.py
# joins each surface-mount pad on the net of a fill on another layer to its
# fill and, where the pads are near, to the pad beside it (it reads the
# blocks from the netlist that scripts/check.sh writes), and
# scripts/join_fills.py ties the fills of one net together and joins the
# pads that are left, and scripts/route_board.py widen takes each track the
# router laid thinner than its net class out to that width where it still
# fits. With that copper in place, scripts/place_designators.py
# puts each part's designator where it can be read. Then prints the counts
# of KiCad's DRC, which are the verdict; the router's own count of
# violations is not.
#
# Every track is at its net class's width: automatic_neckdown is off, so a
# track changes width neither partway between the pins it passes nor at a
# via, and a connection that will not fit at that width is left open for
# the count rather than laid thin.
#
# Needs java (25), kicad-cli (KiCad 10) and the system's Python with KiCad's
# pcbnew module. Freerouting's jar is fetched into build/tools/ and checked
# against the SHA-256 below.

set -u -o pipefail
cd "$(dirname "$0")/.."

# KiCad's pcbnew is not in macOS's /usr/bin/python3: the application's Python
# has it. A Mac checks a checksum with shasum where Linux has sha256sum.
if [ "$(uname -s)" = Darwin ]; then
    python="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
    check_sha256="shasum --algorithm 256 --check --quiet"
else
    python=/usr/bin/python3
    check_sha256="sha256sum --check --quiet"
fi

board=noaidi-fpga-synth.kicad_pcb
out=build/route
jar=build/tools/freerouting-2.5.0.jar
jar_url=https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar
jar_sha256=f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7
netlist=build/check/skidl/board.net
mkdir -p $out build/tools

if [ ! -f $jar ]; then
    curl --silent --show-error --location --output $jar $jar_url || exit 1
fi
echo "$jar_sha256  $jar" | $check_sha256 || exit 1

# pcbnew writes its own chatter to the standard error stream.
"$python" scripts/route_board.py clear $board 2> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
"$python" scripts/lay_pairs.py $board 2> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
if [ ! -f $netlist ]; then
    echo "$netlist is missing: scripts/check.sh writes it from the circuit"
    exit 1
fi
layers_with_tracks=$("$python" scripts/route_board.py export $board $out/board.dsn 2>> $out/pcbnew.log) || { cat $out/pcbnew.log; exit 1; }

if ! java -Djava.awt.headless=true -jar $jar -de $out/board.dsn -do $out/board.ses \
        --router.autorouter.max_passes=30 --router.layers.routable=$layers_with_tracks \
        --router.automatic_neckdown=false > $out/freerouting.log 2>&1; then
    echo "Freerouting failed, see $out/freerouting.log"
    exit 1
fi
grep --only-matching "Auto-routing stage completed.*violations)" $out/freerouting.log \
    | sed 's/^/Freerouting says: /'
# An option the router does not know is a warning in its log, and the run goes on without it.
if grep --quiet "Unknown settings property" $out/freerouting.log; then
    grep --only-matching "Unknown settings property.*" $out/freerouting.log
    exit 1
fi

"$python" scripts/route_board.py import $board $out/board.ses 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
"$python" scripts/lay_fill_vias.py $board $netlist 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
"$python" scripts/join_fills.py $board $out/drc.json 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
"$python" scripts/route_board.py widen $board 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
"$python" scripts/place_designators.py $board 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
kicad-cli pcb drc --severity-all --format json --output $out/drc.json $board > /dev/null || exit 1
echo "KiCad's DRC, by type ($out/drc.json):"
"$python" scripts/rule_counts.py $out/drc.json | sed 's/^/    /'
