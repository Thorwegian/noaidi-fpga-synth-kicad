#!/bin/bash
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
# route.sh -- lay the board's copper with an autorouter, and count what KiCad's DRC finds in it.
#
#     scripts/route.sh
#
# Removes every track and via from the board and has Freerouting lay the
# signals anew, to the net classes' widths and clearances, on the layers
# that take tracks: scripts/route_board.py writes the board for the router
# and reads its result back. The nets of the board's fills get no track:
# the fills join their pads, and scripts/join_fills.py joins the pads the
# fills do not reach. With the vias in place, scripts/place_designators.py
# puts each part's designator where it can be read. Then prints the counts
# of KiCad's DRC, which are the verdict; the router's own count of
# violations is not.
#
# The router narrows a track where the going is tight, which is how it gets
# every connection through between the modules' pins; where it narrows below
# the board's minimum track width, route_board.py widens the track to it.
#
# Needs java (25), kicad-cli (KiCad 10) and the system's Python with KiCad's
# pcbnew module. Freerouting's jar is fetched into build/tools/ and checked
# against the SHA-256 below.

set -u -o pipefail
cd "$(dirname "$0")/.."

board=noaidi-fpga-synth.kicad_pcb
out=build/route
jar=build/tools/freerouting-2.5.0.jar
jar_url=https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar
jar_sha256=f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7
mkdir -p $out build/tools

if [ ! -f $jar ]; then
    curl --silent --show-error --location --output $jar $jar_url || exit 1
fi
echo "$jar_sha256  $jar" | sha256sum --check --quiet || exit 1

# pcbnew writes its own chatter to the standard error stream.
layers_with_tracks=$(scripts/route_board.py export $board $out/board.dsn 2> $out/pcbnew.log) || { cat $out/pcbnew.log; exit 1; }

if ! java -Djava.awt.headless=true -jar $jar -de $out/board.dsn -do $out/board.ses \
        --router.autorouter.max_passes=30 --router.layers.routable=$layers_with_tracks > $out/freerouting.log 2>&1; then
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

scripts/route_board.py import $board $out/board.ses 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
scripts/join_fills.py $board $out/drc.json 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
scripts/place_designators.py $board 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }
kicad-cli pcb drc --severity-all --format json --output $out/drc.json $board > /dev/null || exit 1
echo "KiCad's DRC, by type ($out/drc.json):"
/usr/bin/python3 scripts/rule_counts.py $out/drc.json | sed 's/^/    /'
