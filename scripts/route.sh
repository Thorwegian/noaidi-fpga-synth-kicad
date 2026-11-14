#!/bin/bash
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
# route.sh -- lay the board's copper with an autorouter, and count what KiCad's DRC finds in it.
#
#     scripts/route.sh
#
# Removes every track and via from the board and has Freerouting lay them
# anew, to the net classes' widths and clearances: scripts/route_board.py
# writes the board for the router and reads its result back. Then runs
# KiCad's DRC, whose counts are the verdict; the router's own count of
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
scripts/route_board.py export $board $out/board.dsn 2> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }

if ! java -Djava.awt.headless=true -jar $jar -de $out/board.dsn -do $out/board.ses \
        --router.autorouter.max_passes=30 > $out/freerouting.log 2>&1; then
    echo "Freerouting failed, see $out/freerouting.log"
    exit 1
fi
grep --only-matching "Auto-routing stage completed.*violations)" $out/freerouting.log \
    | sed 's/^/Freerouting says: /'

scripts/route_board.py import $board $out/board.ses 2>> $out/pcbnew.log || { cat $out/pcbnew.log; exit 1; }

kicad-cli pcb drc --severity-all --format json -o $out/drc.json $board > /dev/null || exit 1
echo "KiCad's DRC, by type ($out/drc.json):"
/usr/bin/python3 scripts/rule_counts.py $out/drc.json | sed 's/^/    /'
