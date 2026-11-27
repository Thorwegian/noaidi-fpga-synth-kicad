#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""kicad_netlist.py -- the netlist, as KiCad's PCB editor takes it without
proposing a change to the board.

The board is edited in KiCad, and its File > Import > Netlist is what the
circuit in text is held against: the netlist is right when that dialog,
linking footprints by reference designator, lists no change. So the netlist
states what the board's footprints hold, and nothing they do not:

  - each part's designator, value and footprint;
  - each part's link: the sheet path, which is the tags of the blocks the
    part is made in, and the tstamps, SKiDL's UUIDs of that path and of the
    part's own (gen_netlist.py). A footprint holds the two as its path and
    the path in words as its sheet name, and by its path KiCad knows the
    footprint again when the part's designator changes;
  - the fields the circuit gives a part, which is its LCSC number. KiCad
    compares every field of the netlist with the footprint's, and leaves a
    field that only the footprint has as it is;
  - "exclude from BOM", "exclude from position files" and "do not place",
    for a part the circuit marks so;
  - each net by its name, with its pins and its classes.

It has no pin types: KiCad copies those onto the pads without listing it.
SKiDL's own generate_netlist() writes them, and a tag and a source line as
fields of every part.

A pin the circuit leaves unconnected, or marks as not connected, is written
as a net of its own named unconnected-(<ref>-Pad<pin>), which is what
eeschema writes for a pin that ends up alone in its net. KiCad's importer
warns about every numbered pad on copper that the netlist says nothing
about, so the netlist says something about these. A pad without a number
gets no such warning and needs no pin: the two shielding contacts of each
DIN jack are pads of that kind, soldered for the hold alone (esp32.py,
midi_input).
"""
from skidl import *
from skidl.tools.kicad10.gen_netlist import gen_part_tstamp, gen_sheetpath, gen_sheetpath_tstamp

PROPERTIES = ("dnp", "exclude_from_bom", "exclude_from_pos_files")


def quoted(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def write(path):
    circuit = default_circuit
    circuit.merge_net_names()
    circuit.check_for_empty_footprints()
    # circuit.check_tags() without the root: SKiDL warns that its own root has
    # no tag, and its netlist writer refuses a root that has one.
    for part in circuit.parts:
        part.check_tag(create_if_missing=True)
    for node in circuit.nodes:
        if node is not circuit.root:
            node.check_tag()
    lines = ['(export (version "E")', "  (design", '    (source "circuit/board.py")', '    (tool "SKiDL"))',
             "  (components"]
    for part in sorted(circuit.parts, key=lambda part: str(part.ref)):
        lines += ["    (comp", f"      (ref {quoted(part.ref)})", f"      (value {quoted(part.value)})",
                  f"      (footprint {quoted(part.footprint)})",
                  f"      (sheetpath (names {quoted(gen_sheetpath(part.hiertuple))})"
                  f" (tstamps {quoted(gen_sheetpath_tstamp(part.hiertuple))}))",
                  f"      (tstamps {quoted(gen_part_tstamp(part))})"]
        if part.fields:
            lines.append("      (fields")
            lines += [f"        (field (name {quoted(name)}) {quoted(text)})" for name, text in part.fields.items()]
            lines[-1] += ")"
        lines += [f"      (property (name {quoted(name)}))" for name in PROPERTIES if getattr(part, name, False)]
        lines[-1] += ")"
    lines[-1] += ")"
    lines.append("  (nets")
    for net in circuit.get_nets():
        net.netclasses = "Default"
    nets = [(str(net.name), ",".join(reversed(net.netclasses.by_priority())), list(net.pins))
            for net in circuit.get_nets()]
    nets += [(f"unconnected-({pin.part.ref}-Pad{pin.num})", "Default", [pin]) for pin in circuit.NC.pins]
    for code, (name, classes, pins) in enumerate(sorted(nets, key=lambda net: net[0]), 1):
        lines += ["    (net", f'      (code "{code}")', f"      (name {quoted(name)})", f"      (class {quoted(classes)})"]
        lines += [f"      (node (ref {quoted(pin.part.ref)}) (pin {quoted(pin.num)}))" for pin in sorted(pins, key=str)]
        lines[-1] += ")"
    lines[-1] += "))"
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
