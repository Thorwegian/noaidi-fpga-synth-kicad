#!/bin/bash
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
# check.sh -- is the board the circuit in text?
#
#     scripts/check.sh
#
# Runs circuit/board.py (SKiDL's rule check, the netlist, docs/pins.md)
# and compares the netlist with the board twice: with the net each pad
# is assigned to (scripts/netlist_summary.py), and with the copper, which
# has to join the pins of every net (scripts/net_pieces.py). A difference
# is printed as the pins it concerns.
#
# Copper that joins two nets is for KiCad's DRC to find. Its findings are
# counted by type into build/check/counts.txt, for comparing with the same
# file from main, and each finding of severity error is printed with the
# pads and tracks it names and where they are on the board. Then measures
# the board's print against its pads, which KiCad's DRC does not
# (scripts/silkscreen_clearance.py).
#
# Exit code 0 when the rule check is clean, the board agrees with the
# circuit in its pads and in its copper, KiCad's DRC has no finding of
# severity error and no print is nearer a pad than JLCPCB prints it.
#
# Needs kicad-cli (KiCad 10), the Python environment of
# scripts/requirements.txt in the main checkout's .venv/, and the system's
# Python with KiCad's pcbnew module.

set -u
cd "$(dirname "$0")/.."

# A worktree has no environment of its own: the main checkout's serves them all.
python="$(git rev-parse --path-format=absolute --git-common-dir)/../.venv/bin/python"
export KICAD10_SYMBOL_DIR="${KICAD10_SYMBOL_DIR:-/usr/share/kicad/symbols}"

board=noaidi-fpga-synth.kicad_pcb
out=build/check
mkdir -p $out/skidl
failed=0

# SKiDL writes its log files where it is run.
if ! (cd $out/skidl && "$python" ../../../circuit/board.py > board.out 2>&1); then
    echo "circuit in text: circuit/board.py failed, see $out/skidl/board.out"
    exit 1
fi
if grep -q -E "ERC (WARNING|ERROR)" $out/skidl/board.out; then
    echo "circuit in text: the rule check has findings, see $out/skidl/board.erc"
    failed=1
else
    echo "circuit in text: the rule check is clean"
fi

echo "circuit in text against the board, the net of each pad:"
"$python" scripts/netlist_summary.py $out/skidl/board.net $board | sed 's/^/    /'
[ "${PIPESTATUS[0]}" -eq 0 ] || failed=1

echo "circuit in text against the board, the copper:"
# pcbnew writes its own chatter to the standard error stream.
scripts/net_pieces.py $out/skidl/board.net $board 2> /dev/null | sed 's/^/    /'
[ "${PIPESTATUS[0]}" -eq 0 ] || failed=1

if git diff --quiet -- docs/pins.md; then
    echo "docs/pins.md: unchanged"
else
    echo "docs/pins.md: changed by this run, to be committed with the circuit"
fi

kicad-cli pcb drc --severity-all --format json -o $out/drc.json $board > /dev/null || exit 1
echo "KiCad's DRC, by type ($out/counts.txt):"
"$python" scripts/rule_counts.py $out/drc.json > $out/counts.txt
has_errors=$?
sed 's/^/    /' $out/counts.txt
if [ $has_errors -ne 0 ]; then
    "$python" scripts/rule_counts.py --errors $out/drc.json | sed 's/^/        /'
    failed=1
fi

echo "the print against the pads:"
scripts/silkscreen_clearance.py $board 2> /dev/null | sed 's/^/    /'
[ "${PIPESTATUS[0]}" -eq 0 ] || failed=1

exit $failed
