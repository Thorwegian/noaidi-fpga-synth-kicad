#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""netlist_summary.py -- read KiCad netlists and boards, and compare their connectivity.

    netlist_summary.py <a>                 list the parts and nets
    netlist_summary.py <a> <b>             compare; exit 1 when they differ
    netlist_summary.py --within <a> <b>    check that <a> is contained in <b>; exit 1 if not

<a> and <b> are each a netlist (.net, from kicad-cli or SKiDL), a board
(.kicad_pcb), or several netlists joined with '+' (the sheets of one design:
nets of the same name are merged, as global labels are).

The comparison is by connectivity, not by text: parts by designator (value,
footprint), nets by the set of pins on them. A net's name is compared only
when both sides named it (KiCad's Net-(...) and SKiDL's N$n are generated
names). One-pin nets are dropped: KiCad lists an unconnected pin as a net of
its own, SKiDL leaves it out.

--within is the check for one sheet against the whole board: every part of
<a> is in <b> with the same value and footprint, and the pins of every net
of <a> sit together on one net of <b>.
"""
import re
import sys


def parse(text):
    tok = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()"]+', text)

    def read(i):
        out = []
        while i < len(tok):
            x = tok[i]
            if x == '(':
                sub, i = read(i + 1)
                out.append(sub)
            elif x == ')':
                return out, i + 1
            else:
                out.append(x[1:-1] if x.startswith('"') else x)
                i += 1
        return out, i

    return read(0)[0][0]


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def val(node, name):
    k = kids(node, name)
    return k[0][1] if k and len(k[0]) > 1 else ''


def generated(name):
    return name.startswith(('Net-(', 'unconnected-(', 'N$'))


def read_netlist(path):
    root = parse(open(path, encoding='utf-8').read())
    parts = {}
    for c in kids(kids(root, 'components')[0], 'comp'):
        parts[val(c, 'ref')] = (val(c, 'value'), val(c, 'footprint'))
    nets = {}
    for n in kids(kids(root, 'nets')[0], 'net'):
        nets[val(n, 'name')] = {(val(x, 'ref'), val(x, 'pin')) for x in kids(n, 'node')}
    return parts, nets


def read_board(path):
    root = parse(open(path, encoding='utf-8').read())
    parts, nets = {}, {}
    for fp in kids(root, 'footprint'):
        props = {p[1]: p[2] for p in kids(fp, 'property') if len(p) > 2}
        ref = props.get('Reference', '')
        parts[ref] = (props.get('Value', ''), fp[1])
        for pad in kids(fp, 'pad'):
            net = kids(pad, 'net')
            if not net or not pad[1]:
                continue
            name = net[0][-1]
            if name:
                nets.setdefault(name, set()).add((ref, pad[1]))
    return parts, nets


def summary(spec):
    parts, nets = {}, {}
    for path in spec.split('+'):
        p, n = read_board(path) if path.endswith('.kicad_pcb') else read_netlist(path)
        parts.update(p)
        for name, pins in n.items():
            nets.setdefault(name, set()).update(pins)
    return parts, {name: frozenset(pins) for name, pins in nets.items()}


def pins_text(pins):
    return ' '.join(f'{r}.{p}' for r, p in sorted(pins))


def show(spec):
    parts, nets = summary(spec)
    print(len(parts), 'parts')
    for ref in sorted(parts):
        print('  ', ref, *parts[ref])
    print(len(nets), 'nets')
    for name in sorted(nets):
        print('  ', name, '|', pins_text(nets[name]))


def compare(a, b):
    pa, na = summary(a)
    pb, nb = summary(b)
    diffs = []
    for ref in sorted(set(pa) | set(pb)):
        if pa.get(ref) != pb.get(ref):
            diffs.append(f'part {ref}: {pa.get(ref)} != {pb.get(ref)}')
    ca = {pins: name for name, pins in na.items() if len(pins) > 1}
    cb = {pins: name for name, pins in nb.items() if len(pins) > 1}
    for pins in sorted(set(ca) | set(cb), key=sorted):
        if pins not in cb:
            diffs.append(f'net {ca[pins]} only in {a}: {pins_text(pins)}')
        elif pins not in ca:
            diffs.append(f'net {cb[pins]} only in {b}: {pins_text(pins)}')
        elif ca[pins] != cb[pins] and not generated(ca[pins]) and not generated(cb[pins]):
            diffs.append(f'net name: {ca[pins]} != {cb[pins]} ({pins_text(pins)})')
    for d in diffs:
        print(d)
    print(f'{len(pa)} and {len(pb)} parts, {len(ca)} and {len(cb)} connected nets:',
          'identical' if not diffs else f'{len(diffs)} differences')
    return 1 if diffs else 0


def within(a, b):
    pa, na = summary(a)
    pb, nb = summary(b)
    where = {pin: name for name, pins in nb.items() for pin in pins}
    diffs = []
    for ref in sorted(pa):
        if ref not in pb:
            diffs.append(f'part {ref} is not in {b}')
        elif pa[ref] != pb[ref]:
            diffs.append(f'part {ref}: {pa[ref]} != {pb[ref]}')
    checked = 0
    for name in sorted(na):
        pins = na[name]
        if len(pins) < 2:
            continue
        checked += 1
        homes = {where.get(pin) for pin in pins}
        if None in homes:
            missing = [pin for pin in pins if pin not in where]
            diffs.append(f'net {name}: {pins_text(missing)} on no net in {b}')
        elif len(homes) > 1:
            diffs.append(f'net {name} is split over {sorted(homes)} in {b}')
        else:
            home = homes.pop()
            if home != name and not generated(name) and not generated(home):
                diffs.append(f'net name: {name} != {home}')
    for d in diffs:
        print(d)
    print(f'{len(pa)} parts and {checked} connected nets of {a} checked within {b}:',
          'all present and consistent' if not diffs else f'{len(diffs)} differences')
    return 1 if diffs else 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) == 1:
        show(args[0])
    elif len(args) == 2:
        sys.exit(compare(*args))
    elif len(args) == 3 and args[0] == '--within':
        sys.exit(within(args[1], args[2]))
    else:
        sys.exit(__doc__)
