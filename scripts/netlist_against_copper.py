#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""netlist_against_copper.py -- does the board's copper connect what the netlist connects, and nothing else?

    scripts/netlist_against_copper.py <netlist> <board> <DRC report>

scripts/netlist_summary.py compares the netlist with the net each pad of
the board is assigned to. This compares it with the copper, and says what
it finds as pins (R15.1 is pin 1 of R15), one line for each:

    not connected: R4.1 and R3.1 (ESP_3V3), a gap of 18.68 mm

  Pins of one net of the netlist that the board's tracks, vias and fills
  (as the board file stores them) do not join. A net's copper is then in
  pieces, and for each piece but the largest the line names the place
  where it comes nearest to the others: the pin nearest to either side of
  that gap along the copper, and the gap's width.

    connected, and should not be: R15.2 (I2C1_SCL) and R15.1 (ESP_3V3)

  Copper of two nets of the netlist that touches. KiCad's DRC finds the
  place (the report is what `kicad-cli pcb drc --format json` writes);
  the line names the pin nearest to it along the copper of either net.

A pin of the netlist that has no pad on the board is named too. Prints
the counts last. The exit status is 1 when there is a line of either kind.

Runs under the Python that has KiCad's pcbnew module.
"""
import collections
import heapq
import json
import math
import re
import sys

import pcbnew

from netlist_summary import read_netlist

TOUCHING = ("shorting_items", "tracks_crossing")    # the DRC findings that are copper of two nets in contact


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
    (distance, item of the piece, item of another piece)."""
    return min(((math.hypot(mine.x - theirs.x, mine.y - theirs.y), item, other)
                for item in piece.values() for mine in ends(item)
                for other_piece in others for other in other_piece.values() for theirs in ends(other)),
               key=lambda approach: approach[0])


def nearest_pads(connectivity, item):
    """The pads of the item's own net that are nearest to it along the
    copper, by the length of track on the way; the item itself when it is
    a pad."""
    if item.GetClass() == "PAD":
        return [item]
    seen, reached = {unique_id(item)}, [(0, unique_id(item), item)]
    while reached:
        length, _, track = heapq.heappop(reached)
        pads = [pad for pad in connectivity.GetConnectedPads(track) if pad.GetNetCode() == item.GetNetCode()]
        if pads:
            return pads
        for further in connectivity.GetConnectedTracks(track):
            if unique_id(further) not in seen:
                seen.add(unique_id(further))
                heapq.heappush(reached, (length + further.GetLength(), unique_id(further), further))
    return []


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

    def pins_at(item):
        """The pins nearest to the item along its copper, in reading order."""
        return sorted({pin_of[unique_id(pad)] for pad in nearest_pads(connectivity, item)},
                      key=lambda pin: in_reading_order(pin_name(pin)))

    def names(pins):
        return " ".join(pin_name(pin) for pin in pins)

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
            gap, item, other = nearest_approach(piece, [rest for rest in pieces if rest is not piece])
            line = f"not connected: {names(pins_at(item))} and {names(pins_at(other))} ({name})"
            if item.GetNetname() != other.GetNetname():
                line += f": the board has {names(pins_at(item))} on the net {item.GetNetname() or '(none)'}"
            elif gap == 0:
                line += ", one above the other on different layers with nothing joining the layers"
            else:
                line += f", a gap of {pcbnew.ToMM(gap):.2f} mm"
            not_connected.append(line)

    # What the copper connects and the netlist does not.
    item_of = {unique_id(item): item for item in list(board.GetTracks()) + list(board.Zones())}
    item_of.update((unique_id(pad), pad) for pads in pads_of_pin.values() for pad in pads)
    with open(report_path, encoding="utf-8") as file:
        findings = [finding for finding in json.load(file)["violations"] if finding["type"] in TOUCHING]
    wrongly_connected = set()
    for finding in findings:
        sides = [pins_at(item_of[item["uuid"]]) for item in finding["items"] if item["uuid"] in item_of]
        sides = sorted((pins for pins in sides if pins), key=lambda pins: in_reading_order(names(pins)))
        nets_of_sides = [net_of_pin.get(pins[0], "no net") for pins in sides]
        if len(sides) == 2 and nets_of_sides[0] != nets_of_sides[1]:
            wrongly_connected.add("connected, and should not be: " + " and ".join(
                f"{names(pins)} ({net})" for pins, net in zip(sides, nets_of_sides)))

    for line in not_connected + sorted(wrongly_connected, key=in_reading_order):
        print(line)
    print(f"{len(connected_nets)} nets of more than one pin: {len(not_connected)} not connected, "
          f"{len(wrongly_connected)} connected that should not be")
    sys.exit(1 if not_connected or wrongly_connected else 0)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
