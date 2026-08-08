#!/usr/bin/env python3
"""APS-028: generate the per-wave MIKEY pitch tables for src/main.c.

Why per-wave tables exist at all
--------------------------------
A MIKEY audio channel does not output one square-wave edge per timer
underflow: every underflow shifts the channel's LFSR once, and the
*audible* waveform only repeats after one full LFSR cycle. The
perceived fundamental is therefore

    f_perceived = f_underflow / lfsr_cycle_len

Furnace (src/engine/platform/lynx.cpp) encodes exactly this rule: its
DUTY_DIVIDERS[] table stores the cycle length of every tap combination
and its "tuned" mode divides the target frequency by that divider
before programming BACKUP/CONTROL. This game's original single pitch
table (APS-013, lifted from sample data assuming one edge per two
underflows, i.e. divider 2) was never divided by the real cycle length
(TONE 7, later 6; PULSE 9, later 8; METALLIC 63; NOISE 6), so every
note sounded 3x-31x lower than intended -- the persistent low "buzz".

Note scale
----------
mml2c maps note ids 1..16 to a C-major diatonic scale:
    note = (octave - 1) * 7 + degree,  degree 1..7 = c d e f g a b
so id 1 = C4 ... id 16 = D6 (equal temperament, A4 = 440 Hz). The old
table was also not diatonic (uniform ~1.075 ratio steps), so melodies
played with compressed, out-of-tune intervals; this table fixes that
as well.

Register encoding
-----------------
Timer period = (reload + 1) * 2^prescaler microseconds (prescaler
0..6 = 1..64 us). For each note and wave we pick the prescaler that
keeps reload as large as possible (<= 255) for best pitch precision,
then round reload to the nearest value.
"""

LFSR_CYCLE = {
    "TONE": 6,      # fb=0x04 sh=0x07 twisted ring 111000 (APS-027)
    "METALLIC": 63, # fb=0x36 sh=0x5a maximal-ish sequence (APS-013)
    "NOISE": 6,     # fb=0x1f sh=0x7f 111110 pulse pattern (APS-013)
    "PULSE": 8,     # fb=0x08 sh=0x0f twisted ring 11110000 (APS-027)
}
WAVE_ORDER = ["TONE", "METALLIC", "NOISE", "PULSE"]
DEGREE_SEMIS = [0, 2, 4, 5, 7, 9, 11]
C4 = 261.6255653


def note_freq(note_id):
    octave, degree = divmod(note_id - 1, 7)
    return C4 * 2.0 ** ((12 * octave + DEGREE_SEMIS[degree]) / 12.0)


def encode(period_us):
    best = None
    for presc in range(7):
        reload = int(round(period_us / (1 << presc))) - 1
        if not 0 <= reload <= 255:
            continue
        actual = (reload + 1) * (1 << presc)
        err = abs(actual - period_us) / period_us
        if best is None or err < best[0]:
            best = (err, reload, presc)
    if best is None:
        raise ValueError("period %.2f us not encodable" % period_us)
    return best


def main():
    print("static const SoundPitchRegister sound_pitch_registers[")
    print("    SOUND_WAVE_COUNT][SOUND_NOTE_COUNT] = {")
    for wave in WAVE_ORDER:
        cycle = LFSR_CYCLE[wave]
        entries = []
        worst = 0.0
        for note in range(1, 17):
            f = note_freq(note)
            period_us = 1e6 / (f * cycle)
            err, reload, presc = encode(period_us)
            worst = max(worst, err)
            entries.append("{ 0x%02xu, %du }" % (reload, presc))
        print("    /* %s: LFSR cycle %d, worst pitch error %.2f%% */" %
              (wave, cycle, worst * 100))
        print("    {")
        for row in range(0, 16, 4):
            line = "    " + ", ".join(entries[row:row + 4])
            print(line + ("," if row != 12 else ""))
        print("    }" + ("," if wave != WAVE_ORDER[-1] else ""))
    print("};")


if __name__ == "__main__":
    main()
