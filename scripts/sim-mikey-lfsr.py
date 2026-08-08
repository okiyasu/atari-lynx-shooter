#!/usr/bin/env python3
"""Simulate Gearlynx's MIKEY AdvanceLFSR (mikey_inline.h) for the game's
wave tables, in both normal and integrate mode (APS-027 investigation).

The LFSR is 12 bits. Each timer underflow:
  data_in = XNOR(parity(lfsr & taps_mask))
  lfsr = ((lfsr << 1) & 0x0FFE) | data_in
Normal mode:    output = +vol if data_in else -vol
Integrate mode: output = clamp(output + (+vol if data_in else -vol), -128, 127)

taps_mask: feedback bits0-5 -> taps 0-5, feedback bits6-7 -> taps 10-11,
control bit7 -> tap 7 (unused by this game, always 0).
"""


def taps_mask(feedback, control_bit7=0):
    mask = feedback & 0x3F
    mask |= (feedback & 0xC0) << 4
    if control_bit7:
        mask |= 0x80
    return mask


def parity(x):
    return bin(x).count("1") & 1


def simulate(feedback, shift_low, vol=0x20, steps=4096, other_hi=0):
    lfsr = (shift_low & 0xFF) | ((other_hi & 0xF0) << 4)
    mask = taps_mask(feedback)
    bits = []
    seen = {}
    period = None
    period_start = None
    for i in range(steps):
        if lfsr in seen and period is None:
            period = i - seen[lfsr]
            period_start = seen[lfsr]
        seen.setdefault(lfsr, i)
        data_in = parity(lfsr & mask) ^ 1
        lfsr = ((lfsr << 1) & 0x0FFE) | data_in
        bits.append(data_in)
    acc = 0
    accs = []
    clamped = 0
    for b in bits:
        acc += vol if b else -vol
        acc = max(-128, min(127, acc))
        if acc in (-128, 127):
            clamped += 1
        accs.append(acc)
    if period:
        pb = bits[period_start:period_start + period]
        ones = sum(pb)
        zeros = period - ones
        runs = []
        cur, n = pb[0], 1
        for b in pb[1:]:
            if b == cur:
                n += 1
            else:
                runs.append((cur, n))
                cur, n = b, 1
        runs.append((cur, n))
    else:
        ones = zeros = 0
        runs = []
    return dict(period=period, warmup=period_start, ones=ones, zeros=zeros,
                imbalance=ones - zeros, runs=runs, nruns=len(runs),
                clamp_frac=clamped / len(bits), acc_tail=accs[-64:])


def report(name, fb, sh, vol=0x20):
    r = simulate(fb, sh, vol=vol)
    print(name)
    print("  period=%s ticks (warmup %s) ones=%d zeros=%d imbalance/period=%+d"
          % (r["period"], r["warmup"], r["ones"], r["zeros"], r["imbalance"]))
    print("  runs/period=%d  runs=%s" % (r["nruns"], r["runs"][:16]))
    print("  integrate(vol=0x%02x): clamp fraction=%.1f%%" % (vol, 100 * r["clamp_frac"]))
    print("  integrate acc tail=%s" % r["acc_tail"][:24])
    print()


if __name__ == "__main__":
    print("=== current sound_wave_registers (APS-013 values, APS-026 turned on integrate) ===")
    report("TONE     fb=0x3f sh=0xac", 0x3F, 0xAC)
    report("METALLIC fb=0x36 sh=0x5a", 0x36, 0x5A)
    report("NOISE    fb=0x1f sh=0x7f", 0x1F, 0x7F)
    report("PULSE    fb=0x24 sh=0xb4", 0x24, 0xB4)
