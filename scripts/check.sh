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
# and compares the netlist with the board. Then counts the findings of
# KiCad's DRC by type into build/check/counts.txt, for comparing with
# the same file from main, and measures the board's print against its
# pads, which KiCad's DRC does not (scripts/silkscreen_clearance.py).
#
# Exit code 0 when the rule check is clean, the board agrees with the
# circuit and no print is nearer a pad than JLCPCB prints it.
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

echo "circuit in text against the board:"
"$python" scripts/netlist_summary.py $out/skidl/board.net $board | sed 's/^/    /'
[ "${PIPESTATUS[0]}" -eq 0 ] || failed=1

if git diff --quiet -- docs/pins.md; then
    echo "docs/pins.md: unchanged"
else
    echo "docs/pins.md: changed by this run, to be committed with the circuit"
fi

kicad-cli pcb drc --severity-all --format json -o $out/drc.json $board > /dev/null || exit 1
"$python" scripts/rule_counts.py $out/drc.json > $out/counts.txt
echo "KiCad's DRC, by type ($out/counts.txt):"
sed 's/^/    /' $out/counts.txt

echo "the print against the pads:"
# pcbnew writes its own chatter to the standard error stream.
scripts/silkscreen_clearance.py $board 2> /dev/null | sed 's/^/    /'
[ "${PIPESTATUS[0]}" -eq 0 ] || failed=1

exit $failed
