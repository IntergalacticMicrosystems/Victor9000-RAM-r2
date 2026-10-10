#!/usr/bin/env python3
"""Post-route silk tidy: move each footprint's Reference text to the nearest
candidate spot around its part that overlaps no pad/via/exposed copper, no
other silk and stays clear of the board edge; shrink if needed, hide only
when nothing fits. Re-splices the .kicad_pro netclasses after SaveBoard.

    HOME=/root python3 tidy_silk.py
"""
import json
import os
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
BRD = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "Victor9000-RAM-r2.kicad_pcb")
PRO = BRD[:-len(".kicad_pcb")] + ".kicad_pro"
CLR = 0.2           # silk-to-copper / silk-to-silk margin (mm)
EDGE = 0.4          # silk-to-edge margin (mm)
TONGUE_Y = 101.27   # nothing below the tongue line (finger mask opening)


def rect(bb, m=0.0):
    return (ToMM(bb.GetLeft()) - m, ToMM(bb.GetTop()) - m,
            ToMM(bb.GetRight()) + m, ToMM(bb.GetBottom()) + m)


def hit(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def main():
    net_settings = json.load(open(PRO))["net_settings"]
    board = pcbnew.LoadBoard(BRD)
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)

    copper = [rect(p.GetBoundingBox(), CLR) for f in board.GetFootprints() for p in f.Pads()]
    copper += [rect(t.GetBoundingBox(), CLR) for t in board.GetTracks()
               if t.GetClass() == "PCB_VIA"]
    silk = []                                   # fixed silk: footprint graphics + board texts
    for f in board.GetFootprints():
        for g in f.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != "PCB_TEXT":
                silk.append(rect(g.GetBoundingBox(), CLR))
    label = None                                # the "128K" text goes beside JP1
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS:
            if isinstance(d, pcbnew.PCB_TEXT) and d.GetText() == "128K":
                label = d
            else:
                silk.append(rect(d.GetBoundingBox(), CLR))

    def inside(r):
        if r[3] > TONGUE_Y - EDGE:
            return False
        for x, y in ((r[0] - EDGE, r[1] - EDGE), (r[2] + EDGE, r[1] - EDGE),
                     (r[0] - EDGE, r[3] + EDGE), (r[2] + EDGE, r[3] + EDGE)):
            if not outline.Contains(VECTOR2I(FromMM(x), FromMM(y))):
                return False
        return True

    placed, moved, hidden = [], 0, []
    fps = sorted(board.GetFootprints(), key=lambda f: -len(f.Pads()))   # big parts first
    items = [(f, f.Reference()) for f in fps]
    if label is not None:
        sj = board.FindFootprintByReference("JP1")
        items.insert(0, (sj, label))
    for f, t in items:
        if not t.IsVisible():
            continue
        fb = rect(f.GetBoundingBox(False, False))   # body without texts
        cx, cy = (fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2
        done = False
        for size in (1.0, 0.8, 0.6):
            t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
            t.SetTextThickness(FromMM(0.15 if size >= 0.8 else 0.12))
            cands = []
            for ang in (0, 90):
                t.SetTextAngleDegrees(ang)
                w, h = ToMM(t.GetBoundingBox().GetWidth()), ToMM(t.GetBoundingBox().GetHeight())
                for k in range(0, 9):                    # rings outward
                    g = 0.3 + 0.5 * k
                    for x, y in ((cx, fb[1] - g - h / 2), (cx, fb[3] + g + h / 2),
                                 (fb[0] - g - w / 2, cy), (fb[2] + g + w / 2, cy),
                                 (fb[0] - g - w / 2, fb[1] - g - h / 2),
                                 (fb[2] + g + w / 2, fb[1] - g - h / 2),
                                 (fb[0] - g - w / 2, fb[3] + g + h / 2),
                                 (fb[2] + g + w / 2, fb[3] + g + h / 2)):
                        cands.append((k, abs(x - cx) + abs(y - cy), ang, x, y))
            for _, _, ang, x, y in sorted(cands):
                t.SetTextAngleDegrees(ang)
                t.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
                r = rect(t.GetBoundingBox())
                if inside(r) and not any(hit(r, o) for o in copper + silk + placed):
                    placed.append(rect(t.GetBoundingBox(), CLR))
                    moved += 1
                    done = True
                    break
            if done:
                break
        if not done:
            t.SetVisible(False)
            hidden.append(t.GetText() if t is label else f.GetReference())

    pcbnew.SaveBoard(BRD, board)
    pro = json.load(open(PRO))
    pro["net_settings"] = net_settings
    with open(PRO, "w") as fh:
        json.dump(pro, fh, indent=2)
    print(f"SILK TIDY OK: {moved} refs placed, hidden: {hidden or 'none'}")


if __name__ == "__main__":
    main()
