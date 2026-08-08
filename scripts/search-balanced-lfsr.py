#!/usr/bin/env python3
"""Search MIKEY LFSR feedback/shift_low pairs whose steady-state cycle is
DC-balanced (equal ones and zeros per period), for use with the integrate
bit (APS-027). Restricted to feedback bits 0-5 (taps 0-5) so the cycle is
fully determined by the written shift_low byte -- taps 10/11 (feedback
bits 6-7) and tap 7 (control bit 7) would read LFSR bits this game never
initialises.

For each candidate we report period, run structure, and the accumulator
excursion per unit volume (max partial sum), which bounds how close the
integrated waveform gets to the +/-128 clamp: peak = excursion * volume.
"""


def parity(x):
    return bin(x).count("1") & 1


def cycle_from(feedback, shift_low, max_steps=8192):
    lfsr = shift_low & 0xFF
    mask = feedback & 0x3F
    seen = {}
    bits = []
    for i in range(max_steps):
        if lfsr in seen:
            start = seen[lfsr]
            return bits[:start], bits[start:]
        seen[lfsr] = i
        data_in = parity(lfsr & mask) ^ 1
        lfsr = ((lfsr << 1) & 0x0FFE) | data_in
        bits.append(data_in)
    return bits, []


def runs_of(bits):
    runs = []
    cur, n = bits[0], 1
    for b in bits[1:]:
        if b == cur:
            n += 1
        else:
            runs.append((cur, n))
            cur, n = b, 1
    runs.append((cur, n))
    return runs


def analyse(feedback, shift_low):
    warmup, cyc = cycle_from(feedback, shift_low)
    if not cyc:
        return None
    ones = sum(cyc)
    if ones * 2 != len(cyc):
        return None  # not DC-balanced
    acc = 0
    lo = hi = 0
    for b in cyc:
        acc += 1 if b else -1
        lo = min(lo, acc)
        hi = max(hi, acc)
    return dict(period=len(cyc), warmup=len(warmup), runs=runs_of(cyc),
                excursion=hi - lo)


if __name__ == "__main__":
    import sys
    want_periods = set(int(a) for a in sys.argv[1:]) or {4, 6, 8, 10, 12}
    found = {}
    for fb in range(1, 0x40):
        for sh in range(0, 0x100):
            r = analyse(fb, sh)
            if r is None or r["period"] not in want_periods:
                continue
            key = (r["period"], tuple(r["runs"]))
            if key in found:
                continue
            found[key] = (fb, sh, r)
    for (period, runs), (fb, sh, r) in sorted(found.items()):
        print("period=%2d fb=0x%02x sh=0x%02x warmup=%d excursion=%d runs=%s"
              % (period, fb, sh, r["warmup"], r["excursion"], list(runs)))
