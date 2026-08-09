#ifndef IMA_ADPCM_H
#define IMA_ADPCM_H

/* Minimal mono IMA ADPCM state. Predictor samples use signed 16-bit range;
 * int is sufficient on both cc65/Lynx and the host test build. */
typedef struct ImaAdpcmState {
    int predictor;
    unsigned char step_index;
} ImaAdpcmState;

void ima_adpcm_init(ImaAdpcmState* state, int predictor,
    unsigned char step_index);
int ima_adpcm_decode_nibble(ImaAdpcmState* state, unsigned char nibble);
void ima_adpcm_decode_byte(ImaAdpcmState* state, unsigned char packed,
    int output[2]);
unsigned char ima_adpcm_encode_sample(ImaAdpcmState* state, int sample);
unsigned char ima_adpcm_pcm16_to_mikey_dac(int sample);
unsigned char ima_adpcm_voice_gain(unsigned char signed_dac);

#endif
