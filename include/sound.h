#ifndef SOUND_H
#define SOUND_H

#define SOUND_BGM_STAGE_ONE 0u
#define SOUND_BGM_STAGE_TWO 1u
#define SOUND_BGM_STAGE_THREE 2u
#define SOUND_BGM_COUNT 3u

#define SOUND_SFX_NONE 0u
#define SOUND_SFX_SHOT 1u
#define SOUND_SFX_ENEMY_DEFEAT 2u
#define SOUND_SFX_POWER_UP 3u
#define SOUND_SFX_WARNING 4u
#define SOUND_SFX_PLAYER_EXPLOSION 5u
#define SOUND_SFX_STAGE_CLEAR 6u
#define SOUND_SFX_BOSS_DEFEAT 7u
#define SOUND_SFX_COUNT 8u

#define SOUND_NOTE_REST 0u
#define SOUND_NOTE_COUNT 16u

#define SOUND_WAVE_TONE 0u
#define SOUND_WAVE_METALLIC 1u
#define SOUND_WAVE_NOISE 2u
#define SOUND_WAVE_PULSE 3u
#define SOUND_WAVE_COUNT 4u

typedef struct SoundStep {
    unsigned char note;
    unsigned char duration;
    unsigned char volume;
    unsigned char wave;
} SoundStep;

typedef struct SoundOutput {
    unsigned char active;
    unsigned char note;
    unsigned char volume;
    unsigned char wave;
} SoundOutput;

typedef struct SoundState {
    unsigned char bgm_active;
    unsigned char bgm_id;
    unsigned char bgm_step;
    unsigned char bgm_remaining;
    unsigned char sfx_id;
    unsigned char sfx_step;
    unsigned char sfx_remaining;
    unsigned char pending_stage_clear;
    SoundOutput output_bgm;
    SoundOutput output_sfx;
} SoundState;

void sound_init(SoundState* sound);
void sound_set_stage(SoundState* sound, unsigned char stage);
void sound_stop_all(SoundState* sound);
void sound_request_sfx(SoundState* sound, unsigned char sfx_id);
void sound_tick(SoundState* sound, unsigned char freeze_bgm);
const SoundStep* sound_get_bgm_step(unsigned char bgm_id,
    unsigned char step);
const SoundStep* sound_get_sfx_step(unsigned char sfx_id,
    unsigned char step);
unsigned char sound_get_bgm_step_count(unsigned char bgm_id);
unsigned char sound_get_sfx_step_count(unsigned char sfx_id);
unsigned char sound_get_sfx_priority(unsigned char sfx_id);
unsigned int sound_get_sfx_length(unsigned char sfx_id);

#endif
