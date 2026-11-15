#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""cost_estimate.py -- what an order of the board costs at JLCPCB, delivered to Norway.

    scripts/cost_estimate.py [--quantity <boards>] <board>
    scripts/cost_estimate.py [--quantity <boards>] --board-price <USD>
                             --shipping "<method>=<USD>" [--shipping ...] <board>

Prints the estimate as Markdown, each figure with its source, for a comment
on an issue. Every board of the order is assembled.

Two prices come from JLCPCB's quote page (https://cart.jlcpcb.com/quote),
which gives them without a sign-in for values typed in, and only in a
browser: the price of the bare boards and the price of each shipping method.
The first form prints the values to type in, and the estimate as far as it
goes without the two. The second form takes them and prints the whole
estimate, with one total for each shipping method.

The rest the script reads and fetches as it runs:

  the board          the copper layers, the size, the parts JLCPCB places
                     (scripts/fab_files.py: the ones with an LCSC number)
                     and their joints;
  the parts          each part's price for the quantity, its library class,
                     its minimum placement quantity and its stock, from
                     JLCPCB's parts catalogue;
  the assembly fees  from https://jlcpcb.com/help/article/pcb-assembly-price,
                     the column for Economic assembly, which takes boards
                     with every placed part on one side;
  the rate           US dollars in Norwegian kroner, from Norges Bank.

Norwegian VAT is 25 % of goods and freight. JLCPCB charges it at checkout on
orders from private persons with goods worth up to NOK 3 000
(https://jlcpcb.com/help/article/norway-vat-on-e-commerce-voec-rules), and
then no customs duty applies and nothing is paid to the carrier.

The board file is not changed.
"""
import argparse
import collections
import csv
import dataclasses
import datetime
import html.parser
import io
import json
import re
import sys
import urllib.request

import pcbnew

from fab_files import placed_footprints

QUOTE_PAGE = "https://cart.jlcpcb.com/quote"
FEE_PAGE = "https://jlcpcb.com/help/article/pcb-assembly-price"
CATALOGUE = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
CATALOGUE_PAGE = "https://jlcpcb.com/parts"
VAT_PAGE = "https://jlcpcb.com/help/article/norway-vat-on-e-commerce-voec-rules"
RATE = "https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?lastNObservations=1&format=csv"
BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
VAT = 0.25
VAT_AT_CHECKOUT_LIMIT_NOK = 3000


@dataclasses.dataclass
class Board:
    copper_layers: int
    width_mm: float
    height_mm: float
    thickness_mm: float
    designators: dict       # LCSC number -> the designators of that part line
    values: dict            # LCSC number -> the value printed for the line
    surface_mount_joints: int
    through_hole_joints: int
    parts_on_back: int


@dataclasses.dataclass
class PartLine:
    number: str
    value: str
    model: str
    extended: bool
    stock: int
    needed: int
    charged: int
    unit_price: float

    @property
    def price(self):
        return self.charged * self.unit_price


@dataclasses.dataclass
class Fees:
    updated: str
    setup: float
    stencil: float
    extended_part: float
    surface_mount_joint: float
    through_hole_joint: float


def read_board(path):
    board = pcbnew.LoadBoard(path)
    outline = [drawing for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    extent = outline[0].GetBoundingBox()
    for drawing in outline[1:]:
        extent.Merge(drawing.GetBoundingBox())
    # A drawing's bounding box reaches half its line's width past the line on each side.
    line_width = outline[0].GetWidth()
    designators, values = collections.defaultdict(list), {}
    joints = collections.Counter()
    parts_on_back = 0
    for footprint, number in placed_footprints(board):
        designators[number].append(footprint.GetReference())
        values[number] = footprint.GetValue()
        joints.update(pad.GetAttribute() for pad in footprint.Pads())
        parts_on_back += footprint.IsFlipped()
    return Board(board.GetCopperLayerCount(),
                 pcbnew.ToMM(extent.GetWidth() - line_width), pcbnew.ToMM(extent.GetHeight() - line_width),
                 pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness()),
                 dict(designators), values,
                 joints[pcbnew.PAD_ATTRIB_SMD], joints[pcbnew.PAD_ATTRIB_PTH], parts_on_back)


def fetch(url, body=None):
    headers = {"User-Agent": BROWSER, "Accept": "application/json, text/html, */*"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as answer:
        return answer.read().decode("utf-8")


def part_line(number, value, needed):
    """The catalogue's entry for an LCSC number, priced for the quantity needed."""
    answer = json.loads(fetch(CATALOGUE, json.dumps({"keyword": number, "currentPage": 1, "pageSize": 25}).encode()))
    entries = answer["data"]["componentPageInfo"]["list"] or []
    entry = next((entry for entry in entries if entry["componentCode"] == number), None)
    if entry is None:
        sys.exit(f"{number} is not in JLCPCB's parts catalogue")
    # A guess: that a line is charged at least the catalogue's minimum placement quantity.
    charged = max(needed, entry["leastPatchNumber"])
    unit_price = [step["productPrice"] for step in entry["componentPrices"] if step["startNumber"] <= charged][-1]
    extended = entry["componentLibraryType"] == "expand" and not entry["preferredComponentFlag"]
    return PartLine(number, value, entry["componentModelEn"], extended, entry["stockCount"], needed, charged, unit_price)


class TableRows(html.parser.HTMLParser):
    """The rows of a page's tables, each a list of its cells' text."""

    def __init__(self):
        super().__init__()
        self.rows, self.cell = [], []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self.cell, self.in_cell = [], True

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.rows[-1].append(" ".join("".join(self.cell).split()))
            self.in_cell = False

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)


def assembly_fees():
    """JLCPCB's fees for Economic assembly: the second column of the fee page's table."""
    page = fetch(FEE_PAGE)
    fee_table = TableRows()
    fee_table.feed(page)
    economic = {row[0]: row[1] for row in fee_table.rows if len(row) > 1}

    def dollars(fee):
        cell = next((cell for name, cell in economic.items() if name.startswith(fee)), "")
        amount = re.search(r"\$([0-9.]+)", cell)
        if not amount:
            sys.exit(f"{FEE_PAGE} has no fee \"{fee}\" for Economic assembly")
        return float(amount.group(1))

    updated = re.search(r"Last updated on ([A-Z][a-z]+ \d+, \d+)", page)
    return Fees(updated.group(1) if updated else "no date on the page",
                dollars("Setup fee"), dollars("Stencil"), dollars("Feeder Loading"),
                dollars("SMT Assembly"), dollars("Pre-reflow Soldering"))


def kroner_per_dollar():
    row = list(csv.DictReader(io.StringIO(fetch(RATE)), delimiter=";"))[-1]
    return float(row["OBS_VALUE"]), row["TIME_PERIOD"]


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quantity", type=int, default=5, help="boards ordered and assembled (JLCPCB's smallest order is 5)")
    parser.add_argument("--board-price", type=float, help="the quote page's price of the bare boards, in USD")
    parser.add_argument("--shipping", action="append", default=[], metavar="METHOD=USD",
                        help="a shipping method of the quote page and its price")
    parser.add_argument("board")
    arguments = parser.parse_args()
    if (arguments.board_price is None) != (not arguments.shipping):
        parser.error("--board-price and --shipping come together: both are read from the quote page")
    quantity = arguments.quantity
    shipping = {method: float(price) for method, price in (choice.rsplit("=", 1) for choice in arguments.shipping)}

    board = read_board(arguments.board)
    if board.parts_on_back:
        sys.exit(f"placed parts on the back: {board.parts_on_back}. Parts on both sides need JLCPCB's Standard "
                 "assembly, whose fees this script does not hold")
    fees = assembly_fees()
    lines = [part_line(number, board.values[number], len(designators) * quantity)
             for number, designators in board.designators.items()]
    rate, rate_day = kroner_per_dollar()
    today = datetime.date.today().isoformat()

    parts = sum(len(designators) for designators in board.designators.values())
    extended = [line for line in lines if line.extended]
    surface_mount_joints = board.surface_mount_joints * quantity
    through_hole_joints = board.through_hole_joints * quantity
    fee_source = f"{FEE_PAGE} (updated {fees.updated})"
    goods = [
        ("Assembly setup, Economic", fees.setup, fee_source),
        ("Stencil, Economic", fees.stencil, "same page"),
        (f"Extended parts: {len(extended)} types × {fees.extended_part:.2f}", len(extended) * fees.extended_part, "same page"),
        (f"Placement: {surface_mount_joints} surface-mount joints × {fees.surface_mount_joint}",
         surface_mount_joints * fees.surface_mount_joint, "same page; joints counted on the board"),
    ]
    if through_hole_joints:
        goods.append((f"Through-hole joints of the placed parts: {through_hole_joints} × {fees.through_hole_joint}",
                      through_hole_joints * fees.through_hole_joint, "same page, the pre-reflow rate"))
    goods.append((f"Parts: {sum(line.needed for line in lines)} pieces in {len(lines)} lines",
                  sum(line.price for line in lines), f"JLCPCB's parts catalogue, {CATALOGUE_PAGE}"))
    quoted = arguments.board_price is not None
    if quoted:
        goods.insert(0, (f"Boards: {quantity} × {board.width_mm:g} × {board.height_mm:g} mm, {board.copper_layers} layers",
                         arguments.board_price, f"quote page, {QUOTE_PAGE}, values typed in"))
    goods_total = sum(price for _, price, _ in goods)

    print(f"## What {quantity} assembled boards cost at JLCPCB, delivered to Norway\n")
    if quoted:
        orders = {method: (goods_total + price) * (1 + VAT) for method, price in shipping.items()}
        print(table([""] + list(shipping), [
            ["Goods"] + [f"${goods_total:.2f}"] * len(shipping),
            ["Shipping"] + [f"${price:.2f}" for price in shipping.values()],
            [f"Norwegian VAT, {VAT:.0%}"] + [f"${(goods_total + price) * VAT:.2f}" for price in shipping.values()],
            ["**Order**"] + [f"**${order:.2f}**" for order in orders.values()],
            ["**Per board**"] + [f"**${order / quantity:.2f}**" for order in orders.values()],
            ["Order in NOK"] + [f"{order * rate:.0f}" for order in orders.values()],
            ["Per board in NOK"] + [f"{order / quantity * rate:.0f}" for order in orders.values()],
        ]))
    else:
        print(f"Without the bare boards and shipping, which are read from {QUOTE_PAGE} with ship-to Norway: "
              f"{board.copper_layers} layers, {board.width_mm:g} × {board.height_mm:g} mm, quantity {quantity}, "
              f"thickness {board.thickness_mm:g} mm, and the finish and colour of the order. "
              "Read the price of the boards and the price of each shipping method.")
    print(f"\nRead on {today}. NOK at Norges Bank's rate of {rate_day}, {rate} NOK per USD.")

    print(f"\n### The board\n\n- {board.copper_layers} copper layers, {board.width_mm:g} × {board.height_mm:g} mm, "
          f"{board.thickness_mm:g} mm thick (`{arguments.board}`).")
    print(f"- JLCPCB places {parts} parts in {len(lines)} lines, all on the front: {board.surface_mount_joints} "
          f"surface-mount joints a board and {board.through_hole_joints} through-hole joints on those parts. "
          "A part without an LCSC number is soldered by hand and is not on the order.")

    print("\n### Goods\n")
    print(table(["Line", "USD", "Source"],
                [(name, f"{price:.2f}", source) for name, price, source in goods]
                + [("**Goods**" if quoted else "**Goods without the boards**", f"**{goods_total:.2f}**", "")]))

    print("\n### Parts\n")
    print(table(["Part", "LCSC", "Catalogue name", "Library", "Needed", "Charged", "Unit USD", "Line USD", "Stock"],
                [(line.value, line.number, line.model, "extended" if line.extended else "basic", line.needed,
                  line.charged, f"{line.unit_price:.4f}", f"{line.price:.3f}", line.stock) for line in lines]))

    print("\n### What the figures rest on\n")
    print("- **Economic assembly:** every placed part is on the front. The service's other limits (thickness, colour, "
          "finish, quantity, smallest package, pin pitch) are on https://jlcpcb.com/capabilities/pcb-assembly-capabilities "
          "and are not checked here.")
    print("- **Charged** is a guess: that a part line is charged at least the catalogue's minimum placement quantity. "
          "The unit price is the catalogue's for the quantity charged.")
    if through_hole_joints:
        print("- **Through-hole joints of placed parts** (a socket's shell tabs) are charged at the fee table's pre-reflow "
              "rate, which is a reading of the table. JLCPCB's order page shows what they cost.")
    short = [line for line in lines if line.stock < line.charged]
    print("- **Stock:** " + ("JLCPCB has every line in stock." if not short else
                             "JLCPCB has too few of " + ", ".join(f"{line.value} ({line.number})" for line in short) + "."))
    goods_kroner = goods_total * rate
    if quoted:
        print(f"- **VAT:** the goods are NOK {goods_kroner:.0f}, "
              + (f"under the NOK {VAT_AT_CHECKOUT_LIMIT_NOK} up to which JLCPCB charges Norwegian VAT at checkout "
                 f"({VAT_PAGE}); no customs duty applies and nothing is paid to the carrier."
                 if goods_kroner <= VAT_AT_CHECKOUT_LIMIT_NOK else
                 f"over the NOK {VAT_AT_CHECKOUT_LIMIT_NOK} up to which JLCPCB charges Norwegian VAT at checkout "
                 f"({VAT_PAGE}): VAT, customs clearance and the carrier's fee are settled at the border, and the "
                 "totals above do not hold."))
    print("- **Not counted:** JLCPCB's coupons, its optional services, the card's currency conversion, and the parts "
          "soldered by hand.")


if __name__ == "__main__":
    main()
