#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""join_fills.py -- join the pads that the board's fills do not reach.

    scripts/join_fills.py <board> <DRC report>

The router lays no track on the net of a fill (scripts/route_board.py): the
fill joins that net's pads wherever it reaches them. This script fills the
board and first ties the fills of one net on different layers together, with
a via every 10 mm wherever all of them have copper and the via keeps its
distance from other nets on every layer. Then it has KiCad's DRC say which
pads are left, and joins them:

  - a surface-mount pad with a missing connection gets a track to a via,
    which every fill of its net on the other layers then meets. The via is
    one of the net's that is near and can be reached, or else a new one at
    the nearest place that keeps the Default class's clearance from other
    copper on every layer. The pad's net must have a fill on another layer.
    Where there is no such place and the connection that is missing is to
    a through-hole pad, that pad is joined to its fills solidly, so that
    its copper meets the surface-mount pad's;
  - a through-hole pad that its fill does not reach, or reaches with fewer
    spokes than the board asks for, is joined to its fills solidly.

It fills and checks again until the DRC has nothing more of the kind or a
round changes nothing, and leaves the last DRC report at the path given.
What it cannot join it names: KiCad's DRC is the verdict, not this script.

Which pads are joined solidly is this script's to decide on every run: it
begins by giving each pad on a fill's net the connection its fills ask for,
so that a board with solid pads is joined as one without them is.

Runs under the system's Python, which has KiCad's pcbnew module; needs
kicad-cli (KiCad 10).
"""
import json
import math
import subprocess
import sys

import pcbnew

OWN_PAD_GAP = pcbnew.FromMM(0.15)   # a via in a pad draws the solder away from it
STEP = pcbnew.FromMM(0.1)           # of the search for a via's place
REACH = pcbnew.FromMM(4.0)          # how far from its pad a new via may be
SHARE = pcbnew.FromMM(2.5)          # how far from a pad a via it shares may be
STITCH = pcbnew.FromMM(10.0)        # between the vias that tie a net's fills together
ROUNDS = 5


def to_segment(x, y, start, end):
    dx, dy = end.x - start.x, end.y - start.y
    if dx == 0 and dy == 0:
        return math.hypot(x - start.x, y - start.y)
    along = max(0.0, min(1.0, ((x - start.x) * dx + (y - start.y) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - start.x - along * dx, y - start.y - along * dy)


def to_box(x, y, box):
    return math.hypot(max(box.GetLeft() - x, 0, x - box.GetRight()), max(box.GetTop() - y, 0, y - box.GetBottom()))


class Joiner:
    def __init__(self, board):
        self.board = board
        default = board.GetAllNetClasses()["Default"]
        self.via, self.hole, self.clearance = default.GetViaDiameter(), default.GetViaDrill(), default.GetClearance()
        self.net_settings = board.GetDesignSettings().m_NetSettings
        settings = board.GetDesignSettings()
        self.hole_to_hole, self.minimum_width = settings.m_HoleToHoleMin, settings.m_TrackMinWidth
        self.inside = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts][0].GetBoundingBox()
        self.inside.Inflate(-settings.m_CopperEdgeClearance)
        self.pads = [pad for footprint in board.GetFootprints() for pad in footprint.Pads()]

    def clear(self, x, y, radius, net, layer, own_pad):
        """True when a disc of the net's copper at (x, y) keeps its distance
        from other copper: on every layer when layer is None (a via), on
        that layer otherwise (a piece of track)."""
        if not (self.inside.GetLeft() + radius <= x <= self.inside.GetRight() - radius
                and self.inside.GetTop() + radius <= y <= self.inside.GetBottom() - radius):
            return False
        for pad in self.pads:
            if pad is own_pad or (layer is not None and not pad.IsOnLayer(layer)):
                continue
            if pad.GetNetname() != net:
                gap = self.clearance
            elif layer is None:
                gap = OWN_PAD_GAP
            else:
                continue
            if to_box(x, y, pad.GetBoundingBox()) < radius + gap:
                return False
        for track in self.board.GetTracks():
            is_via = track.Type() == pcbnew.PCB_VIA_T
            if track.GetNetname() == net:
                if is_via and layer is None:
                    position = track.GetPosition()
                    if math.hypot(x - position.x, y - position.y) < self.hole + self.hole_to_hole:
                        return False
            elif is_via:
                position = track.GetPosition()
                if math.hypot(x - position.x, y - position.y) < radius + track.GetWidth(pcbnew.F_Cu) / 2 + self.clearance:
                    return False
            elif layer is None or track.GetLayer() == layer:
                if to_segment(x, y, track.GetStart(), track.GetEnd()) < radius + track.GetWidth() / 2 + self.clearance:
                    return False
        return True

    def track_clear(self, pad, x, y, width):
        centre = pad.GetPosition()
        count = max(1, int(math.hypot(x - centre.x, y - centre.y) // STEP))
        return all(self.clear(centre.x + (x - centre.x) * i // count, centre.y + (y - centre.y) * i // count,
                              width / 2, pad.GetNetname(), pad.GetPrincipalLayer(), pad)
                   for i in range(count + 1))

    def add_track(self, pad, x, y, width):
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(pad.GetPosition())
        track.SetEnd(pcbnew.VECTOR2I(x, y))
        track.SetWidth(width)
        track.SetLayer(pad.GetPrincipalLayer())
        track.SetNet(pad.GetNet())
        self.board.Add(track)

    def add_via(self, x, y, net):
        via = pcbnew.PCB_VIA(self.board)
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetPosition(pcbnew.VECTOR2I(x, y))
        via.SetWidth(pcbnew.F_Cu, self.via)
        via.SetDrill(self.hole)
        via.SetNet(net)
        self.board.Add(via)

    def stitch(self, fills):
        """Tie the fills, which are of one net, together with vias on a grid.
        Returns how many."""
        net = fills[0].GetNet()
        copper = [fill.GetFilledPolysList(fill.GetLayerSet().Seq()[0]) for fill in fills]
        count = 0
        for x in range(self.inside.GetLeft() + STITCH // 2, self.inside.GetRight(), STITCH):
            for y in range(self.inside.GetTop() + STITCH // 2, self.inside.GetBottom(), STITCH):
                if (all(area.Contains(pcbnew.VECTOR2I(x, y)) for area in copper)
                        and self.clear(x, y, self.via / 2, net.GetNetname(), None, None)):
                    self.add_via(x, y, net)
                    count += 1
        return count

    def to_via(self, pad):
        """Join the pad to a via by a track. Returns what was done, or None
        when no via is within reach."""
        net, centre, box = pad.GetNetname(), pad.GetPosition(), pad.GetBoundingBox()
        class_width = self.net_settings.GetEffectiveNetClass(net).GetTrackWidth()
        width = max(self.minimum_width, min(class_width, box.GetWidth(), box.GetHeight()))
        shared = sorted((math.hypot(via.GetPosition().x - centre.x, via.GetPosition().y - centre.y), via.GetPosition())
                        for via in self.board.GetTracks() if via.Type() == pcbnew.PCB_VIA_T and via.GetNetname() == net)
        for distance, position in shared:
            if distance <= SHARE and self.track_clear(pad, position.x, position.y, width):
                self.add_track(pad, position.x, position.y, width)
                return f"a track to the via {pcbnew.ToMM(distance):.2f} mm away"
        steps = range(-REACH, REACH + 1, STEP)
        for dx, dy in sorted(((dx, dy) for dx in steps for dy in steps), key=lambda move: math.hypot(*move)):
            x, y = centre.x + dx, centre.y + dy
            if (to_box(x, y, box) >= self.via / 2 + OWN_PAD_GAP and self.clear(x, y, self.via / 2, net, None, pad)
                    and self.track_clear(pad, x, y, width)):
                self.add_via(x, y, pad.GetNet())
                self.add_track(pad, x, y, width)
                return f"a new via {pcbnew.ToMM(math.hypot(dx, dy)):.2f} mm away"
        return None


def main(board_path, report_path):
    board = pcbnew.LoadBoard(board_path)
    joiner = Joiner(board)
    pad_of = {pad.m_Uuid.AsString(): pad for pad in joiner.pads}
    fill_layers, fills_of = {}, {}
    board_fills = [zone for zone in board.Zones() if not zone.GetIsRuleArea()]
    for fill in board_fills:
        fill_layers.setdefault(fill.GetNetname(), set()).add(fill.GetLayerSet().Seq()[0])
        fills_of.setdefault(fill.GetNetname(), []).append(fill)

    def name(pad):
        return f"{pad.GetParentFootprint().GetReference()} pad {pad.GetNumber()} [{pad.GetNetname()}]"

    # A solid pad is saved in the board, and a fill that begins with one reaches pads it otherwise does not.
    for pad in joiner.pads:
        if pad.GetNetname() in fill_layers:
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_INHERITED)

    given_up = []
    for attempt in range(ROUNDS + 1):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        # The third argument keeps KiCad from rewriting the project file with the board.
        pcbnew.SaveBoard(board_path, board, True)
        done = subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json",
                               "--output", report_path, board_path], capture_output=True, text=True)
        if done.returncode:
            sys.exit(done.stdout + done.stderr)
        if attempt == 0:
            stitched = False
            for net, fills in sorted(fills_of.items()):
                if len(fills) > 1:
                    print(f"tied: the {len(fills)} fills of {net}, by {joiner.stitch(fills)} vias")
                    stitched = True
            if stitched:
                continue
        report = json.load(open(report_path, encoding="utf-8"))
        starved = [finding for finding in report["violations"] if finding["type"] == "starved_thermal"]
        to_via, solid, beside = [], [], {}
        for finding in report["unconnected_items"] + starved:
            found = [pad_of[item["uuid"]] for item in finding["items"] if item["uuid"] in pad_of]
            for pad in found:
                if pad.GetNetname() not in fill_layers or pad in given_up or pad in to_via or pad in solid:
                    continue
                if pad.HasHole():
                    # A through-hole pad that is missing a connection to another pad is left to that pad.
                    if finding in starved or len(found) == 1:
                        solid.append(pad)
                elif fill_layers[pad.GetNetname()] - {pad.GetPrincipalLayer()}:
                    to_via.append(pad)
                    beside[pad.m_Uuid.AsString()] = [other for other in found if other.HasHole()]
                else:
                    given_up.append(pad)
                    print(f"not joined: {name(pad)}, whose net has no fill on another layer")
        if (not to_via and not solid) or attempt == ROUNDS:
            break
        for pad in sorted(to_via, key=name):
            how = joiner.to_via(pad)
            thermal = [other for other in beside[pad.m_Uuid.AsString()]
                       if other.GetLocalZoneConnection() != pcbnew.ZONE_CONNECTION_FULL]
            if how:
                print(f"joined: {name(pad)}, by {how}")
            elif thermal:
                for other in thermal:
                    other.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
                print(f"joined: {name(pad)}, by joining {' and '.join(name(other) for other in thermal)} solidly")
            else:
                given_up.append(pad)
                print(f"not joined: {name(pad)}, no clear place for a via within {pcbnew.ToMM(REACH):g} mm")
        for pad in sorted(solid, key=name):
            if pad.GetLocalZoneConnection() == pcbnew.ZONE_CONNECTION_FULL:
                given_up.append(pad)
                print(f"not joined: {name(pad)}, which is joined solidly and still not reached")
            else:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
                print(f"joined: {name(pad)}, solidly")

    for fill in board_fills:
        layer = fill.GetLayerSet().Seq()[0]
        pieces = fill.GetFilledPolysList(layer)
        areas = sorted((pieces.Outline(i).Area() / 1e14 for i in range(pieces.OutlineCount())), reverse=True)
        print(f"fill {board.GetLayerName(layer):7} {fill.GetNetname():8} {sum(areas):6.1f} cm2 in {len(areas)} "
              f"piece{'s' if len(areas) != 1 else ''}" + (f", the largest {areas[0]:.1f} cm2" if len(areas) > 1 else ""))
    tracks = list(board.GetTracks())
    vias = sum(1 for track in tracks if track.Type() == pcbnew.PCB_VIA_T)
    length = sum(track.GetLength() for track in tracks if track.Type() != pcbnew.PCB_VIA_T)
    print(f"{len(tracks) - vias} track segments, {vias} vias, {pcbnew.ToMM(length):.0f} mm of track")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
