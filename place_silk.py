#!/usr/bin/env python3
"""Post-placement: delete the PLACE-BLOCK zones, then board silk for Victor9000-RAM-r2 (run after place.py). Re-runnable: removes
its own texts first. Re-splices the .kicad_pro netclasses after SaveBoard.

    HOME=/root python3 place_silk.py
"""
import json
import os
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
BRD = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "Victor9000-RAM-r2.kicad_pcb")
PRO = BRD[:-len(".kicad_pcb")] + ".kicad_pro"
TITLE = "Victor 9000 RAM r2"
LABEL = "128K"


def text(board, s, x, y, h, w):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    t.SetTextSize(VECTOR2I(FromMM(h), FromMM(h)))
    t.SetTextThickness(FromMM(w))
    board.Add(t)


def main():
    net_settings = json.load(open(PRO))["net_settings"]
    board = pcbnew.LoadBoard(BRD)
    for z in list(board.Zones()):        # place_anchors.py's placement blockers
        if z.GetZoneName().startswith("PLACE-BLOCK"):
            board.Delete(z)
    for d in list(board.GetDrawings()):
        if isinstance(d, pcbnew.PCB_TEXT) and d.GetText() in (TITLE, LABEL):
            board.Delete(d)
    text(board, TITLE, 113.0, 64.5, 1.5, 0.25)            # free top-left corner
    sj = board.FindFootprintByReference("JP1").GetBoundingBox(False)
    # beside JP1 (left if there is room before the board edge, else right),
    # vertically centred on it, 0.6 mm clear of its bbox
    lx = pcbnew.ToMM(sj.GetLeft()) - 0.6 - 1.7
    if lx - 1.7 < 100.5:
        lx = pcbnew.ToMM(sj.GetRight()) + 0.6 + 1.7
    text(board, LABEL, lx, pcbnew.ToMM(sj.GetCenter().y), 1.0, 0.15)
    pcbnew.SaveBoard(BRD, board)
    pro = json.load(open(PRO))
    pro["net_settings"] = net_settings
    with open(PRO, "w") as f:
        json.dump(pro, f, indent=2)
    print("SILK OK")


if __name__ == "__main__":
    main()
