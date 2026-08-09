#include "ima_adpcm.h"

#define IMA_ADPCM_MIN_PREDICTOR (-32767 - 1)
#define IMA_ADPCM_MAX_PREDICTOR 32767
#define IMA_ADPCM_MAX_STEP_INDEX 88u

static const int ima_adpcm_index_delta[8] = {
    -1, -1, -1, -1, 2, 4, 6, 8
};

static const int ima_adpcm_step[89] = {
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371,
    408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166,
    1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024,
    3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845,
    8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500,
    20350, 22385, 24623, 27086, 29794, 32767
};

static int clamp_predictor(long predictor)
{
    if (predictor < (long)IMA_ADPCM_MIN_PREDICTOR) {
        return IMA_ADPCM_MIN_PREDICTOR;
    }
    if (predictor > (long)IMA_ADPCM_MAX_PREDICTOR) {
        return IMA_ADPCM_MAX_PREDICTOR;
    }
    return (int)predictor;
}

static unsigned char clamp_step_index(int step_index)
{
    if (step_index < 0) {
        return 0u;
    }
    if (step_index > (int)IMA_ADPCM_MAX_STEP_INDEX) {
        return IMA_ADPCM_MAX_STEP_INDEX;
    }
    return (unsigned char)step_index;
}

void ima_adpcm_init(ImaAdpcmState* state, int predictor,
    unsigned char step_index)
{
    state->predictor = clamp_predictor((long)predictor);
    state->step_index = clamp_step_index((int)step_index);
}

int ima_adpcm_decode_nibble(ImaAdpcmState* state, unsigned char nibble)
{
    unsigned char code;
    int step;
    long difference;
    long predictor;
    int next_index;

    code = (unsigned char)(nibble & 0x0fu);
    step = ima_adpcm_step[state->step_index];
    difference = (long)(step >> 3);
    if ((code & 1u) != 0u) {
        difference += (long)(step >> 2);
    }
    if ((code & 2u) != 0u) {
        difference += (long)(step >> 1);
    }
    if ((code & 4u) != 0u) {
        difference += (long)step;
    }

    predictor = (long)state->predictor;
    if ((code & 8u) != 0u) {
        predictor -= difference;
    } else {
        predictor += difference;
    }
    state->predictor = clamp_predictor(predictor);

    next_index = (int)state->step_index +
        ima_adpcm_index_delta[code & 7u];
    state->step_index = clamp_step_index(next_index);
    return state->predictor;
}

void ima_adpcm_decode_byte(ImaAdpcmState* state, unsigned char packed,
    int output[2])
{
    output[0] = ima_adpcm_decode_nibble(state,
        (unsigned char)(packed & 0x0fu));
    output[1] = ima_adpcm_decode_nibble(state,
        (unsigned char)((packed >> 4) & 0x0fu));
}

unsigned char ima_adpcm_encode_sample(ImaAdpcmState* state, int sample)
{
    long target;
    long difference;
    int step;
    int test_step;
    unsigned char code;

    target = (long)clamp_predictor((long)sample);
    difference = target - (long)state->predictor;
    code = 0u;
    if (difference < 0L) {
        code = 8u;
        difference = -difference;
    }

    step = ima_adpcm_step[state->step_index];
    test_step = step;
    if (difference >= (long)test_step) {
        code = (unsigned char)(code | 4u);
        difference -= (long)test_step;
    }
    test_step >>= 1;
    if (difference >= (long)test_step) {
        code = (unsigned char)(code | 2u);
        difference -= (long)test_step;
    }
    test_step >>= 1;
    if (difference >= (long)test_step) {
        code = (unsigned char)(code | 1u);
    }

    (void)ima_adpcm_decode_nibble(state, code);
    return code;
}

unsigned char ima_adpcm_pcm16_to_mikey_dac(int sample)
{
    long unsigned_level;
    unsigned char unsigned_pcm;

    unsigned_level = (long)clamp_predictor((long)sample) + 32768L;
    unsigned_pcm = (unsigned char)(unsigned_level / 256L);
    return (unsigned char)(unsigned_pcm ^ 0x80u);
}

#ifndef __CC65__
unsigned char ima_adpcm_voice_gain(unsigned char signed_dac)
{
    int signed_sample;
    int magnitude;
    int scaled;

    signed_sample = signed_dac < 0x80u
        ? (int)signed_dac : (int)signed_dac - 256;
    magnitude = signed_sample < 0 ? -signed_sample : signed_sample;
    scaled = (magnitude * 5) / 4;
    if (signed_sample < 0) {
        if (scaled > 128) {
            scaled = 128;
        }
        scaled = -scaled;
    } else if (scaled > 127) {
        scaled = 127;
    }
    return (unsigned char)scaled;
}
#endif
