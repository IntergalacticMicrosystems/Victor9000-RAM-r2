#!/usr/bin/env python3
"""Stage 4a for Victor9000-RAM-r2: board outline + anchors (scripted stand-in
for the human). Re-runnable: clears its own Edge.Cuts/keepout first.

    HOME=/root python3 place_anchors.py

- Edge.Cuts: body 100..173 x 62..101.27 plus the r1 card-edge tongue.
- J1 at (120, 100) rot 0; anchors U1-U6 placed + LOCKED, each orientation
  chosen by reading back pad coordinates (not by rotation convention).
- JLCPCB 2-layer board rules; netclasses in the .kicad_pro are snapshotted
  before SaveBoard and re-spliced after (SaveBoard rewrites the .kicad_pro).
- Card edge: a LOCKED stub on every connected finger (own layer, pad top ->
  y 100.6); keepouts: no pour/vias for y >= 101.0, no tracks for y >= 101.65
  (just below the stubs' round ends), so no routing enters the tongue.
- Temporary LOCKED F.Cu "PLACE-BLOCK" zones keep place.py out of the U5->U1
  D corridor and the U6|U1 lane; place_silk.py deletes them after placement.
"""
import json
import os
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
BRD = os.path.join(HERE, "Victor9000-RAM-r2.kicad_pcb")
PRO = os.path.join(HERE, "Victor9000-RAM-r2.kicad_pro")

OUTLINE = [(100.00, 62.00), (173.00, 62.00), (173.00, 101.27), (169.21, 101.27),
           (169.21, 108.51), (168.58, 109.14), (104.44, 109.14), (103.81, 108.51),
           (103.81, 101.27), (100.00, 101.27)]
TONGUE_TOP = 101.27
KEEPOUT = "J1 tongue keepout"            # no pour / vias, y >= KO_POUR
KEEPOUT_T = "J1 tongue track keepout"    # no tracks, y >= KO_TRACK
KO_POUR, KO_TRACK = 101.0, 101.65
STUB_IN, STUB_OUT = 101.35, 100.6        # stub: 0.08 mm into the pad -> 100.6
BLOCK = "PLACE-BLOCK"
BLOCKS = [(132.0, 84.0, 135.6, 89.5),    # D corridor U5 B port -> U1 D pins,
          (137.4, 84.0, 141.0, 89.5),    # minus a C2 slot under U1 pins 33/34
          (135.6, 87.6, 137.4, 89.5),
          (121.0, 66.0, 127.0, 88.0)]    # lane between U6 and U1's left end

# ref: (x, y, predicate over {pad: (x, y)} relative to the part centre)
def bottom(pins):          # these pins on the bottom row (+y), the rest on top
    return lambda P: all((P[p][1] > 0) == (int(p) in pins) for p in P)

# Floorplan r2 (orchestrator, after route attempts 1-3): translators left, data
# transceiver U5 directly under the SRAM's D pins, latch right, decoder U6 up
# in the empty top-left with its S inputs (9-11) on the bottom row. Lower row
# at y 93.0, not 94.5 (lever 1 after route attempt 4: BA15 and +5V stayed open in
# the 2.5 mm strip between the A ports and the finger stubs; now 4 mm).
ANCHORS = {
    "U1": (136.5, 76.5, lambda P: bottom(range(23, 45))(P) and P["23"][0] < P["44"][0]),
    "U3": (107.0, 93.0, bottom(range(1, 13))),
    "U4": (118.5, 93.0, bottom(range(1, 13))),
    "U5": (135.9, 93.0, bottom(range(1, 13))),
    "U2": (163.0, 93.0, bottom(range(1, 11))),
    "U6": (112.0, 79.0, bottom(range(9, 17))),
}

RULES = dict(min_track=0.127, min_clear=0.127, via_dia=0.6, via_drill=0.3,
             hole_to_hole=0.5, edge=0.3, hole_clear=0.2)


def pads_rel(fp):
    c = fp.GetPosition()
    return {p.GetNumber(): (ToMM(p.GetPosition().x - c.x), ToMM(p.GetPosition().y - c.y))
            for p in fp.Pads()}


def signal_rats(board, fp, placed):
    """Sum over the part's signal pads of distance to the nearest same-net pad
    on another PLACED footprint (J1 + anchors; power/pour nets excluded)."""
    by_net = {}
    for f in board.GetFootprints():
        if f.GetReference() == fp.GetReference() or f.GetReference() not in placed:
            continue
        for p in f.Pads():
            by_net.setdefault(p.GetNetname(), []).append(p.GetPosition())
    tot = 0.0
    for p in fp.Pads():
        n = p.GetNetname()
        if n in ("GND", "+5V", "+3V3") or n.startswith("unconnected") or n not in by_net:
            continue
        a = p.GetPosition()
        tot += min(ToMM((a - b).EuclideanNorm()) for b in by_net[n])
    return tot


def main():
    net_settings = json.load(open(PRO))["net_settings"]
    board = pcbnew.LoadBoard(BRD)
    fps = {f.GetReference(): f for f in board.GetFootprints()}

    # ---- clear previous run's outline / keepout -----------------------------
    for d in list(board.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            board.Delete(d)
    for z in list(board.Zones()):
        if z.GetZoneName() in (KEEPOUT, KEEPOUT_T) or z.GetZoneName().startswith(BLOCK):
            board.Delete(z)
    for t in list(board.GetTracks()):
        if t.IsLocked() and min(ToMM(t.GetStart().y), ToMM(t.GetEnd().y)) >= STUB_OUT - 0.01:
            board.Delete(t)

    # ---- J1 ------------------------------------------------------------------
    j1 = fps["J1"]
    j1.SetLocked(False)
    j1.SetPosition(VECTOR2I(FromMM(120.0), FromMM(100.0)))
    j1.SetOrientationDegrees(0)
    j1.SetAllowSolderMaskBridges(True)   # one mask opening over all fingers (r1)
    j1.SetLocked(True)
    xs = []
    for p in j1.Pads():
        x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        n = int(p.GetNumber())
        want = pcbnew.F_Cu if n >= 26 else pcbnew.B_Cu
        if abs(y - 105.08) > 0.005 or not p.IsOnLayer(want) or p.IsOnLayer(
                pcbnew.B_Cu if want == pcbnew.F_Cu else pcbnew.F_Cu):
            sys.exit(f"ANCHORS FAIL: J1 pad {n} at ({x:.3f},{y:.3f}) wrong layer/row")
        xs.append(x)
    if abs(min(xs) - 106.03) > 0.005 or abs(max(xs) - 166.99) > 0.005:
        sys.exit(f"ANCHORS FAIL: J1 finger span {min(xs):.3f}..{max(xs):.3f}")

    # ---- anchors: choose rotation by reading back pad coordinates -----------
    chosen = {}
    for ref, (x, y, pred) in ANCHORS.items():
        fp = fps[ref]
        fp.SetLocked(False)
        fp.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        ok = []
        for rot in (0, 90, 180, 270):
            fp.SetOrientationDegrees(rot)
            if pred(pads_rel(fp)):
                ok.append((signal_rats(board, fp, {"J1", *ANCHORS}), rot))
        if len(ok) != 1:
            sys.exit(f"ANCHORS FAIL: {ref} rotations satisfying the rule: {ok}")
        rats, rot = min(ok)
        fp.SetOrientationDegrees(rot)
        fp.SetLocked(True)
        chosen[ref] = (x, y, rot, ok)

    # ---- clearance from the tongue / overlap check ---------------------------
    for ref in ANCHORS:
        ymax = max(ToMM(fps[ref].GetCourtyard(pcbnew.F_CrtYd).BBox().GetBottom()),
                   max(ToMM(p.GetBoundingBox().GetBottom()) for p in fps[ref].Pads()))
        if TONGUE_TOP - ymax < 2.5:
            sys.exit(f"ANCHORS FAIL: {ref} reaches y={ymax:.2f}, <2.5 mm from tongue")
    refs = list(ANCHORS)
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            ca = fps[a].GetCourtyard(pcbnew.F_CrtYd).BBox()
            cb = fps[b].GetCourtyard(pcbnew.F_CrtYd).BBox()
            if ca.Intersects(cb):
                sys.exit(f"ANCHORS FAIL: courtyards {a}/{b} overlap")

    # ---- board rules (JLCPCB standard 2-layer) ------------------------------
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(1.6))
    ds.m_TrackMinWidth = FromMM(RULES["min_track"])
    ds.m_MinClearance = FromMM(RULES["min_clear"])
    ds.m_ViasMinSize = FromMM(RULES["via_dia"])
    ds.m_MinThroughDrill = FromMM(RULES["via_drill"])
    ds.m_HoleToHoleMin = FromMM(RULES["hole_to_hole"])
    ds.m_CopperEdgeClearance = FromMM(RULES["edge"])
    ds.m_HoleClearance = FromMM(RULES["hole_clear"])

    # ---- Edge.Cuts: one closed polygon ---------------------------------------
    poly = pcbnew.PCB_SHAPE(board)
    poly.SetShape(pcbnew.SHAPE_T_POLY)
    poly.SetLayer(pcbnew.Edge_Cuts)
    poly.SetWidth(FromMM(0.05))
    poly.SetFilled(False)
    poly.SetPolyPoints([VECTOR2I(FromMM(x), FromMM(y)) for x, y in OUTLINE])
    board.Add(poly)

    # ---- finger stubs (locked), then the tongue keepouts ----------------------
    nets = 0
    for p in j1.Pads():
        n = p.GetNetname()
        if not n or n.startswith("unconnected"):
            continue
        x = p.GetPosition().x
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(VECTOR2I(x, FromMM(STUB_IN)))
        t.SetEnd(VECTOR2I(x, FromMM(STUB_OUT)))
        t.SetLayer(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
        t.SetWidth(FromMM(0.5 if n in ("+5V", "+3V3", "GND") else 0.2))
        t.SetNet(p.GetNet())
        t.SetLocked(True)
        board.Add(t)
        nets += 1

    def rule_area(name, y0, tracks):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetZoneName(name)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowTracks(tracks)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        o = z.Outline()
        o.NewOutline()
        for x, y in [(103.81, y0), (169.21, y0), (169.21, 109.14), (103.81, 109.14)]:
            o.Append(FromMM(x), FromMM(y))
        board.Add(z)
    rule_area(KEEPOUT, KO_POUR, False)
    rule_area(KEEPOUT_T, KO_TRACK, True)

    # ---- temporary placement blockers (deleted by place_silk.py) ------------
    for i, (x0, y0, x1, y1) in enumerate(BLOCKS):
        z = pcbnew.ZONE(board)
        z.SetZoneName(f"{BLOCK} {i}")
        z.SetLayer(pcbnew.F_Cu)
        z.SetLocked(True)
        o = z.Outline()
        o.NewOutline()
        for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            o.Append(FromMM(x), FromMM(y))
        board.Add(z)

    pcbnew.SaveBoard(BRD, board)

    # SaveBoard rewrote the .kicad_pro from defaults: re-splice the netclasses
    pro = json.load(open(PRO))
    pro["net_settings"] = net_settings
    with open(PRO, "w") as f:
        json.dump(pro, f, indent=2)

    for ref, (x, y, rot, ok) in chosen.items():
        print(f"{ref}: ({x}, {y}) rot {rot}  candidates (rats_mm, rot) = "
              + ", ".join(f"({r:.1f}, {o_})" for r, o_ in ok))
    print("ANCHORS OK: J1 + %d anchors locked, outline %d vertices, %d finger stubs, "
          "netclasses %s" % (len(chosen), len(OUTLINE), nets,
                             [c["name"] for c in net_settings["classes"]]))


if __name__ == "__main__":
    main()
