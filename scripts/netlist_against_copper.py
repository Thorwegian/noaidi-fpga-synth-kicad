#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""netlist_against_copper.py -- does the board's copper connect what the netlist connects, and nothing else?

    scripts/netlist_against_copper.py
    scripts/netlist_against_copper.py <netlist> <board> <DRC report>

Without arguments it takes the project's own files: the netlist that
scripts/check.sh last wrote (build/check/skidl/board.net), the board, and
a DRC report that it has kicad-cli make of the board as it is now.

scripts/netlist_summary.py compares the netlist with the net each pad of
the board is assigned to. This compares it with the copper, and says what
it finds as pins (R15.1 is pin 1 of R15), one line for each:

    not connected: R4.1 and R3.1 (ESP_3V3), a gap of 18.68 mm

  Pins of one net of the netlist that the board's tracks, vias and fills
  (as the board file stores them) do not join. A net's copper is then in
  pieces, and for each piece but the largest the line names the place
  where it comes nearest to the others: on either side of that gap, the
  pin nearest to it of those the copper there reaches, and the gap's
  width.

    connected, and should not be: R15.2 (I2C1_SCL) and R15.1 (ESP_3V3)

  Copper of two nets of the netlist that touches. KiCad's DRC finds the
  place (the report is what `kicad-cli pcb drc --all-track-errors
  --format json` writes: a short, crossing tracks, or a clearance that is
  down to nothing); the line names, for the copper of either net, the pin
  nearest to it of those it reaches, and a fill by its net.

A pin of the netlist that has no pad on the board is named too. Prints
the counts last. The exit status is 1 when there is a line of either kind.

Needs KiCad's pcbnew module. The system's Python has it on Linux; on
macOS it is in the Python inside the KiCad application, and the script
starts itself again under that one.
"""
import collections
import json
import math
import os
import re
import subprocess
import sys

KICAD_PYTHON_ON_MACOS = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
try:
    import pcbnew
except ModuleNotFoundError:
    if "UNDER_KICAD_PYTHON" in os.environ or not os.path.exists(KICAD_PYTHON_ON_MACOS):
        raise
    os.execve(KICAD_PYTHON_ON_MACOS, [KICAD_PYTHON_ON_MACOS] + sys.argv, {**os.environ, "UNDER_KICAD_PYTHON": "1"})

from netlist_summary import read_netlist

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOUCHING = ("shorting_items", "tracks_crossing")    # the DRC findings that are copper of two nets in contact
NO_DISTANCE = re.compile(r"actual 0\.0+ mm")        # in a clearance finding's description: the two items touch


def unique_id(item):
    return item.m_Uuid.AsString()


def pin_name(pin):
    return ".".join(pin)


def in_reading_order(name):
    """Sorts R3.1 ahead of R11.1."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def pieces_of(connectivity, pads):
    """The copper of the pads, grouped by what it joins: a list of pieces,
    each {unique id: item} of the pads, tracks, vias and fills in it."""
    placed, pieces = set(), []
    for pad in pads:
        if unique_id(pad) in placed:
            continue
        piece = {unique_id(item): item.Cast() for item in connectivity.GetConnectedItems(pad)}
        piece[unique_id(pad)] = pad
        placed.update(piece)
        pieces.append(piece)
    return pieces


def ends(item):
    """The points at which copper joins the item: the two ends of a track,
    the middle of a via or a pad. A fill has none: a gap is measured
    between tracks, vias and pads."""
    kind = item.GetClass()
    if kind in ("PCB_TRACK", "PCB_ARC"):
        return [item.GetStart(), item.GetEnd()]
    if kind in ("PCB_VIA", "PAD"):
        return [item.GetPosition()]
    return []


def nearest_approach(piece, others):
    """Where the piece comes nearest to the other pieces of its net, as
    (distance, item of the piece, its end there, item of another piece,
    its end there)."""
    return min(((math.hypot(mine.x - theirs.x, mine.y - theirs.y), item, mine, other, theirs)
                for item in piece.values() for mine in ends(item)
                for other_piece in others for other in other_piece.values() for theirs in ends(other)),
               key=lambda approach: approach[0])


def nearest_pad(connectivity, item, points):
    """The pad that the item's copper reaches and that lies nearest to one
    of the points, in a straight line; the item itself when it is a pad,
    and None when its copper reaches no pad."""
    if item.GetClass() == "PAD":
        return item
    pads = [joined.Cast() for joined in connectivity.GetConnectedItems(item) if joined.GetClass() == "PAD"]
    return min(pads, default=None, key=lambda pad: (
        min(math.hypot(pad.GetPosition().x - point.x, pad.GetPosition().y - point.y) for point in points),
        unique_id(pad)))


def main(netlist_path, board_path, report_path):
    _, nets = read_netlist(netlist_path)
    net_of_pin = {pin: name for name, pins in nets.items() for pin in pins}
    board = pcbnew.LoadBoard(board_path)
    connectivity = board.GetConnectivity()
    pads_of_pin, pin_of = collections.defaultdict(list), {}
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.IsOnCopperLayer():
                pin = (footprint.GetReference(), pad.GetNumber())
                pads_of_pin[pin].append(pad)
                pin_of[unique_id(pad)] = pin

    def pin_at(item, points):
        """The pin whose pad the item's copper reaches nearest to the
        points, as (designator, pad number), or None."""
        pad = nearest_pad(connectivity, item, points)
        return pin_of[unique_id(pad)] if pad else None

    # What the netlist connects and the copper does not.
    connected_nets = {name: pins for name, pins in nets.items() if len(pins) > 1}
    not_connected = []
    for name in sorted(connected_nets):
        pins = connected_nets[name]
        for pin in sorted(pins - set(pads_of_pin), key=lambda pin: in_reading_order(pin_name(pin))):
            not_connected.append(f"not connected: {pin_name(pin)} ({name}) has no pad on the board")
        pieces = pieces_of(connectivity, [pad for pin in pins for pad in pads_of_pin.get(pin, [])])
        pieces.sort(key=lambda piece: sum(item.GetClass() == "PAD" for item in piece.values()))
        for piece in pieces[:-1]:
            gap, item, end, other, other_end = nearest_approach(piece, [rest for rest in pieces if rest is not piece])
            loose = pin_name(pin_at(item, [end]))
            line = f"not connected: {loose} and {pin_name(pin_at(other, [other_end]))} ({name})"
            if item.GetNetname() != other.GetNetname():
                line += f": the board has {loose} on the net {item.GetNetname() or '(none)'}"
            elif gap == 0:
                line += ", one above the other on different layers with nothing joining the layers"
            else:
                line += f", a gap of {pcbnew.ToMM(gap):.2f} mm"
            not_connected.append(line)

    # What the copper connects and the netlist does not.
    item_of = {unique_id(item): item for item in list(board.GetTracks()) + list(board.Zones())}
    item_of.update((unique_id(pad), pad) for pads in pads_of_pin.values() for pad in pads)

    def side(item):
        """One side of a contact, as (what to call it, its net): the pin
        nearest to the item among those its copper reaches, with its net
        in the netlist, or a fill by its net."""
        if item.GetClass() == "ZONE":
            return f"the fill of {item.GetNetname()}", item.GetNetname()
        pin = pin_at(item, ends(item))
        if not pin:
            return f"copper that reaches no pin ({item.GetNetname()})", item.GetNetname()
        return f"{pin_name(pin)} ({net_of_pin.get(pin, 'no net')})", net_of_pin.get(pin)

    with open(report_path, encoding="utf-8") as file:
        findings = [finding for finding in json.load(file)["violations"]
                    if finding["type"] in TOUCHING
                    or finding["type"] == "clearance" and NO_DISTANCE.search(finding["description"])]
    wrongly_connected = set()
    for finding in findings:
        sides = sorted((side(item_of[item["uuid"]]) for item in finding["items"] if item["uuid"] in item_of),
                       key=lambda found: in_reading_order(found[0]))
        if len(sides) == 2 and sides[0][1] != sides[1][1]:
            wrongly_connected.add(f"connected, and should not be: {sides[0][0]} and {sides[1][0]}")

    for line in not_connected + sorted(wrongly_connected, key=in_reading_order):
        print(line)
    print(f"{len(connected_nets)} nets of more than one pin: {len(not_connected)} not connected, "
          f"{len(wrongly_connected)} connected that should not be")
    sys.exit(1 if not_connected or wrongly_connected else 0)


def project_files():
    """The netlist, the board and a DRC report of the project the script
    is in, the report made now."""
    netlist = os.path.join(PROJECT_DIR, "build", "check", "skidl", "board.net")
    board = os.path.join(PROJECT_DIR, "noaidi-fpga-synth.kicad_pcb")
    report = os.path.join(PROJECT_DIR, "build", "check", "drc.json")
    if not os.path.exists(netlist):
        sys.exit(f"no netlist at {netlist}: scripts/check.sh writes it, or name one (see the top of this file)")
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--all-track-errors", "--format", "json",
                    "-o", report, board], check=True, stdout=subprocess.DEVNULL)
    return netlist, board, report


if __name__ == "__main__":
    if len(sys.argv) not in (1, 4):
        sys.exit(__doc__)
    main(*(sys.argv[1:] or project_files()))
