#include "sound.h"
#include "music_data.h"

typedef struct SoundSequence {
    const SoundStep* steps;
    unsigned char count;
} SoundSequence;

/* BGM step tables are compiled from the assets/music MML sources by
 * tools/mml2c (APS-022) into the generated music_data translation unit.
 * SFX remain hand-tuned here: they are effect contours, not music. */

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
    { sound_bgm_stage_one_steps, SOUND_BGM_STAGE_ONE_STEP_COUNT },
    { sound_bgm_stage_two_steps, SOUND_BGM_STAGE_TWO_STEP_COUNT },
    { sound_bgm_stage_three_steps, SOUND_BGM_STAGE_THREE_STEP_COUNT }
};

/* APS-023: bassline steps compiled from the assets/music bass tracks
 * onto MIKEY channel C. Indexed by the same bgm_id as bgm_sequences;
 * each bass loop's total duration matches its melody's exactly (see
 * the assets/music bass MML file headers) so the two voices land back
 * on step 0 together, even though the bass has fewer, longer steps. */
static const SoundSequence bass_sequences[SOUND_BGM_COUNT] = {
    { sound_bgm_stage_one_bass_steps, SOUND_BGM_STAGE_ONE_BASS_STEP_COUNT },
    { sound_bgm_stage_two_bass_steps, SOUND_BGM_STAGE_TWO_BASS_STEP_COUNT },
    { sound_bgm_stage_three_bass_steps,
        SOUND_BGM_STAGE_THREE_BASS_STEP_COUNT }
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

/* Shared logical-output projection used by both channels (APS-021):
 * the previous update_bgm_output/update_sfx_output pair duplicated
 * this step-to-output copy verbatim. */
static void set_step_output(SoundOutput* output, const SoundStep* step)
{
    output->active = (unsigned char)(step->note != SOUND_NOTE_REST &&
        step->volume != 0u);
    output->note = step->note;
    output->volume = step->volume;
    output->wave = step->wave;
}

/* Shared step-cursor load/advance (APS-023): the melody and bass
 * voices each have their own SoundSequence and cursor fields but move
 * through them identically, so both go through these two helpers
 * instead of duplicating the loop-and-wrap logic per voice. */
static void load_step_cursor(const SoundSequence* sequence,
    unsigned char* step, unsigned char* remaining, unsigned char at)
{
    *step = at;
    *remaining = sequence->steps[at].duration;
}

static void advance_step_cursor(const SoundSequence* sequence,
    unsigned char* step, unsigned char* remaining)
{
    --(*remaining);
    if (*remaining != 0u) {
        return;
    }
    ++(*step);
    if (*step == sequence->count) {
        *step = 0u;
    }
    *remaining = sequence->steps[*step].duration;
}

static void load_bgm_step(SoundState* sound, unsigned char step)
{
    load_step_cursor(&bgm_sequences[sound->bgm_id], &sound->bgm_step,
        &sound->bgm_remaining, step);
}

static void load_bass_step(SoundState* sound, unsigned char step)
{
    load_step_cursor(&bass_sequences[sound->bgm_id], &sound->bass_step,
        &sound->bass_remaining, step);
}

static void start_sfx(SoundState* sound, unsigned char sfx_id)
{
    sound->sfx_id = sfx_id;
    sound->sfx_step = 0u;
    sound->sfx_remaining = sfx_sequences[sfx_id].steps[0].duration;
}

static void update_bgm_output(SoundState* sound)
{
    if (sound->bgm_active == 0u) {
        set_silent_output(&sound->output_bgm);
        return;
    }
    set_step_output(&sound->output_bgm,
        &bgm_sequences[sound->bgm_id].steps[sound->bgm_step]);
}

/* APS-023: the bassline (MIKEY channel C) follows the same bgm_active
 * gate as the melody so both voices start, freeze and stop together. */
static void update_bass_output(SoundState* sound)
{
    if (sound->bgm_active == 0u) {
        set_silent_output(&sound->output_bgm_bass);
        return;
    }
    set_step_output(&sound->output_bgm_bass,
        &bass_sequences[sound->bgm_id].steps[sound->bass_step]);
}

static void update_sfx_output(SoundState* sound)
{
    if (sound->sfx_id == SOUND_SFX_NONE) {
        set_silent_output(&sound->output_sfx);
        return;
    }
    set_step_output(&sound->output_sfx,
        &sfx_sequences[sound->sfx_id].steps[sound->sfx_step]);
}

/* APS-023: advances both the melody and bass cursors on the shared
 * bgm_active gate, so freeze_bgm (checked by the sound_tick caller)
 * freezes both voices together. Each voice keeps its own sequence and
 * step count, so a bass loop with fewer/longer steps than its melody
 * still wraps back to step 0 in phase every loop (their total
 * durations are equal; see the assets/music bass MML files). */
static void advance_bgm(SoundState* sound)
{
    if (sound->bgm_active == 0u) {
        return;
    }
    advance_step_cursor(&bgm_sequences[sound->bgm_id], &sound->bgm_step,
        &sound->bgm_remaining);
    advance_step_cursor(&bass_sequences[sound->bgm_id], &sound->bass_step,
        &sound->bass_remaining);
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

/* Shared restart used by sound_init and sound_set_stage (APS-021): both
 * enable the BGM at the head of the selected song and clear all SFX
 * state, exactly as the previous duplicated bodies did. */
static void restart_bgm(SoundState* sound, unsigned char bgm_id)
{
    /* BGM sequences continuously on MIKEY channel A once active; SFX
     * are independent on channel B and no longer overwrite it
     * (APS-020). */
    sound->bgm_active = 1u;
    sound->bgm_id = bgm_id;
    load_bgm_step(sound, 0u);
    load_bass_step(sound, 0u);
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    update_bgm_output(sound);
    update_bass_output(sound);
    update_sfx_output(sound);
}

void sound_init(SoundState* sound)
{
    restart_bgm(sound, SOUND_BGM_STAGE_ONE);
}

void sound_set_stage(SoundState* sound, unsigned char stage)
{
    if (stage < 1u || stage > SOUND_BGM_COUNT) {
        return;
    }
    restart_bgm(sound, (unsigned char)(stage - 1u));
}

void sound_stop_all(SoundState* sound)
{
    sound->bgm_active = 0u;
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    set_silent_output(&sound->output_bgm);
    set_silent_output(&sound->output_bgm_bass);
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
    update_bass_output(sound);
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

const SoundStep* sound_get_bgm_bass_step(unsigned char bgm_id,
    unsigned char step)
{
    if (bgm_id >= SOUND_BGM_COUNT ||
        step >= bass_sequences[bgm_id].count) {
        return (const SoundStep*)0;
    }
    return &bass_sequences[bgm_id].steps[step];
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

unsigned char sound_get_bgm_bass_step_count(unsigned char bgm_id)
{
    if (bgm_id >= SOUND_BGM_COUNT) {
        return 0u;
    }
    return bass_sequences[bgm_id].count;
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
