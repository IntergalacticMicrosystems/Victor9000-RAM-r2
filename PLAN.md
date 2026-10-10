# Victor9000-RAM-r2 — modernization plan

Goal: have JLCPCB assemble the card from surface-mount LCSC parts that are
cheap, easy to get and deeply stocked. Profile: **type2 (JLC-assembled)**.
Quantity: **10 boards**. Outline: **shrink** from 95 x 87 mm.

Researched 2026-10-02 by four Opus 5.5 agents (5 V port, 3.3 V SRAM,
RP2350+PSRAM, RTC), reviewed by GPT-6-Astra, stock checked by hand against
JLCPCB's live parts API the same day.

## 1. What the current card is

Through-hole, 2-layer, 95 x 87 mm, 50-pin card edge.

- 2x AS6C4008-55PCN (512Kx8, 5 V). U5 = 20000h or 40000h–7FFFFh (JP1: 128K
  vs 256K motherboard), U7 = 80000h–DFFFFh. Brings the machine to 896K.
- 74LS373 latches BD0-7 into A0-7 on ALE. A8–A19 arrive already latched.
- 74LS245 data transceiver (DIR = /RD), 74LS139 + 74LS11 + 74LS00 decode.
- DS1315 phantom clock in U7's chip-enable path, crystal, CR2032. The SRAMs
  are not battery backed.

The decode and memory map are correct; no functional bugs were found in the
RAM path. One inherited wart: at the end of every read the '245 turns round
~20 ns before the SRAM lets go of its data pins.

## 2. Why a straight SMD port does not work

| Finding | Evidence (JLC live stock, 2026-10-02) |
|---|---|
| 5 V SMD SRAM is nearly gone | R1LP0408DSP-5SI 21 pcs (40 needed), CY62148ELL-55SXIT 28, AS6C4008-55ZIN 2, AS6C8008-55ZIN 1 |
| Only one large parallel SRAM is deeply stocked, and it is 3.3 V | IS62WV51216BLL-55TLI: 3939 pcs + 2000 on tape, ~$10.94 |
| DS1315 is not buildable at JLC | 0 at JLC/LCSC; $28–31 at Digi-Key/Mouser |
| No DS1315 software exists for the Victor | The only phantom-clock utility found (SMWCLOCK) drives a DS1216E in ROM mode and would not work with this card's wiring. Victor DOS has no RTC support. Any clock needs its own small utility either way. |
| No 74HCT/AHCT/LVC logic is JLC Basic | Every logic IC is Extended (setup fee per part type, about $3 — not verified) except JLC "Preferred" parts |

## 3. Options compared (parts only, ~20 boards)

| | A: 5 V SMD port | **B: 3.3 V SRAM + translators** | C: RP2350B + PSRAM |
|---|---|---|---|
| Memory | 2x R1LP0408DSP SOP-32 | 1x IS62WV51216BLL TSOP-II-44 | ~384K internal SRAM + QSPI PSRAM |
| Memory stock at JLC | 21 — short for 20 boards | ~5900 | 933–2264 (3 V PSRAM) |
| Parts cost per board | ~$11.3 | ~$13 | ~$7.5–8.5 |
| ICs | 6 | 7 + 2 single gates + LDO | ~8, QFN-80, many passives |
| Layers | 2 | 2 | 4 recommended |
| Firmware | none | none | est. 6–12 weeks incl. validation |
| Wait states | 0 | 0 | 1 on the PSRAM half |
| Failure mode | hard fault | hard fault | silent RAM corruption possible |

**Choose B.** It is the only option that meets "lots in stock" with no
firmware. A fails on stock. C is feasible (XACK wait states are proven on this
bus by pico_v9k) but only pays off if the card is meant to become a
multi-function card.

## 4. Design B

### RAM section

| Ref | Part | LCSC | JLC stock | Job |
|---|---|---|---|---|
| U1 | IS62WV51216BLL-55TLI, TSOP-II-44 | C11315 (tape: C2064581) | 3939 (+2000) | 512Kx16 used as 1Mx8 |
| U2 | 74LVC573APW,118 | C6096 | 53,660 | A0-7 latch at 3.3 V; D and LE straight from the 5 V bus |
| U3, U4 | SN74LVC4245APWR | C7859 (Preferred) | 122,378 | A8–A19, /RD, /WR, CE# from 5 V down to 3.3 V |
| U5 | SN74LVC4245APWR | C7859 | — | Data transceiver; drives a full 5 V swing onto the bus |
| U6 | 74HCT151D,653 at 5 V | C547364 | 1,725 | The whole address decode |
| U7 | SN74LVC1G04DBVR | C19829658 | 3,958 | UB# = /A19 |
| U8 | SN74LVC1G0832DBVR at 3.3 V | C206101 | 1,343 | Transceiver enable = CE# + (/RD · /WR) |
| U9 | XC6206P332MR-G (Basic) | C5446 | 469,796 | 3.3 V LDO, 1 µF in and out |
| — | 100 nF, 1 µF, 10 µF, 4x10k array (all Basic) | C14663, C15849, C15850, C29718 | millions | Decoupling; pull-ups on /RD, /WR, IO/M; pull-down on the jumper input |
| JP1 | PZ254R-11-02P right-angle 1x2 0.1 in header (through-hole) | C492410 | 178,732 | Replaces the old JP1: shunt fitted = 128K motherboard (enables the 20000h block), open = 256K |

How it fits together:

- **x16 as x8.** I/O0-7 tied to I/O8-15; LB# = A19, UB# = /A19; SRAM A0-18 =
  CPU A0-18; CS1# = decode; OE# = /RD; WE# = /WR. A19 only changes at ALE,
  outside the strobes, so the two lanes never overlap.
- **Decode.** 74HCT151 fed straight from the bus: S2:S0 = A19:A17,
  E# = IO/M, I0 = 0, I1 = JP1, I2–I6 = 1, I7 = 0. The inverting output
  (pin 6 on the Nexperia part) is CE#. Run at 5 V because the HC151 has no
  guaranteed timing at 3.3 V.
- **Transceiver control.** DIR = /RD as in the original, but enabled only
  during a strobe. This cuts the read-end overlap from ~27 ns to about one
  gate delay. Do **not** use DT/R and /DEN instead: pico_v9k's DMA master
  holds DEN high, so a /DEN-gated card would not see DMA transfers.
- **Power sequencing.** The LVC4245A is glitch-free in any supply order and
  goes high-Z if either rail is down; the LVC573A has 5 V-tolerant inputs and
  Ioff. The SRAM only ever sees 3.3 V-powered outputs.
- **Timing.** Address valid at 125 ns; data must be on the bus by ~547 ns.
  Decode (~50 ns) + translator (7) + SRAM (55) + transceiver (6) puts data
  ready near 245 ns. No wait states; XACK stays unconnected.

Same-footprint alternates for U1 (pinouts to be verified in Stage 2):
IS61WV51216EDBLL-10TLI C57407 (514), IS62WV51216EBLL-45TLI C1348903 (217),
IS62WV51216HBLL-45TLI C7211338 (147).

### Clock section — NOT on r2 (dropped 2026-10-02; kept here for a later rev)

- **DS3231MZ+TRL** (C107410, 8,640 in stock, ~$2.87): no crystal, ±5 ppm,
  runs at 5 V, VBAT from a CR2032. Cheaper alternative: DS1302Z (C8959,
  20,553, Preferred, ~$1.03) plus a 6 pF crystal, with crystal-grade accuracy.
- CR2032 holder: SMD C22363833 (8,544) or through-hole C70377 (13,625).
- A new small DOS utility reads the clock at boot and sets DOS date/time
  (and writes the clock back on request).

**How it attaches to the bus.** One memory-mapped byte at **EFFF0h–EFFFFh**,
the window the Valid Technologies clock card used, reached through the bus's
own external-I/O mechanism (CSEN + /EXTIO). pico_v9k already uses the same
mechanism at EF300h on real hardware. The 5 V logic sits directly on the bus;
it is independent of the 3.3 V RAM section.

| Part | LCSC | JLC stock | Job |
|---|---|---|---|
| 2x 74HCT30PW (8-input NAND) | C547587 | 620 | /RTCSEL = CSEN · A15..A4 all high. CSEN already means "E-segment access", so A16–A19 need no decode |
| 74HCT32D | C5985 | 3,342 | Combines the two NANDs; /RTCWR = /RTCSEL + /WR; /RTCRD = /RTCSEL + /RD |
| SN74HCT74DR | C352961 | 8,996 | Two output bits latched from BD0/BD1 on /RTCWR rising: SCL and SDA-out. RC preset so both power up released |
| 74HCT125D | C5962 | 86,527 | Gate 1 pulls /EXTIO low while selected; gate 2 puts SDA on BD0 during /RTCRD; gate 3 pulls SDA low (open-drain) |

- Write `ES:[0]` with bit 0 = SCL, bit 1 = SDA; read bit 0 = SDA. The
  utility bit-bangs I2C. E-segment cycles are stretched to a full PHASE2
  period (1 µs), so logic speed is irrelevant.
- The DS3231's SCL pin is input-only, so the flip-flop drives it directly.
- With a DS1302 instead, the port needs three output bits (CE, SCLK, IO), so
  the '74 becomes a wider latch and a crystal is added.
- Not used: 8088 I/O space (IN/OUT). On an I/O cycle A16–A19 are zero and the
  /RD and /WR strobes are shared, so the motherboard may answer as if it were
  a read of low RAM. Unverified, so avoided.
- To verify at Stage 3: EFFF0h is free on the target machines (it would
  clash only with a Valid Technologies card), and bus RESET polarity if a
  hard reset of the port is wanted instead of the RC preset.

## 5. Build pipeline (board_design SKILL)

0. **Profile + quantity.** `project.toml`: type2, boards = 10, single
   variant. Two layers: finest pitch is 0.65 mm TSSOP and
   0.8 mm TSOP-II, so normal F.Cu escapes exist. Move to four only if routing
   plateaus.
1. **Blocks.** None needed (the AMS1117 block is oversized for ~40 mA).
2. **Parts.** Record the table above via partbroker. Verify pinouts against
   datasheets: IS62WV51216BLL (TSOP-II has no CS2 pin), LVC4245A (A = 5 V
   port, pin 23 = VCCB), HCT151, U1 alternates.
3. **Schematic.** SchBuilder; reuse the existing card-edge symbol and
   footprint (brownfield rule). check-sch, lint-sch, PDF review, emit-pcb,
   pad-net audit. Settle the clock port first.
4. **Placement.** New, smaller outline. The card edge fixes the minimum
   width (finger span is ~65 mm); height is set by the parts, roughly
   40–45 mm with the clock fitted. Confirm any card-guide or retention
   constraint in the Victor before drawing it. Human places and locks
   anchors; place.py does the rest.
5. **Routing.** autoroute.py, DRC clean, human reviews the render.
6. **BOM.** check-bom / order-bom per variant. Re-check live JLC stock the day
   of ordering — it moved during this study.
7. **Fab options to confirm.** 1.6 mm board, gold fingers with bevel, and
   whether the battery holder is assembled or hand-fitted.
8. **Bring-up.** Memory test on 128K and 256K motherboards; independent
   patterns at addresses that share an SRAM word across the two lanes
   (e.g. 40000h vs C0000h); hard-disk DMA into expansion RAM; clock utility.

## 6. Decisions needed

All settled 2026-10-02: 10 boards, RAM only (no clock on r2), shrunk outline.

## 7. Status (2026-10-02)

- Stages 0-4 passed. Schematic `Victor9000-RAM-r2.kicad_sch` (generated by
  `gen_sch.py`), board `Victor9000-RAM-r2.kicad_pcb`: 73.0 x 47.2 mm, 2 layers.
- Stage 5: routed 85/85 nets; `kicad-cli pcb drc` shows 0 violations and
  0 unconnected. Awaiting human review of the render before the stage is
  marked passed.
- As built, the decoder and translators differ from section 4 only in pin
  assignment: translator channels and SRAM address/data pins were permuted
  for routing (`build/verify_function.py` proves equivalence).
- Power tracks are 0.25 mm (not 0.5): the load is under 100 mA and both
  layers carry a ground pour.
- Not yet done: fab outputs (gerbers, drill, placement file), bring-up.
