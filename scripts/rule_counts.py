#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""rule_counts.py -- count the findings in kicad-cli's DRC reports by type, or list the errors.

    rule_counts.py <report.json> ...
    rule_counts.py --errors <report.json> ...

Without an option, prints one line per report, severity and type, so that
two runs can be compared with diff.

With --errors, prints each finding of severity error: what KiCad says is
wrong, then every item it names (the pad with its part and net, the track
with its net and layer) and where on the board that item is.

Exit code 1 when a report holds a finding of severity error. The project
file sets each type's severity; a missing connection and copper that
joins two nets are errors there.
"""
import collections
import json
import os
import sys


def findings(report):
    """The findings of a DRC report: the rule violations and the missing connections."""
    yield from report.get("violations", [])
    yield from report.get("unconnected_items", [])


def print_counts(name, found):
    counts = collections.Counter((finding["severity"], finding["type"]) for finding in found)
    for (severity, kind), count in sorted(counts.items()):
        print(f"{name:<18} {severity:<8} {kind:<28} {count}")
    if not counts:
        print(f"{name:<18} no findings")


def print_errors(errors, units):
    for error in errors:
        print(f"{error['description']} ({error['type']})")
        for item in error["items"]:
            print(f"    {item['description']}, at {item['pos']['x']:.2f}, {item['pos']['y']:.2f} {units}")


arguments = sys.argv[1:]
list_errors = arguments[:1] == ["--errors"]
has_error = False
for path in arguments[list_errors:]:
    with open(path, encoding="utf-8") as file:
        report = json.load(file)
    found = list(findings(report))
    errors = [finding for finding in found if finding["severity"] == "error"]
    has_error = has_error or bool(errors)
    if list_errors:
        print_errors(errors, report["coordinate_units"])
    else:
        print_counts(os.path.splitext(os.path.basename(path))[0], found)
sys.exit(1 if has_error else 0)
