#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""netlist_import.py -- what KiCad's Import Netlist would do to the board with a netlist.

    scripts/netlist_import.py [--by-designator] <netlist> <board>

Links footprints by tstamps, the setting the board's netlist is judged with
(AGENTS.md). --by-designator links them by reference designator instead.

Prints the lines the PCB editor's File > Import > Netlist lists under
"Changes to Be Applied" for the netlist and the board, in KiCad's own
wording, and exits 1 when one of them is a change or an error. A netlist
that agrees with the board gives no change.

It is a check for whoever works on the circuit, not a verdict on it. KiCad's
dialog is the authority, and the last check of a netlist is a person opening
the board in KiCad and importing it. This script runs no KiCad: it reads the
two files and applies the rules of KiCad 10.0.8's pcbnew/netlist_reader
(board_netlist_updater.cpp, kicad_netlist_reader.cpp) as read from its
source, so a later KiCad can differ from it.

A footprint's link is the path to a symbol that it holds, and matching by it
is the dialog's "Link footprints using component tstamps (unique ids)";
matching by reference designator is the dialog's other choice. For each part
KiCad then compares:

  - the value, and the footprint's name (listed by the dialog only with
    "Replace footprints with those specified in netlist" ticked);
  - the link to a symbol: the netlist's sheet path and tstamps against the
    footprint's path;
  - the fields: every field the netlist gives the part has to be on the
    footprint with the same text. A field that only the footprint has is
    left alone;
  - the sheet's name and file, and the footprint filters;
  - the attributes "exclude from BOM", "do not place" and "exclude from
    position files", and the jumper settings;
  - each pad's net by name. A pad with a number, on copper, that has no
    net on the board and no pin in the netlist is a warning.

An update also sets each pad's pin function and pin type to the netlist's
without listing it; those are printed here marked "silently". Groups,
component classes, units and variants are compared only for being absent on
both sides, and are named when either side has one.

A footprint that is on the board and not in the netlist is listed by the
dialog only with "Delete footprints with no components in netlist" ticked.
"""
import re
import sys

NOT_FIELDS = ("Reference", "Value", "Footprint", "Component Class")
NOT_COMPARED = ("group", "units", "component_classes", "variants")


def parse(text):
    """The s-expressions in the text as nested lists of strings."""
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()"]+', text)

    def read(index):
        out = []
        while index < len(tokens):
            token = tokens[index]
            if token == "(":
                sub, index = read(index + 1)
                out.append(sub)
            elif token == ")":
                return out, index + 1
            else:
                out.append(token[1:-1] if token.startswith('"') else token)
                index += 1
        return out, index

    return read(0)[0][0]


def kids(node, name):
    return [child for child in node if isinstance(child, list) and child and child[0] == name]


def val(node, name):
    found = kids(node, name)
    return found[0][1] if found and len(found[0]) > 1 else ""


def val_list(node, name):
    return [child[1] for child in kids(node, name) if len(child) > 1]


def read_netlist(path):
    """The netlist's parts by designator, in the file's order, each with what KiCad's reader keeps of it."""
    root = parse(open(path, encoding="utf-8").read())
    parts = {}
    for comp in kids(kids(root, "components")[0], "comp"):
        sheetpath = kids(comp, "sheetpath")
        tstamps = [stamp for node in kids(comp, "tstamps") for stamp in node[1:]]
        sheet_tstamps = val(sheetpath[0], "tstamps") if sheetpath else ""
        link = "/".join(filter(None, sheet_tstamps.split("/") + tstamps[:1]))
        parts[val(comp, "ref")] = {
            "value": val(comp, "value"),
            "footprint": val(comp, "footprint"),
            "fields": {val(field, "name"): next((text for text in field[1:] if isinstance(text, str)), "")
                       for fields in kids(comp, "fields") for field in kids(fields, "field")},
            "properties": {val(node, "name"): val(node, "value") for node in kids(comp, "property")},
            "sheetname": val(sheetpath[0], "names") if sheetpath else "",
            "tstamps": tstamps,
            "path": "/" + link if link else "",
            "jumpers": val(comp, "duplicate_pin_numbers_are_jumpers") == "1",
            "jumper_groups": sorted(sorted(val_list(group, "pin")) for groups in kids(comp, "jumper_pin_groups")
                                    for group in kids(groups, "group")),
            "more": [name for name in NOT_COMPARED if any(len(node) > 1 for node in kids(comp, name))],
            "pins": {},
        }
    for net in kids(kids(root, "nets")[0], "net"):
        if not val(net, "code").lstrip("-").isdigit() or int(val(net, "code")) < 1:
            continue
        name = val(net, "name") or "N-00000" + val(net, "code")
        for node in kids(net, "node"):
            if val(node, "ref") in parts:
                parts[val(node, "ref")]["pins"].setdefault(
                    val(node, "pin"), (name, val(node, "pinfunction"), val(node, "pintype")))
    return parts


def read_board(path):
    """The board's footprints, in the file's order, and the nets of its zones."""
    root = parse(open(path, encoding="utf-8").read())
    footprints = []
    for footprint in kids(root, "footprint"):
        properties = {node[1]: node[2] if len(node) > 2 and isinstance(node[2], str) else ""
                      for node in kids(footprint, "property")}
        attributes = [word for node in kids(footprint, "attr") for word in node[1:]]
        footprints.append({
            "footprint": footprint[1],
            "reference": properties.get("Reference", ""),
            "value": properties.get("Value", ""),
            "fields": {name: text for name, text in properties.items()
                       if name not in ("Reference", "Value", "Component Class", "ki_fp_filters")},
            "filters": properties.get("ki_fp_filters", ""),
            "path": val(footprint, "path"),
            "sheetname": val(footprint, "sheetname"),
            "sheetfile": val(footprint, "sheetfile"),
            "attributes": attributes,
            "jumpers": val(footprint, "duplicate_pad_numbers_are_jumpers") == "yes",
            "jumper_groups": sorted(sorted(group[1:]) for groups in kids(footprint, "jumper_pad_groups")
                                    for group in groups[1:] if isinstance(group, list)),
            "more": [name for name in ("units", "component_classes") if any(len(node) > 1 for node in kids(footprint, name))],
            "pads": [{"number": pad[1],
                      "copper": any(layer.endswith(".Cu") for node in kids(pad, "layers") for layer in node[1:]),
                      "net": next((node[-1] for node in kids(pad, "net")), ""),
                      "pinfunction": val(pad, "pinfunction"),
                      "pintype": val(pad, "pintype")} for pad in kids(footprint, "pad")],
        })
    zone_nets = {next((node[-1] for node in kids(zone, "net")), "") for zone in kids(root, "zone")} - {""}
    groups = len(kids(root, "group"))
    return footprints, zone_nets, groups


def report(netlist_path, board_path, by_tstamps):
    parts = read_netlist(netlist_path)
    footprints, zone_nets, groups = read_board(board_path)
    changes, silent, warnings, errors = [], [], [], []
    used = set()
    nets_of_pads = {}
    board_nets = {pad["net"] for footprint in footprints for pad in footprint["pads"]} | zone_nets
    added_nets = set()
    if groups:
        warnings.append(f"The board has {groups} groups, which this script does not compare.")

    for reference, part in parts.items():
        if "exclude_from_board" in part["properties"]:
            continue
        if ":" not in part["footprint"] and part["footprint"]:
            warnings.append(f"Warning: {reference} footprint '{part['footprint']}' is missing a library name. Use the full "
                            f"'Library:Footprint' format to avoid repeated update notifications.")
        if by_tstamps:
            links = {"/" + "/".join(filter(None, part["path"].rsplit("/", 1)[0].split("/") + [stamp]))
                     for stamp in part["tstamps"]} if part["tstamps"] else set()
            matching = [index for index, footprint in enumerate(footprints) if footprint["path"] in links]
        else:
            matching = [index for index, footprint in enumerate(footprints)
                        if footprint["reference"].lower() == reference.lower()]
        matching = [index for index in matching if index not in used]
        if not matching:
            if not part["footprint"]:
                errors.append(f"Cannot add {reference} (no footprint assigned).")
            else:
                changes.append(f"Add {reference} (footprint '{part['footprint']}').")
            continue
        index = next((index for index in matching if footprints[index]["footprint"] == part["footprint"]), matching[0])
        used.add(index)
        footprint = footprints[index]
        name = footprint["reference"]

        if footprint["footprint"] != part["footprint"]:
            changes.append(f"Change {name} footprint from '{footprint['footprint']}' to '{part['footprint']}'. "
                           f"(with \"Replace footprints with those specified in netlist\")")
        if name != reference:
            changes.append(f"Change {name} reference designator to {reference}.")
        if footprint["value"] != part["value"]:
            changes.append(f"Change {name} value from {footprint['value']} to {part['value']}.")
        if footprint["path"] != part["path"]:
            changes.append(f"Update {name} symbol association from {footprint['path']} to {part['path']}.")

        given = {field: text for field, text in part["fields"].items() if field not in NOT_FIELDS}
        if any(field not in footprint["fields"] or footprint["fields"][field] != text for field, text in given.items()):
            differing = [field for field, text in given.items() if footprint["fields"].get(field) != text]
            changes.append(f"Update {name} fields. ({', '.join(differing)})")

        sheetname = part["sheetname"] or part["properties"].get("Sheetname", "")
        if sheetname != footprint["sheetname"]:
            changes.append(f"Update {name} sheetname to '{sheetname}'.")
        if part["properties"].get("Sheetfile", "") != footprint["sheetfile"]:
            changes.append(f"Update {name} sheetfile to '{part['properties'].get('Sheetfile', '')}'.")
        if part["properties"].get("ki_fp_filters", "") != footprint["filters"]:
            changes.append(f"Update {name} footprint filters to '{part['properties'].get('ki_fp_filters', '')}'.")
        for key, attribute, text in (("exclude_from_bom", "exclude_from_bom", "'exclude from BOM' fabrication"),
                                     ("dnp", "dnp", "'Do not place' fabrication"),
                                     ("exclude_from_pos_files", "exclude_from_pos_files",
                                      "'exclude from position files' fabrication")):
            if (key in part["properties"]) != (attribute in footprint["attributes"]):
                changes.append(f"{'Add' if key in part['properties'] else 'Remove'} {name} {text} attribute.")
        if part["jumpers"] != footprint["jumpers"]:
            changes.append(f"{'Add' if part['jumpers'] else 'Remove'} {name} 'duplicate pad numbers are jumpers' attribute.")
        if part["jumper_groups"] != footprint["jumper_groups"]:
            changes.append(f"Update {name} jumper pad groups")
        for what in part["more"]:
            warnings.append(f"The netlist gives {reference} {what}, which this script does not compare.")
        for what in footprint["more"]:
            warnings.append(f"The board's {name} has {what}, which this script does not compare.")

        for pad in footprint["pads"]:
            pin = part["pins"].get(pad["number"])
            net, pinfunction, pintype = pin or ("", "", "")
            if pad["pinfunction"] != pinfunction:
                silent.append(f"{name} pad {pad['number']}: pin function '{pad['pinfunction']}' to '{pinfunction}'")
            if pad["pintype"] != pintype:
                silent.append(f"{name} pad {pad['number']}: pin type '{pad['pintype']}' to '{pintype}'")
            if not pin or not pad["copper"]:
                if pad["net"]:
                    changes.append(f"Disconnect {name} pin {pad['number']}.")
                elif pad["copper"] and pad["number"]:
                    warnings.append(f"No net found for component {name} pad {pad['number']} "
                                    f"(no pin {pad['number']} in symbol).")
                nets_of_pads[index, id(pad)] = ""
            else:
                if pad["net"] != net:
                    if net not in board_nets and net not in added_nets:
                        added_nets.add(net)
                        changes.append(f"Add net {net}.")
                    if pad["net"]:
                        changes.append(f"Reconnect {name} pin {pad['number']} from {pad['net']} to {net}.")
                    else:
                        changes.append(f"Connect {name} pin {pad['number']} to {net}.")
                nets_of_pads[index, id(pad)] = net
        for number in part["pins"]:
            if not number:
                errors.append(f"Symbol {reference} has pins with no number.  These pins can not be matched to pads in "
                              f"{footprint['footprint']}.")
            elif not any(pad["number"] == number for pad in footprint["pads"]):
                errors.append(f"{reference} pad {number} not found in {footprint['footprint']}.")

    for index, footprint in enumerate(footprints):
        if index in used or "board_only" in footprint["attributes"]:
            continue
        in_netlist = (any(part["path"] == footprint["path"] for part in parts.values()) if by_tstamps
                      else footprint["reference"] in parts)
        if not in_netlist:
            changes.append(f"Remove unused footprint {footprint['reference']}. (with \"Delete footprints with no components in netlist\")")
        for pad in footprint["pads"]:
            nets_of_pads[index, id(pad)] = pad["net"]
    for net in sorted(zone_nets - set(nets_of_pads.values())):
        warnings.append(f"Copper zone on net \"{net}\" has no pads connected.")
    return changes, silent, warnings, errors


if __name__ == "__main__":
    arguments = [argument for argument in sys.argv[1:] if argument != "--by-designator"]
    if len(arguments) != 2:
        sys.exit(__doc__)
    by_tstamps = "--by-designator" not in sys.argv[1:]
    changes, silent, warnings, errors = report(arguments[0], arguments[1], by_tstamps)
    print(f"Using {'tstamps (unique IDs)' if by_tstamps else 'reference designators'} to match symbols and footprints.")
    for line in changes + warnings + errors:
        print(line)
    for line in silent:
        print(f"silently: {line}")
    print(f"{len(changes)} changes, {len(silent)} made silently; total warnings: {len(warnings)}, errors: {len(errors)}.")
    sys.exit(1 if changes or silent or errors else 0)
