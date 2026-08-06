#include "sound.h"

typedef struct SoundSequence {
    const SoundStep* steps;
    unsigned char count;
} SoundSequence;

static const SoundStep stage_one_bgm[] = {
    { 5u, 15u, 17u, SOUND_WAVE_TONE },
    { 9u, 15u, 15u, SOUND_WAVE_TONE },
    { 12u, 15u, 17u, SOUND_WAVE_PULSE },
    { 9u, 15u, 15u, SOUND_WAVE_TONE },
    { 6u, 15u, 17u, SOUND_WAVE_TONE },
    { 10u, 15u, 15u, SOUND_WAVE_TONE },
    { 13u, 15u, 17u, SOUND_WAVE_PULSE },
    { 10u, 15u, 15u, SOUND_WAVE_TONE }
};

static const SoundStep stage_two_bgm[] = {
    { 7u, 5u, 14u, SOUND_WAVE_PULSE },
    { 9u, 5u, 15u, SOUND_WAVE_PULSE },
    { 11u, 5u, 16u, SOUND_WAVE_PULSE },
    { 13u, 5u, 17u, SOUND_WAVE_PULSE },
    { 15u, 5u, 18u, SOUND_WAVE_METALLIC },
    { 13u, 5u, 16u, SOUND_WAVE_PULSE },
    { 11u, 5u, 15u, SOUND_WAVE_PULSE },
    { 9u, 5u, 14u, SOUND_WAVE_PULSE }
};

static const SoundStep stage_three_bgm[] = {
    { 3u, 18u, 18u, SOUND_WAVE_METALLIC },
    { SOUND_NOTE_REST, 9u, 0u, SOUND_WAVE_TONE },
    { 2u, 18u, 17u, SOUND_WAVE_METALLIC },
    { SOUND_NOTE_REST, 9u, 0u, SOUND_WAVE_TONE },
    { 4u, 12u, 16u, SOUND_WAVE_NOISE },
    { SOUND_NOTE_REST, 12u, 0u, SOUND_WAVE_TONE }
};

static const SoundStep shot_sfx[] = {
    { 15u, 4u, 28u, SOUND_WAVE_PULSE },
    { 12u, 4u, 22u, SOUND_WAVE_PULSE }
};

static const SoundStep enemy_defeat_sfx[] = {
    { 12u, 4u, 28u, SOUND_WAVE_METALLIC },
    { 8u, 4u, 24u, SOUND_WAVE_NOISE },
    { 4u, 4u, 18u, SOUND_WAVE_NOISE }
};

static const SoundStep power_up_sfx[] = {
    { 8u, 5u, 22u, SOUND_WAVE_TONE },
    { 12u, 5u, 25u, SOUND_WAVE_TONE },
    { 16u, 5u, 28u, SOUND_WAVE_PULSE }
};

static const SoundStep warning_sfx[] = {
    { 7u, 8u, 26u, SOUND_WAVE_METALLIC },
    { 10u, 8u, 28u, SOUND_WAVE_METALLIC },
    { 7u, 8u, 26u, SOUND_WAVE_METALLIC },
    { 10u, 8u, 28u, SOUND_WAVE_METALLIC }
};

static const SoundStep player_explosion_sfx[] = {
    { 12u, 8u, 31u, SOUND_WAVE_NOISE },
    { 8u, 8u, 27u, SOUND_WAVE_NOISE },
    { 5u, 8u, 22u, SOUND_WAVE_NOISE },
    { 2u, 8u, 15u, SOUND_WAVE_NOISE }
};

static const SoundStep stage_clear_sfx[] = {
    { 8u, 12u, 24u, SOUND_WAVE_TONE },
    { 12u, 12u, 27u, SOUND_WAVE_TONE },
    { 16u, 12u, 30u, SOUND_WAVE_PULSE }
};

static const SoundStep boss_defeat_sfx[] = {
    { 16u, 12u, 31u, SOUND_WAVE_METALLIC },
    { 12u, 12u, 29u, SOUND_WAVE_NOISE },
    { 8u, 12u, 26u, SOUND_WAVE_NOISE },
    { 4u, 12u, 22u, SOUND_WAVE_NOISE }
};

#define ARRAY_COUNT(values) \
    ((unsigned char)(sizeof(values) / sizeof((values)[0])))

static const SoundSequence bgm_sequences[SOUND_BGM_COUNT] = {
    { stage_one_bgm, ARRAY_COUNT(stage_one_bgm) },
    { stage_two_bgm, ARRAY_COUNT(stage_two_bgm) },
    { stage_three_bgm, ARRAY_COUNT(stage_three_bgm) }
};

static const SoundSequence sfx_sequences[SOUND_SFX_COUNT] = {
    { (const SoundStep*)0, 0u },
    { shot_sfx, ARRAY_COUNT(shot_sfx) },
    { enemy_defeat_sfx, ARRAY_COUNT(enemy_defeat_sfx) },
    { power_up_sfx, ARRAY_COUNT(power_up_sfx) },
    { warning_sfx, ARRAY_COUNT(warning_sfx) },
    { player_explosion_sfx, ARRAY_COUNT(player_explosion_sfx) },
    { stage_clear_sfx, ARRAY_COUNT(stage_clear_sfx) },
    { boss_defeat_sfx, ARRAY_COUNT(boss_defeat_sfx) }
};

static void set_silent_output(SoundOutput* output)
{
    output->active = 0u;
    output->note = SOUND_NOTE_REST;
    output->volume = 0u;
    output->wave = SOUND_WAVE_TONE;
}

static void load_bgm_step(SoundState* sound, unsigned char step)
{
    const SoundSequence* sequence;

    sequence = &bgm_sequences[sound->bgm_id];
    sound->bgm_step = step;
    sound->bgm_remaining = sequence->steps[step].duration;
}

static void start_sfx(SoundState* sound, unsigned char sfx_id)
{
    sound->sfx_id = sfx_id;
    sound->sfx_step = 0u;
    sound->sfx_remaining = sfx_sequences[sfx_id].steps[0].duration;
}

static void update_bgm_output(SoundState* sound)
{
    const SoundStep* step;

    if (sound->bgm_active == 0u) {
        set_silent_output(&sound->output_bgm);
        return;
    }
    step = &bgm_sequences[sound->bgm_id].steps[sound->bgm_step];
    sound->output_bgm.active = (unsigned char)(step->note != SOUND_NOTE_REST &&
        step->volume != 0u);
    sound->output_bgm.note = step->note;
    sound->output_bgm.volume = step->volume;
    sound->output_bgm.wave = step->wave;
}

static void update_sfx_output(SoundState* sound)
{
    const SoundStep* step;

    if (sound->sfx_id == SOUND_SFX_NONE) {
        set_silent_output(&sound->output_sfx);
        return;
    }
    step = &sfx_sequences[sound->sfx_id].steps[sound->sfx_step];
    sound->output_sfx.active = (unsigned char)(step->note != SOUND_NOTE_REST &&
        step->volume != 0u);
    sound->output_sfx.note = step->note;
    sound->output_sfx.volume = step->volume;
    sound->output_sfx.wave = step->wave;
}

static void advance_bgm(SoundState* sound)
{
    const SoundSequence* sequence;

    if (sound->bgm_active == 0u) {
        return;
    }
    --sound->bgm_remaining;
    if (sound->bgm_remaining != 0u) {
        return;
    }
    sequence = &bgm_sequences[sound->bgm_id];
    ++sound->bgm_step;
    if (sound->bgm_step == sequence->count) {
        sound->bgm_step = 0u;
    }
    sound->bgm_remaining = sequence->steps[sound->bgm_step].duration;
}

static void advance_sfx(SoundState* sound)
{
    const SoundSequence* sequence;

    if (sound->sfx_id == SOUND_SFX_NONE) {
        return;
    }
    --sound->sfx_remaining;
    if (sound->sfx_remaining != 0u) {
        return;
    }
    sequence = &sfx_sequences[sound->sfx_id];
    ++sound->sfx_step;
    if (sound->sfx_step < sequence->count) {
        sound->sfx_remaining = sequence->steps[sound->sfx_step].duration;
        return;
    }
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    if (sound->pending_stage_clear != 0u) {
        sound->pending_stage_clear = 0u;
        start_sfx(sound, SOUND_SFX_STAGE_CLEAR);
    }
}

void sound_init(SoundState* sound)
{
    /* BGM sequences continuously on MIKEY channel A once active; SFX are
     * independent on channel B and no longer overwrite it (APS-020). */
    sound->bgm_active = 1u;
    sound->bgm_id = SOUND_BGM_STAGE_ONE;
    load_bgm_step(sound, 0u);
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    update_bgm_output(sound);
    update_sfx_output(sound);
}

void sound_set_stage(SoundState* sound, unsigned char stage)
{
    if (stage < 1u || stage > SOUND_BGM_COUNT) {
        return;
    }
    sound->bgm_active = 1u;
    sound->bgm_id = (unsigned char)(stage - 1u);
    load_bgm_step(sound, 0u);
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    update_bgm_output(sound);
    update_sfx_output(sound);
}

void sound_stop_all(SoundState* sound)
{
    sound->bgm_active = 0u;
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    set_silent_output(&sound->output_bgm);
    set_silent_output(&sound->output_sfx);
}

void sound_request_sfx(SoundState* sound, unsigned char sfx_id)
{
    if (sfx_id == SOUND_SFX_NONE || sfx_id >= SOUND_SFX_COUNT) {
        return;
    }
    if (sound->sfx_id == SOUND_SFX_BOSS_DEFEAT &&
        sfx_id == SOUND_SFX_STAGE_CLEAR) {
        sound->pending_stage_clear = 1u;
        return;
    }
    if (sound->sfx_id != SOUND_SFX_NONE &&
        sound_get_sfx_priority(sfx_id) <
            sound_get_sfx_priority(sound->sfx_id)) {
        return;
    }
    start_sfx(sound, sfx_id);
    update_sfx_output(sound);
}

void sound_tick(SoundState* sound, unsigned char freeze_bgm)
{
    update_bgm_output(sound);
    update_sfx_output(sound);
    if (freeze_bgm == 0u) {
        advance_bgm(sound);
    }
    advance_sfx(sound);
}

const SoundStep* sound_get_bgm_step(unsigned char bgm_id,
    unsigned char step)
{
    if (bgm_id >= SOUND_BGM_COUNT ||
        step >= bgm_sequences[bgm_id].count) {
        return (const SoundStep*)0;
    }
    return &bgm_sequences[bgm_id].steps[step];
}

const SoundStep* sound_get_sfx_step(unsigned char sfx_id,
    unsigned char step)
{
    if (sfx_id == SOUND_SFX_NONE || sfx_id >= SOUND_SFX_COUNT ||
        step >= sfx_sequences[sfx_id].count) {
        return (const SoundStep*)0;
    }
    return &sfx_sequences[sfx_id].steps[step];
}

unsigned char sound_get_bgm_step_count(unsigned char bgm_id)
{
    if (bgm_id >= SOUND_BGM_COUNT) {
        return 0u;
    }
    return bgm_sequences[bgm_id].count;
}

unsigned char sound_get_sfx_step_count(unsigned char sfx_id)
{
    if (sfx_id == SOUND_SFX_NONE || sfx_id >= SOUND_SFX_COUNT) {
        return 0u;
    }
    return sfx_sequences[sfx_id].count;
}

unsigned char sound_get_sfx_priority(unsigned char sfx_id)
{
    if (sfx_id >= SOUND_SFX_COUNT) {
        return 0u;
    }
    return sfx_id;
}

unsigned int sound_get_sfx_length(unsigned char sfx_id)
{
    const SoundSequence* sequence;
    unsigned char i;
    unsigned int length;

    if (sfx_id == SOUND_SFX_NONE || sfx_id >= SOUND_SFX_COUNT) {
        return 0u;
    }
    sequence = &sfx_sequences[sfx_id];
    length = 0u;
    for (i = 0u; i < sequence->count; ++i) {
        length += sequence->steps[i].duration;
    }
    return length;
}
