#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ima_adpcm.h"
#include "game_over_voice_data.h"
#include "title_voice_data.h"

#define VOICE_GAIN_TABLE_COUNT 256u

static unsigned tests_run;

static void expect(int condition, const char* message)
{
    ++tests_run;
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(1);
    }
}

static void test_known_decode_vector(void)
{
    ImaAdpcmState state;
    int samples[2];

    ima_adpcm_init(&state, 0, 0u);
    expect(ima_adpcm_decode_nibble(&state, 7u) == 11 &&
        state.step_index == 8u,
        "known nibble 7 advances predictor and index");
    expect(ima_adpcm_decode_nibble(&state, 7u) == 41 &&
        state.step_index == 16u,
        "second known nibble 7 uses the advanced step");
    expect(ima_adpcm_decode_nibble(&state, 15u) == -22 &&
        state.step_index == 24u,
        "known negative nibble applies sign and index delta");
    expect(ima_adpcm_decode_nibble(&state, 0u) == -13 &&
        state.step_index == 23u,
        "known zero-magnitude code applies the baseline delta");

    ima_adpcm_init(&state, 0, 0u);
    ima_adpcm_decode_byte(&state, 0xf7u, samples);
    expect(samples[0] == 11 && samples[1] == -19,
        "packed bytes decode low nibble before high nibble");
}

static void test_state_clamps(void)
{
    ImaAdpcmState state;

    ima_adpcm_init(&state, 32767, 255u);
    expect(state.predictor == 32767 && state.step_index == 88u,
        "initial state clamps the step index");
    expect(ima_adpcm_decode_nibble(&state, 7u) == 32767 &&
        state.step_index == 88u,
        "positive decode clamps predictor and step index");

    ima_adpcm_init(&state, -32768, 88u);
    expect(ima_adpcm_decode_nibble(&state, 15u) == -32768 &&
        state.step_index == 88u,
        "negative decode clamps predictor and step index");
}

static void test_mikey_dac_conversion(void)
{
    unsigned value;

    expect(ima_adpcm_pcm16_to_mikey_dac(-32768) == 0x80u,
        "negative full scale maps to signed DAC byte 0x80");
    expect(ima_adpcm_pcm16_to_mikey_dac(0) == 0x00u,
        "zero maps to signed DAC byte zero");
    expect(ima_adpcm_pcm16_to_mikey_dac(32767) == 0x7fu,
        "positive full scale maps to signed DAC byte 0x7f");

    expect(ima_adpcm_voice_gain(0x00u) == 0x00u,
        "voice gain preserves signed DAC zero and silence");
    expect(ima_adpcm_voice_gain(0x04u) == 0x05u &&
        ima_adpcm_voice_gain(0xfcu) == 0xfbu,
        "voice gain applies symmetric 5/4 magnitude mapping");
    expect(ima_adpcm_voice_gain(0x7fu) == 0x7fu &&
        ima_adpcm_voice_gain(0x80u) == 0x80u,
        "voice gain saturates at unsigned-domain 255 and 0 endpoints");

    for (value = 1u; value <= 102u; ++value) {
        int positive;
        int negative;

        positive = (int)ima_adpcm_voice_gain((unsigned char)value);
        negative = (int)ima_adpcm_voice_gain((unsigned char)(256u - value));
        if (negative >= 128) {
            negative -= 256;
        }
        expect(positive == -negative,
            "voice gain keeps positive/negative signs symmetric before clamp");
    }
}

static unsigned char reference_voice_gain(unsigned char signed_dac)
{
    int sample;
    int magnitude;
    int scaled;

    sample = signed_dac < 0x80u ? (int)signed_dac : (int)signed_dac - 256;
    magnitude = sample < 0 ? -sample : sample;
    scaled = (magnitude * 5) / 4;
    if (sample < 0) {
        if (scaled > 128) {
            scaled = 128;
        }
        scaled = -scaled;
    } else if (scaled > 127) {
        scaled = 127;
    }
    return (unsigned char)scaled;
}

static int voice_gain_clamps(unsigned char signed_dac)
{
    int sample;
    int scaled;

    sample = signed_dac < 0x80u ? (int)signed_dac : (int)signed_dac - 256;
    scaled = ((sample < 0 ? -sample : sample) * 5) / 4;
    return scaled > (sample < 0 ? 128 : 127);
}

static void test_voice_gain_table(void)
{
    FILE* input;
    char line[512];
    unsigned count;
    unsigned mismatch_count;

    input = fopen("src/title_voice_gain.inc", "r");
    expect(input != NULL, "generated assembly voice gain table opens");
    count = 0u;
    mismatch_count = 0u;
    while (fgets(line, sizeof(line), input) != NULL) {
        char* cursor;

        cursor = line;
        while ((cursor = strchr(cursor, '$')) != NULL) {
            char* end;
            long parsed;

            parsed = strtol(cursor + 1, &end, 16);
            if (end == cursor + 1 || parsed < 0L || parsed > 255L ||
                count >= VOICE_GAIN_TABLE_COUNT ||
                (unsigned char)parsed !=
                    reference_voice_gain((unsigned char)count)) {
                ++mismatch_count;
            }
            ++count;
            cursor = end;
        }
    }
    fclose(input);
    expect(count == VOICE_GAIN_TABLE_COUNT && mismatch_count == 0u,
        "C89 voice gain reference matches all 256 assembly table entries");

    for (count = 0u; count < VOICE_GAIN_TABLE_COUNT; ++count) {
        expect(ima_adpcm_voice_gain((unsigned char)count) ==
            reference_voice_gain((unsigned char)count),
            "C89 runtime voice gain matches independent full-domain reference");
    }
}

static void test_deterministic_non_speech_round_trip(void)
{
    ImaAdpcmState encoder;
    ImaAdpcmState decoder;
    long total_error;
    int maximum_error;
    int direction;
    int sample;
    unsigned i;

    ima_adpcm_init(&encoder, 0, 0u);
    ima_adpcm_init(&decoder, 0, 0u);
    total_error = 0L;
    maximum_error = 0;
    direction = 1;
    sample = -12000;

    for (i = 0u; i < 512u; ++i) {
        unsigned char code;
        int decoded;
        int error;

        code = ima_adpcm_encode_sample(&encoder, sample);
        decoded = ima_adpcm_decode_nibble(&decoder, code);
        error = sample - decoded;
        if (error < 0) {
            error = -error;
        }
        total_error += (long)error;
        if (error > maximum_error) {
            maximum_error = error;
        }
        if (direction > 0) {
            sample += 750;
            if (sample >= 12000) {
                sample = 12000;
                direction = -1;
            }
        } else {
            sample -= 750;
            if (sample <= -12000) {
                sample = -12000;
                direction = 1;
            }
        }
    }

    expect(encoder.predictor == decoder.predictor &&
        encoder.step_index == decoder.step_index,
        "encoder and independent decoder finish in identical state");
    expect(total_error / 512L < 600L,
        "deterministic triangle average error stays below 600");
    expect(maximum_error < 12000,
        "deterministic triangle maximum error stays bounded");
}

static void test_voice_artifact(const char* path, unsigned sample_count,
    unsigned expected_byte_count, int initial_predictor,
    unsigned char initial_step_index, int expected_dac_minimum,
    int expected_dac_maximum, int expected_gain_minimum,
    int expected_gain_maximum, unsigned expected_center_count,
    unsigned expected_silent_tail, const char* open_message)
{
    FILE* input;
    ImaAdpcmState decoder;
    unsigned sample_index;
    unsigned byte_count;
    unsigned active_samples;
    unsigned char packed;
    int decoded;
    int minimum;
    int maximum;
    int dac_minimum;
    int dac_maximum;
    int gain_minimum;
    int gain_maximum;
    unsigned center_before;
    unsigned center_after;
    unsigned clamp_count;
    unsigned silent_tail;
    unsigned gain_mismatch_count;

    input = fopen(path, "rb");
    expect(input != NULL, open_message);
    ima_adpcm_init(&decoder, initial_predictor, initial_step_index);
    byte_count = 0u;
    active_samples = 0u;
    packed = 0u;
    minimum = 32767;
    maximum = -32768;
    dac_minimum = 127;
    dac_maximum = -128;
    gain_minimum = 127;
    gain_maximum = -128;
    center_before = 0u;
    center_after = 0u;
    clamp_count = 0u;
    silent_tail = 0u;
    gain_mismatch_count = 0u;
    for (sample_index = 0u; sample_index < sample_count;
        ++sample_index) {
        if ((sample_index & 1u) == 0u) {
            int next;

            next = fgetc(input);
            expect(next != EOF, "voice artifact contains every declared sample");
            packed = (unsigned char)next;
            ++byte_count;
            decoded = ima_adpcm_decode_nibble(&decoder,
                (unsigned char)(packed & 0x0fu));
        } else {
            decoded = ima_adpcm_decode_nibble(&decoder,
                (unsigned char)(packed >> 4));
        }
        if (decoded < minimum) {
            minimum = decoded;
        }
        if (decoded > maximum) {
            maximum = decoded;
        }
        if (decoded < -256 || decoded > 256) {
            ++active_samples;
        }
        {
            unsigned char dac;
            unsigned char gained;
            int signed_dac;
            int signed_gain;

            dac = ima_adpcm_pcm16_to_mikey_dac(decoded);
            gained = ima_adpcm_voice_gain(dac);
            signed_dac = dac < 0x80u ? (int)dac : (int)dac - 256;
            signed_gain = gained < 0x80u
                ? (int)gained : (int)gained - 256;
            if (signed_dac < dac_minimum) {
                dac_minimum = signed_dac;
            }
            if (signed_dac > dac_maximum) {
                dac_maximum = signed_dac;
            }
            if (signed_gain < gain_minimum) {
                gain_minimum = signed_gain;
            }
            if (signed_gain > gain_maximum) {
                gain_maximum = signed_gain;
            }
            if (signed_dac == 0) {
                ++center_before;
                ++silent_tail;
            } else {
                silent_tail = 0u;
            }
            if (signed_gain == 0) {
                ++center_after;
            }
            if (voice_gain_clamps(dac)) {
                ++clamp_count;
            }
            if (gained != reference_voice_gain(dac)) {
                ++gain_mismatch_count;
            }
        }
    }
    expect(byte_count == expected_byte_count && fgetc(input) == EOF,
        "voice byte count exactly matches packed sample metadata");
    expect(minimum < -4000 && maximum > 6000,
        "voice decoded waveform spans audible signed PCM range");
    expect(active_samples > sample_count / 2u,
        "voice contains sustained non-silent decoded content");
    expect(decoder.predictor == 0 && decoder.step_index == 0u,
        "voice trailing natural silence reaches the recorded final state");
    expect(dac_minimum == expected_dac_minimum &&
        dac_maximum == expected_dac_maximum,
        "voice pre-gain signed DAC min/max match checked baseline");
    expect(gain_minimum == expected_gain_minimum &&
        gain_maximum == expected_gain_maximum,
        "voice post-gain signed DAC min/max match checked baseline");
    expect(center_before == expected_center_count &&
        center_after == expected_center_count,
        "voice gain preserves every decoded center sample");
    expect(clamp_count == 0u,
        "checked voice gain has no saturated samples");
    expect(silent_tail == expected_silent_tail,
        "voice gain preserves the exact silent tail");
    expect(gain_mismatch_count == 0u,
        "every decoded voice sample matches the 5/4 saturating reference");
    fclose(input);
}

static void test_checked_voice_artifacts(void)
{
    test_voice_artifact("assets/voice/title-start.adpcm",
        TITLE_VOICE_SAMPLE_COUNT, TITLE_VOICE_ADPCM_BYTE_COUNT,
        TITLE_VOICE_INITIAL_PREDICTOR, TITLE_VOICE_INITIAL_STEP_INDEX,
        -28, 33, -35, 41, 3583u, 815u,
        "checked-in title voice ADPCM artifact opens");
    test_voice_artifact("assets/voice/game-over.adpcm",
        GAME_OVER_VOICE_SAMPLE_COUNT, GAME_OVER_VOICE_ADPCM_BYTE_COUNT,
        GAME_OVER_VOICE_INITIAL_PREDICTOR,
        GAME_OVER_VOICE_INITIAL_STEP_INDEX,
        -20, 24, -25, 30, 2778u, 826u,
        "checked-in GAME OVER voice ADPCM artifact opens");
}

int main(void)
{
    test_known_decode_vector();
    test_state_clamps();
    test_mikey_dac_conversion();
    test_voice_gain_table();
    test_deterministic_non_speech_round_trip();
    test_checked_voice_artifacts();
    printf("ima adpcm tests passed: %u\n", tests_run);
    return 0;
}
