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
# is assigned to (scripts/netlist_summary.py), and with the copper
# (scripts/netlist_against_copper.py), which says in pins what the copper
# does not connect that the netlist does, and what it connects that the
# netlist does not.
#
# KiCad's DRC finds where copper of two nets touches, and the comparison
# with the copper reads its report. Its findings are counted by type into
# build/check/counts.txt, for comparing with the same file from main, and
# each finding of severity error that is not about a connection is printed
# with the items it names and where they are on the board. Then measures
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

# Runs a script that reads the board with KiCad's pcbnew module and prints
# what it says, indented. pcbnew writes its own chatter to the standard
# error stream, which goes to a log. Each of these scripts ends with a
# count, so one that printed nothing did not run, and the log says why.
run_on_board() {
    local name
    name=$(basename "$1" .py)
    "$@" > $out/$name.txt 2> $out/$name.log
    local status=$?
    sed 's/^/    /' $out/$name.txt
    if [ ! -s $out/$name.txt ]; then
        echo "    $1 did not run ($out/$name.log):"
        tail -n 1 $out/$name.log | sed 's/^/        /'
    fi
    return $status
}

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

kicad-cli pcb drc --severity-all --format json -o $out/drc.json $board > /dev/null || exit 1

echo "circuit in text against the board, the copper:"
run_on_board scripts/netlist_against_copper.py $out/skidl/board.net $board $out/drc.json || failed=1

if git diff --quiet -- docs/pins.md; then
    echo "docs/pins.md: unchanged"
else
    echo "docs/pins.md: changed by this run, to be committed with the circuit"
fi

echo "KiCad's DRC, by type ($out/counts.txt):"
"$python" scripts/rule_counts.py $out/drc.json > $out/counts.txt
has_errors=$?
sed 's/^/    /' $out/counts.txt
if [ $has_errors -ne 0 ]; then
    "$python" scripts/rule_counts.py --errors $out/drc.json | sed 's/^/        /'
    failed=1
fi

echo "the print against the pads:"
run_on_board scripts/silkscreen_clearance.py $board || failed=1

exit $failed
