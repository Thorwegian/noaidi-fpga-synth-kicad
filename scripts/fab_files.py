#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""fab_files.py -- the files JLCPCB's order page takes, from the board.

    scripts/fab_files.py [--out <folder>] <board>

Writes into build/fab/, or into the folder given:

  gerbers.zip    one Gerber file for each copper layer, solder mask,
                 silkscreen and paste layer and for the board's edge, and
                 the drill files for plated and for unplated holes;
  bom.csv        the parts JLCPCB places, one line for each LCSC number;
  placement.csv  where each of those parts sits, and how it is turned.

The Gerber and drill settings are the ones JLCPCB asks for
(https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9):
Protel file name extensions, by which JLCPCB tells the layers apart and
counts the inner ones, the extended X2 format, drill files in Excellon with
millimetres, decimal zeros and absolute origin, plated and unplated holes
in separate files. The columns of the two lists are the ones of
https://jlcpcb.com/help/article/how-to-generate-the-bom-and-centroid-file-from-kicad.

JLCPCB places the parts that have an LCSC number, which is the footprint's
field `LCSC`. A part without one is soldered by hand and is in neither list.

A position is the footprint's own, in millimetres from the same origin as
the Gerber files, with y upwards. JLCPCB's library holds some packages
turned against KiCad's footprint for them, and how a package is drawn there
goes by the part, not by the package's name. So the script fetches each
part's package from that library (EasyEDA's component API, by LCSC number,
kept in build/tools/jlcpcb-library/) and turns the board's footprint until
every pad number lies on the library's pad of that number. A part's
rotation in the list is its orientation on the board less that turn, with
the library's drawing taken as JLCPCB's 0 degrees.

A footprint whose pad numbers lie where the library has them at no turn
stops the script: its pads are not where the part's pins are.

The board file is not changed.
"""
import argparse
import collections
import csv
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

import pcbnew

LIBRARY_URL = "https://easyeda.com/api/products/{number}/components?version=6.4.19.5"
LIBRARY_FOLDER = "build/tools/jlcpcb-library"
LIBRARY_UNIT_MM = 0.254     # the library's coordinates are in units of 10 mil
# The API answers a request without a browser's name with 403, and now and then one with it.
BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
ATTEMPTS = 4
OTHER_LAYERS = ["F.Mask", "B.Mask", "F.Silkscreen", "B.Silkscreen", "F.Paste", "B.Paste", "Edge.Cuts"]


def library_pads(number):
    """The pads of a part's package in JLCPCB's library, as {pad number:
    [(x, y), ...]} in millimetres with y downwards, as in KiCad."""
    path = os.path.join(LIBRARY_FOLDER, f"{number}.json")
    if not os.path.exists(path):
        request = urllib.request.Request(LIBRARY_URL.format(number=number),
                                         headers={"Accept": "application/json", "User-Agent": BROWSER})
        for attempt in range(1, ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as answer:
                    fetched = answer.read()
                json.loads(fetched)["result"]["packageDetail"]["dataStr"]["shape"]
                break
            except (OSError, ValueError, KeyError, TypeError) as error:
                if attempt == ATTEMPTS:
                    sys.exit(f"JLCPCB's library gave no package for {number}: {error}")
                time.sleep(3 * attempt)
        os.makedirs(LIBRARY_FOLDER, exist_ok=True)
        with open(path, "wb") as file:
            file.write(fetched)
    with open(path, encoding="utf-8") as file:
        package = json.load(file)["result"]["packageDetail"]["dataStr"]
    origin_x, origin_y = float(package["head"]["x"]), float(package["head"]["y"])
    pads = collections.defaultdict(list)
    for shape in package["shape"]:
        # PAD~shape~x~y~width~height~layer~net~number~...
        fields = shape.split("~")
        if fields[0] == "PAD":
            pads[fields[8]].append(((float(fields[2]) - origin_x) * LIBRARY_UNIT_MM,
                                    (float(fields[3]) - origin_y) * LIBRARY_UNIT_MM))
    return pads


def turned(pads, degrees):
    """The pads with their footprint turned counter-clockwise as seen on the
    board, which is KiCad's positive direction, y downwards."""
    cosine, sine = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return {number: [(x * cosine + y * sine, -x * sine + y * cosine) for x, y in places]
            for number, places in pads.items()}


def own_pads(footprint):
    """The footprint's pads as {pad number: [(x, y), ...]} in millimetres
    from the footprint's position, with the footprint not turned."""
    centre = footprint.GetPosition()
    pads = collections.defaultdict(list)
    for pad in footprint.Pads():
        pads[pad.GetNumber()].append((pcbnew.ToMM(pad.GetPosition().x - centre.x), pcbnew.ToMM(pad.GetPosition().y - centre.y)))
    return turned(pads, -footprint.GetOrientationDegrees())


def about_their_middle(pads, numbers):
    """The pads of the numbers given, from the middle of the rectangle around them."""
    places = [place for number in numbers for place in pads[number]]
    middle_x = (min(x for x, _ in places) + max(x for x, _ in places)) / 2
    middle_y = (min(y for _, y in places) + max(y for _, y in places)) / 2
    return {number: [(x - middle_x, y - middle_y) for x, y in pads[number]] for number in numbers}


def furthest_apart(ours, theirs):
    """The largest distance from a pad to the nearest pad of its number in the other set."""
    return max(min(math.dist(place, other) for other in second[number])
               for first, second in ((ours, theirs), (theirs, ours)) for number in first for place in first[number])


def turn_to_library(footprint, number):
    """The degrees the footprint is turned by, counter-clockwise, to lie as
    the part's package is drawn in JLCPCB's library.

    The pads that have the same number on both sides are compared. A pad
    fits when it is nearer the library's pad of its number than half the
    smallest distance between two pads of the package: nearer its own place
    than any other pad's."""
    designator = footprint.GetReference()
    if footprint.IsFlipped():
        sys.exit(f"{designator} is on the back: the turn against JLCPCB's library is worked out for the front only")
    ours, library = own_pads(footprint), library_pads(number)
    shared = sorted(set(ours) & set(library))
    if not shared:
        sys.exit(f"{designator}: no pad of its footprint has a number that JLCPCB's package for {number} has")
    theirs = about_their_middle(library, shared)
    places = sorted({place for group in theirs.values() for place in group})
    fits_within = min(math.dist(first, second) for index, first in enumerate(places) for second in places[index + 1:]) / 2
    turns = [degrees for degrees in (0, 90, 180, 270)
             if furthest_apart(about_their_middle(turned(ours, degrees), shared), theirs) < fits_within]
    if len(turns) != 1:
        sys.exit(f"{designator}: its footprint's pad numbers lie where JLCPCB's package for {number} has them "
                 f"at {'no turn' if not turns else 'the turns ' + ', '.join(map(str, turns))}: "
                 f"the pads are not where the part's pins are")
    return turns[0]


def run(*command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(command)}\n{done.stdout}{done.stderr}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="build/fab")
    parser.add_argument("board")
    arguments = parser.parse_args()
    out = arguments.out
    plots = os.path.join(out, "gerbers")
    os.makedirs(plots, exist_ok=True)
    for name in os.listdir(plots):
        os.remove(os.path.join(plots, name))

    board = pcbnew.LoadBoard(arguments.board)
    copper = [board.GetLayerName(layer) for layer in board.GetEnabledLayers().CuStack()]
    run("kicad-cli", "pcb", "export", "gerbers", "--output", plots + "/", "--layers", ",".join(copper + OTHER_LAYERS),
        "--subtract-soldermask", "--check-zones", arguments.board)
    run("kicad-cli", "pcb", "export", "drill", "--output", plots + "/", "--format", "excellon",
        "--drill-origin", "absolute", "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
        "--excellon-oval-format", "alternate", "--excellon-separate-th", arguments.board)
    # KiCad also writes a job file, which is no part of what JLCPCB asks for.
    plotted = sorted(name for name in os.listdir(plots) if not name.endswith(".gbrjob"))
    with zipfile.ZipFile(os.path.join(out, "gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for name in plotted:
            archive.write(os.path.join(plots, name), name)

    lines = collections.defaultdict(list)
    placements, turned_parts = [], []
    for footprint, number in placed_footprints(board):
        designator = footprint.GetReference()
        package = str(footprint.GetFPID().GetLibItemName())
        lines[(number, footprint.GetValue(), package)].append(designator)
        turn = turn_to_library(footprint, number)
        if turn:
            turned_parts.append(f"{designator} by {turn}")
        position = footprint.GetPosition()
        placements.append((designator, f"{pcbnew.ToMM(position.x):.4f}", f"{-pcbnew.ToMM(position.y):.4f}",
                           "bottom" if footprint.IsFlipped() else "top",
                           f"{(footprint.GetOrientationDegrees() - turn) % 360:g}"))

    with open(os.path.join(out, "bom.csv"), "w", encoding="utf-8", newline="") as file:
        rows = csv.writer(file)
        rows.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (number, value, package), designators in sorted(lines.items(), key=lambda line: natural(line[1][0])):
            rows.writerow([value, ",".join(designators), package, number])
    with open(os.path.join(out, "placement.csv"), "w", encoding="utf-8", newline="") as file:
        rows = csv.writer(file)
        rows.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        rows.writerows(placements)

    print(f"gerbers.zip: {len(plotted)} files: {' '.join(plotted)}")
    print(f"bom.csv: {len(placements)} parts in {len(lines)} lines")
    print(f"placement.csv: {len(placements)} parts, {sum(1 for row in placements if row[3] == 'bottom')} of them on the back; "
          f"drawn turned in JLCPCB's library: {', '.join(turned_parts) or 'none'}")


def placed_footprints(board):
    """The footprints JLCPCB places, each with its LCSC number, J9 before J14."""
    for footprint in sorted(board.GetFootprints(), key=lambda footprint: natural(footprint.GetReference())):
        number = footprint.GetFieldText("LCSC") if footprint.HasField("LCSC") else ""
        if number:
            yield footprint, number


def natural(designator):
    """J9 before J14."""
    letters, digits = re.match(r"(\D*)(\d*)", designator).groups()
    return letters, int(digits or 0)


if __name__ == "__main__":
    main()
