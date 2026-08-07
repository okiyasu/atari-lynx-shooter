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

/* Music voices, indexed 0..SOUND_MUSIC_VOICE_COUNT-1. Each voice owns
 * one per-bgm_id sequence table plus a cursor and a logical output
 * inside SoundState; all of them are wired up in music_voice() below.
 * Adding a third voice (a possible MIKEY channel D harmony) means: new
 * SoundState fields, one more table row here, one more branch in
 * music_voice() and a bumped count -- every loop below then covers it. */
#define MUSIC_VOICE_MELODY 0u
#define MUSIC_VOICE_BASS 1u
#define MUSIC_VOICE_COUNT 2u

static const SoundSequence* const music_sequence_tables[
    MUSIC_VOICE_COUNT] = {
    bgm_sequences,
    bass_sequences
};

/* Borrowed view of one music voice: where its sequence, cursor and
 * logical output live. Built on demand by music_voice() so the shared
 * load/advance/output helpers never care which voice they move. */
typedef struct MusicVoiceRef {
    const SoundSequence* sequence;
    unsigned char* step;
    unsigned char* remaining;
    SoundOutput* output;
} MusicVoiceRef;

static void music_voice(SoundState* sound, unsigned char voice,
    MusicVoiceRef* ref)
{
    ref->sequence = &music_sequence_tables[voice][sound->bgm_id];
    if (voice == MUSIC_VOICE_MELODY) {
        ref->step = &sound->bgm_step;
        ref->remaining = &sound->bgm_remaining;
        ref->output = &sound->output_bgm;
    } else {
        ref->step = &sound->bass_step;
        ref->remaining = &sound->bass_remaining;
        ref->output = &sound->output_bgm_bass;
    }
}

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

/* APS-026: derives this tick's volume from the step's base volume plus
 * how far the step has progressed, so a held note attacks up to its
 * base volume over its first ~20% of ticks, then decays to ~70% of
 * base over the rest -- instead of holding one flat volume for the
 * whole duration. `remaining` is ticks-left-inclusive-of-this-tick (as
 * tracked by the step cursor), so elapsed = duration - remaining is
 * 0 on the step's first tick. Pitch, wave and duration are untouched;
 * only the volume written to hardware changes per tick. */
static unsigned char envelope_volume(unsigned char base,
    unsigned char remaining, unsigned char duration)
{
    unsigned char elapsed;
    unsigned char attack_len;
    unsigned char decay_len;
    unsigned char decay_pos;
    unsigned int floor_vol;
    unsigned int vol;

    if (duration <= 1u || base == 0u) {
        return base;
    }
    elapsed = (unsigned char)(duration - remaining);
    attack_len = (unsigned char)(duration / 5u);
    if (attack_len == 0u) {
        attack_len = 1u;
    }
    if (attack_len >= duration) {
        attack_len = (unsigned char)(duration - 1u);
    }
    if (elapsed < attack_len) {
        vol = ((unsigned int)base * (unsigned int)(elapsed + 1u)) /
            attack_len;
    } else {
        decay_len = (unsigned char)(duration - attack_len);
        decay_pos = (unsigned char)(elapsed - attack_len);
        floor_vol = ((unsigned int)base * 7u) / 10u;
        if (decay_len <= 1u) {
            vol = base;
        } else {
            vol = (unsigned int)base - ((((unsigned int)base - floor_vol) *
                decay_pos) / (unsigned int)(decay_len - 1u));
        }
    }
    if (vol == 0u) {
        vol = 1u;
    }
    if (vol > base) {
        vol = base;
    }
    return (unsigned char)vol;
}

/* Shared logical-output projection used by both channels (APS-021):
 * the previous update_bgm_output/update_sfx_output pair duplicated
 * this step-to-output copy verbatim. */
static void set_step_output(SoundOutput* output, const SoundStep* step,
    unsigned char remaining)
{
    output->active = (unsigned char)(step->note != SOUND_NOTE_REST &&
        step->volume != 0u);
    output->note = step->note;
    output->volume = envelope_volume(step->volume, remaining,
        step->duration);
    output->wave = step->wave;
}

/* Shared step-cursor load/advance (APS-023): every music voice moves
 * through its own SoundSequence identically, so all of them go through
 * these two helpers instead of duplicating the loop-and-wrap logic per
 * voice. (SFX keep their own advance: they end instead of looping.) */
static void load_voice_step(const MusicVoiceRef* ref, unsigned char at)
{
    *ref->step = at;
    *ref->remaining = ref->sequence->steps[at].duration;
}

static void advance_voice_step(const MusicVoiceRef* ref)
{
    --(*ref->remaining);
    if (*ref->remaining != 0u) {
        return;
    }
    ++(*ref->step);
    if (*ref->step == ref->sequence->count) {
        *ref->step = 0u;
    }
    *ref->remaining = ref->sequence->steps[*ref->step].duration;
}

static void start_sfx(SoundState* sound, unsigned char sfx_id)
{
    sound->sfx_id = sfx_id;
    sound->sfx_step = 0u;
    sound->sfx_remaining = sfx_sequences[sfx_id].steps[0].duration;
}

/* APS-023: every music voice (the channel C bassline included) follows
 * the same bgm_active gate so all voices start, freeze and stop
 * together. */
static void update_music_outputs(SoundState* sound)
{
    MusicVoiceRef ref;
    unsigned char voice;

    for (voice = 0u; voice < MUSIC_VOICE_COUNT; ++voice) {
        music_voice(sound, voice, &ref);
        if (sound->bgm_active == 0u) {
            set_silent_output(ref.output);
        } else {
            set_step_output(ref.output, &ref.sequence->steps[*ref.step],
                *ref.remaining);
        }
    }
}

static void update_sfx_output(SoundState* sound)
{
    if (sound->sfx_id == SOUND_SFX_NONE) {
        set_silent_output(&sound->output_sfx);
        return;
    }
    set_step_output(&sound->output_sfx,
        &sfx_sequences[sound->sfx_id].steps[sound->sfx_step],
        sound->sfx_remaining);
}

/* APS-023: advances every music voice cursor on the shared bgm_active
 * gate, so freeze_bgm (checked by the sound_tick caller) freezes all
 * voices together. Each voice keeps its own sequence and step count,
 * so a bass loop with fewer/longer steps than its melody still wraps
 * back to step 0 in phase every loop (their total durations are equal;
 * see the assets/music bass MML files). */
static void advance_music(SoundState* sound)
{
    MusicVoiceRef ref;
    unsigned char voice;

    if (sound->bgm_active == 0u) {
        return;
    }
    for (voice = 0u; voice < MUSIC_VOICE_COUNT; ++voice) {
        music_voice(sound, voice, &ref);
        advance_voice_step(&ref);
    }
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
    MusicVoiceRef ref;
    unsigned char voice;

    /* BGM sequences continuously on MIKEY channels A/C once active;
     * SFX are independent on channel B and no longer overwrite it
     * (APS-020). */
    sound->bgm_active = 1u;
    sound->bgm_id = bgm_id;
    for (voice = 0u; voice < MUSIC_VOICE_COUNT; ++voice) {
        music_voice(sound, voice, &ref);
        load_voice_step(&ref, 0u);
    }
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    update_music_outputs(sound);
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
    MusicVoiceRef ref;
    unsigned char voice;

    sound->bgm_active = 0u;
    sound->sfx_id = SOUND_SFX_NONE;
    sound->sfx_step = 0u;
    sound->sfx_remaining = 0u;
    sound->pending_stage_clear = 0u;
    for (voice = 0u; voice < MUSIC_VOICE_COUNT; ++voice) {
        music_voice(sound, voice, &ref);
        set_silent_output(ref.output);
    }
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
    update_music_outputs(sound);
    update_sfx_output(sound);
    if (freeze_bgm == 0u) {
        advance_music(sound);
    }
    advance_sfx(sound);
}

/* Shared bounds-checked table lookups behind the per-voice public
 * accessors (sound_get_bgm_* / sound_get_bgm_bass_*). */
static const SoundStep* music_table_step(unsigned char voice,
    unsigned char bgm_id, unsigned char step)
{
    const SoundSequence* sequence;

    if (bgm_id >= SOUND_BGM_COUNT) {
        return (const SoundStep*)0;
    }
    sequence = &music_sequence_tables[voice][bgm_id];
    if (step >= sequence->count) {
        return (const SoundStep*)0;
    }
    return &sequence->steps[step];
}

static unsigned char music_table_step_count(unsigned char voice,
    unsigned char bgm_id)
{
    if (bgm_id >= SOUND_BGM_COUNT) {
        return 0u;
    }
    return music_sequence_tables[voice][bgm_id].count;
}

const SoundStep* sound_get_bgm_step(unsigned char bgm_id,
    unsigned char step)
{
    return music_table_step(MUSIC_VOICE_MELODY, bgm_id, step);
}

const SoundStep* sound_get_bgm_bass_step(unsigned char bgm_id,
    unsigned char step)
{
    return music_table_step(MUSIC_VOICE_BASS, bgm_id, step);
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
    return music_table_step_count(MUSIC_VOICE_MELODY, bgm_id);
}

unsigned char sound_get_bgm_bass_step_count(unsigned char bgm_id)
{
    return music_table_step_count(MUSIC_VOICE_BASS, bgm_id);
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
