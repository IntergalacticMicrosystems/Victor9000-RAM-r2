#!/usr/bin/env python3
"""Victor 9000 RAM expansion r2 -- schematic generator (Stage 3).

Run from anywhere with the eda_blocks venv:
    /root/sync/eda_blocks/.venv/bin/python gen_sch.py

1. Builds the project symbol library v9k_r2.kicad_sym:
   - IS62WV51216BLL-55TLI, SN74LVC4245APWR: partbroker's easyeda2kicad symbols
     (pin numbers checked against the datasheets) with pin electrical types set
     (easyeda ships every pin as "unspecified");
   - Expansion_Connector: harvested from the r1 schematic
     (Victor9000-RAM-Clock.kicad_sch); power pins set passive, +5V/GND get
     PWR_FLAGs instead.
2. Authors Victor9000-RAM-r2.kicad_sch (+ .kicad_pro with netclasses).
Pin numbers below are datasheet pin numbers (see project.toml / the report).
"""
import copy
import os
import sys

sys.path.insert(0, "/root/sync/eda_blocks")
from kiutils.schematic import Schematic
from kiutils.symbol import SymbolLib
from kiutils.items.common import Justify
from edablock.gensch import SchBuilder

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = "Victor9000-RAM-r2"
LIBNICK = "v9k_r2"
LIBFILE = os.path.join(HERE, f"{LIBNICK}.kicad_sym")

FP_TSOP44 = "Package_SO:TSOP-II-44_10.16x18.41mm_P0.8mm"
FP_TSSOP24 = "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"
FP_EDGE = f"{LIBNICK}:Victor Expansion Edge Connector"


# --------------------------------------------------------------------------
# project symbol library
# --------------------------------------------------------------------------
def _pins(sym):
    for p in sym.pins:
        yield p
    for u in sym.units:
        yield from _pins(u)


def _set_prop(sym, key, val):
    for p in sym.properties:
        if p.key == key:
            p.value = val


def build_symbol_lib():
    ee = SymbolLib.from_file(os.path.join(HERE, "easyeda2kicad/easyeda2kicad.kicad_sym"))
    ees = {s.entryName: s for s in ee.symbols}

    sram = copy.deepcopy(ees["IS62WV51216BLL-55TLI"])
    for p in _pins(sram):
        if p.name in ("VDD", "GND"):
            p.electricalType = "power_in"
        elif p.name.startswith("I/O"):
            p.electricalType = "bidirectional"
        else:                                   # A0-A18, CS1, WE, OE, LB, UB
            p.electricalType = "input"
    _set_prop(sram, "Footprint", FP_TSOP44)

    xcvr = copy.deepcopy(ees["SN74LVC4245APWR"])
    for p in _pins(xcvr):
        if p.name in ("VCCA", "VCCB", "GND"):
            p.electricalType = "power_in"
        elif p.name in ("DIR", "~{OE}"):
            p.electricalType = "input"
        else:                                   # A1-A8, B1-B8
            p.electricalType = "bidirectional"
    _set_prop(xcvr, "Footprint", FP_TSSOP24)

    old = Schematic.from_file(os.path.join(HERE, "Victor9000-RAM-Clock.kicad_sch"))
    conn = copy.deepcopy(next(s for s in old.libSymbols
                              if s.entryName == "Expansion_Connector"))
    power_pins = {"31", "35", "39", "44", "36", "37"}   # GND x4, +5V x2
    for p in _pins(conn):
        if p.number in power_pins:
            p.electricalType = "passive"
    for p in _pins(conn):
        if p.number == "11":
            p.name = "~{RD}"        # r1 symbol lost the overbar on /RD
    _set_prop(conn, "Footprint", FP_EDGE)
    _set_prop(conn, "Reference", "J")

    lib = SymbolLib()
    lib.version = ee.version
    lib.generator = "gen_sch.py"
    lib.filePath = LIBFILE
    for s in (sram, xcvr, conn):
        s.libraryNickname = None
        for u in s.units:
            u.libraryNickname = None
        lib.symbols.append(s)
    lib.to_file()


# --------------------------------------------------------------------------
# schematic
# --------------------------------------------------------------------------
P = {  # part definitions: libId, libfile, entry, value, footprint, fields
    "sram": (f"{LIBNICK}:IS62WV51216BLL-55TLI", LIBFILE, "IS62WV51216BLL-55TLI",
             "IS62WV51216BLL-55TLI", FP_TSOP44,
             {"MPN": "IS62WV51216BLL-55TLI", "LCSC": "C11315"}),
    "573": ("74xx:74LS573", "74xx.kicad_sym", "74LS573", "74LVC573A",
            "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
            {"MPN": "74LVC573APW,118", "LCSC": "C6096"}),
    "4245": (f"{LIBNICK}:SN74LVC4245APWR", LIBFILE, "SN74LVC4245APWR",
             "SN74LVC4245A", FP_TSSOP24,
             {"MPN": "SN74LVC4245APWR", "LCSC": "C7859"}),
    "151": ("74xx:74LS151", "74xx.kicad_sym", "74LS151", "74HCT151",
            "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm",
            {"MPN": "74HCT151D,653", "LCSC": "C547364"}),
    "1g04": ("74xGxx:74LVC1G04", "74xGxx.kicad_sym", "74LVC1G04", "74LVC1G04",
             "Package_TO_SOT_SMD:SOT-23-5",
             {"MPN": "SN74LVC1G04DBVR", "LCSC": "C19829658"}),
    "0832": ("74xGxx:74LVC1G0832", "74xGxx.kicad_sym", "74LVC1G0832", "74LVC1G0832",
             "Package_TO_SOT_SMD:SOT-23-6",
             {"MPN": "SN74LVC1G0832DBVR", "LCSC": "C206101"}),
    "ldo": ("Regulator_Linear:XC6206PxxxMR", "Regulator_Linear.kicad_sym",
            "XC6206PxxxMR", "XC6206P332MR", "Package_TO_SOT_SMD:SOT-23",
            {"MPN": "XC6206P332MR-G", "LCSC": "C5446"}),
    "rn": ("Device:R_Pack04_Split", "Device.kicad_sym", "R_Pack04_Split", "4x10k",
           "Resistor_SMD:R_Array_Convex_4x0603",
           {"MPN": "4D03WGJ0103T5E", "LCSC": "C29718"}),
    "100n": ("Device:C", "Device.kicad_sym", "C", "100nF",
             "Capacitor_SMD:C_0603_1608Metric",
             {"MPN": "CC0603KRX7R9BB104", "LCSC": "C14663"}),
    "1u": ("Device:C", "Device.kicad_sym", "C", "1uF",
           "Capacitor_SMD:C_0603_1608Metric",
           {"MPN": "CL10A105KB8NNNC", "LCSC": "C15849"}),
    "10u": ("Device:C", "Device.kicad_sym", "C", "10uF",
            "Capacitor_SMD:C_0805_2012Metric",
            {"MPN": "CL21A106KAYNNNE", "LCSC": "C15850"}),
}


def main():
    build_symbol_lib()

    b = SchBuilder(PROJ, paper="A3", title="Victor 9000 RAM Expansion r2",
                   rev="r2", date="2026-10-02",
                   comments={1: "RAM only; 1 MB SRAM (512Kx16 used as 1Mx8) behind 5V/3.3V translators",
                             2: "gen_sch.py (edablock SchBuilder) - do not hand-edit"})

    def side_text(ref, rdx, rdy, vdx, vdy, unit=1):
        """Move Reference/Value of `ref` (that unit) beside the symbol,
        left-justified, clear of the vertical power/pin labels."""
        for s in b.sch.schematicSymbols:
            props = {p.key: p for p in s.properties}
            if props["Reference"].value != ref or (s.unit or 1) != unit:
                continue
            x, y = s.position.X, s.position.Y
            for key, dx, dy in (("Reference", rdx, rdy), ("Value", vdx, vdy)):
                pr = props[key]
                pr.position.X, pr.position.Y = round(x + dx, 2), round(y + dy, 2)
                pr.effects.justify = Justify(horizontally="left")

    def add(kind, ref, x, y, **kw):
        lid, lf, ent, val, fp, fields = P[kind]
        return b.add_symbol(lid, lf, ent, ref, val, x, y, footprint=fp,
                            fields=dict(fields), **kw)

    # ---- J1: card edge (brownfield symbol, pcb-feature) --------------------
    j1 = b.add_symbol(f"{LIBNICK}:Expansion_Connector", LIBFILE, "Expansion_Connector",
                      "J1", "Victor_Expansion_Bus", 45, 110, footprint=FP_EDGE,
                      fields={"MPN": "card-edge fingers"}, in_bom=False)
    jmap = {1: "BA18", 2: "BA16", 3: "BA14", 4: "BA12", 5: "BA10", 6: "BA8",
            45: "BA9", 46: "BA11", 47: "BA13", 48: "BA15", 49: "BA17", 50: "BA19",
            25: "BD0", 26: "BD1", 24: "BD2", 27: "BD3", 23: "BD4", 28: "BD5",
            22: "BD6", 29: "BD7",
            9: "ALE", 11: "BRD_N", 14: "BWR_N", 10: "IOM",
            36: "+5V", 37: "+5V", 31: "GND", 35: "GND", 39: "GND", 44: "GND"}
    for pin, net in jmap.items():
        b.net(net, j1(pin))
    # every other J1 pin (SSO, DEN, DT/R, RESET, NMI, IRQ, HOLD, HLDA, CSEN,
    # PHASE2, XACK, EXTIO, +-12V, DLATCH, CLK5, CLK15B, READY, IR4/5) -> NC via
    # auto_noconnect() below.

    # PWR_FLAGs: +5V and GND enter only through passive card-edge pins
    for i, net in enumerate(("+5V", "GND")):
        f = b.add_symbol("power:PWR_FLAG", "power.kicad_sym", "PWR_FLAG",
                         f"#FLG0{i + 1}", "PWR_FLAG", 20 + 15 * i, 175,
                         in_bom=False, on_board=False)
        b.net(net, f(1))

    # ---- U2: 74LVC573A address latch A0-A7 (VCC +3V3) --------------------
    u2 = add("573", "U2", 125, 45)
    for n in range(8):
        # pin-swap 1: channel order reversed to match the BD finger order
        b.net(f"BD{7 - n}", u2(2 + n))       # D0..D7 = pins 2..9
        b.net(f"A{7 - n}", u2(19 - n))       # Q0..Q7 = pins 19..12
    b.net("ALE", u2(11))                     # LE
    b.net("GND", u2(1))                      # OE#
    b.net("+3V3", u2(20)); b.net("GND", u2(10))
    side_text("U2", 3, -20, 3, 20)

    # ---- U6: 74HCT151 decode at +5V ----------------------------------------
    u6 = add("151", "U6", 125, 115)
    b.net("BA17", u6(11)); b.net("BA18", u6(10)); b.net("BA19", u6(9))  # S0 S1 S2
    b.net("IOM", u6(7))                      # E#
    b.net("GND", u6(4))                      # I0
    b.net("SEL128", u6(3))                   # I1
    b.net("+5V", u6(2), u6(1), u6(15), u6(14), u6(13))   # I2..I6
    b.net("GND", u6(12))                     # I7
    b.net("CE5_N", u6(6))                    # ~Z (Y-bar); Z pin 5 -> NC
    b.net("+5V", u6(16)); b.net("GND", u6(8))
    side_text("U6", 3, -20, 3, 20)

    # ---- JP1 + RN1 ---------------------------------------------------------
    # right-angle 0.1" header; fit a shunt for a 128K motherboard
    jp1 = b.add_symbol("Jumper:Jumper_2_Open", "Jumper.kicad_sym",
                       "Jumper_2_Open", "JP1", "128K", 100, 180,
                       footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal",
                       fields={"MPN": "PZ254R-11-02P", "LCSC": "C492410"})
    b.net("SEL128", jp1(1)); b.net("+5V", jp1(2))
    # RN1: 4 isolated 10k (R1 = 1-8, R2 = 2-7, R3 = 3-6, R4 = 4-5), one unit each
    for u, (lo, hi, top, bot) in enumerate([(1, 8, "+5V", "BRD_N"),
                                            (2, 7, "+5V", "BWR_N"),
                                            (3, 6, "+5V", "IOM"),
                                            (4, 5, "GND", "SEL128")], 1):
        r = add("rn", "RN1", 125 + 12 * (u - 1), 180, unit=u)
        b.net(top, r(hi)); b.net(bot, r(lo))
        side_text("RN1", 2.54, -1.27, 2.54, 1.27, unit=u)

    # ---- U3/U4/U5: SN74LVC4245A (A = 5 V side, B = 3.3 V side) -------------
    def xcvr(ref, y, a_nets, b_nets, dir_net, oe_net):
        u = add("4245", ref, 205, y)
        b.net("+5V", u(1))                    # VCCA
        b.net("+3V3", u(23), u(24))           # VCCB (both)
        b.net("GND", u(11), u(12), u(13))
        b.net(dir_net, u(2)); b.net(oe_net, u(22))
        for i, (an, bn) in enumerate(zip(a_nets, b_nets)):
            if an:
                b.net(an, u(3 + i))           # A1..A8 = pins 3..10
            if bn:
                b.net(bn, u(21 - i))          # B1..B8 = pins 21..14
        return u

    # pin-swap 1: one-way channels ordered to follow the finger order
    # (BA18/19 leftmost ... BA8/9 rightmost) instead of crossing it
    xcvr("U3", 45, [f"BA{n}" for n in range(19, 11, -1)],
         [f"A{n}" for n in range(19, 11, -1)], "+5V", "GND")
    xcvr("U4", 100, ["BA11", "BA10", "BA9", "BA8", "BRD_N", "BWR_N", "CE5_N", "GND"],
         ["A11", "A10", "A9", "A8", "RD_N", "WR_N", "CE_N", None], "+5V", "GND")
    xcvr("U5", 155, [f"BD{n}" for n in range(8)], [f"D{n}" for n in range(8)],
         "BRD_N", "DOE_N")

    # ---- U1: IS62WV51216BLL, TSOP-II-44 (no CS2 on this package) -----------
    u1 = add("sram", "U1", 290, 100)
    # pin-swap 1: A8-A18 re-permuted over the left-end address pins so the
    # U3/U4 B-port bundle reaches U1 without crossings (A0-A7 unchanged)
    apin = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 44, 6: 43, 7: 42, 8: 28, 9: 27,
            10: 26, 11: 25, 12: 24, 13: 23, 14: 22, 15: 21, 16: 20, 17: 19, 18: 18}
    for n, pin in apin.items():
        b.net(f"A{n}", u1(pin))
    lo = {0: 7, 1: 8, 2: 9, 3: 10, 4: 13, 5: 14, 6: 15, 7: 16}            # I/O0-7
    hi = {8: 29, 9: 30, 10: 31, 11: 32, 12: 35, 13: 36, 14: 37, 15: 38}   # I/O8-15
    # pin-swap 1: I/O8=D0 ... I/O15=D7 (matches U5's B-port order) and
    # I/O7=D0 ... I/O0=D7 (each D net's two pins stay vertically aligned)
    for n in range(8):
        b.net(f"D{n}", u1(lo[7 - n]), u1(hi[8 + n]))
    b.net("CE_N", u1(6)); b.net("RD_N", u1(41)); b.net("WR_N", u1(17))  # CS1# OE# WE#
    b.net("A19", u1(39)); b.net("A19_N", u1(40))                        # LB# UB#
    b.net("+3V3", u1(11), u1(33)); b.net("GND", u1(12), u1(34))

    # ---- U7 / U8 glue, U9 LDO ----------------------------------------------
    u7 = add("1g04", "U7", 365, 40)
    b.net("A19", u7(2)); b.net("A19_N", u7(4))
    b.net("+3V3", u7(5)); b.net("GND", u7(3))        # pin 1 NC
    side_text("U7", 6, -9, 6, 9)

    u8 = add("0832", "U8", 365, 80)
    b.net("BRD_N", u8(1)); b.net("BWR_N", u8(3)); b.net("CE5_N", u8(6))  # A B C
    b.net("DOE_N", u8(4))                                                # Y
    b.net("+3V3", u8(5)); b.net("GND", u8(2))
    side_text("U8", 8, -9, 8, 9)

    u9 = add("ldo", "U9", 365, 120)
    b.net("+5V", u9(3)); b.net("+3V3", u9(2)); b.net("GND", u9(1))      # VIN VOUT VSS
    side_text("U9", 5, -6, 5, 6)

    # ---- capacitors ----------------------------------------------------------
    caps = [  # ref, kind, rail, placement_near
        ("C1", "100n", "+3V3", "U1 pin 11"), ("C2", "100n", "+3V3", "U1 pin 33"),
        ("C3", "100n", "+3V3", "U2 pin 20"),
        ("C4", "100n", "+5V", "U3 pin 1"), ("C5", "100n", "+3V3", "U3 pin 24"),
        ("C6", "100n", "+5V", "U4 pin 1"), ("C7", "100n", "+3V3", "U4 pin 24"),
        ("C8", "100n", "+5V", "U5 pin 1"), ("C9", "100n", "+3V3", "U5 pin 24"),
        ("C10", "100n", "+5V", "U6 pin 16"),
        ("C11", "100n", "+3V3", "U7 pin 5"), ("C12", "100n", "+3V3", "U8 pin 5"),
        ("C13", "1u", "+5V", "U9 pin 3"), ("C14", "1u", "+3V3", "U9 pin 2"),
        ("C15", "10u", "+5V", "J1 pin 36"), ("C16", "10u", "+3V3", "U1 pin 33"),
    ]
    for i, (ref, kind, rail, near) in enumerate(caps):
        c = add(kind, ref, 170 + 14 * (i % 8), 210 + 38 * (i // 8),
                placement_near=near)
        b.net(rail, c(1)); b.net("GND", c(2))
        side_text(ref, 2.54, -1.27, 2.54, 1.27)

    # ---- notes ----------------------------------------------------------------
    notes = [
        "MEMORY MAP (U6 74HCT151, S2:S0 = A19:A17, E# = IO/M)",
        "  00000h-1FFFFh  I0 = GND: off (motherboard RAM)",
        "  20000h-3FFFFh  I1 = SEL128: JP1 fitted = on (128K motherboard),",
        "                 JP1 open = off (256K motherboard)",
        "  40000h-DFFFFh  I2-I6 = +5V: on",
        "  E0000h-FFFFFh  I7 = GND: off",
        "U1 used as 1Mx8: LB#/UB# select the byte lane from A19",
        "  (LB# = A19, UB# = A19_N; I/O8-15 = D0..D7, I/O0-7 = D7..D0)",
        "U5 data transceiver: DIR = /RD (H = A->B write, L = B->A read),",
        "  OE# = DOE_N = (/RD AND /WR) OR CE5_N",
        "Bus side (BA*, BD*, ALE, BRD_N, BWR_N, IOM) is 5 V; SRAM side is 3.3 V",
    ]
    for i, line in enumerate(notes):   # one text item per line (no raw newlines)
        b.text(line, 20, 205 + 3.3 * i, size=1.8, justify="left")

    # KiCad draws a 270-degree global label upward (back over the part) unless
    # it is right-justified; same fix gensch.glabel() applies. Cosmetic only.
    for gl in b.sch.globalLabels:
        if int(gl.position.angle or 0) == 270:
            gl.effects.justify = Justify(horizontally="right")
    b.auto_noconnect()
    b.set_netclasses([{"name": "Power", "track_width": 0.25, "clearance": 0.2,
                       "via_diameter": 0.6, "via_drill": 0.3,
                       "patterns": ["+5V", "+3V3", "GND"]}])
    out = os.path.join(HERE, f"{PROJ}.kicad_sch")
    b.save(out)
    print("SCH OK:", out)


if __name__ == "__main__":
    main()
