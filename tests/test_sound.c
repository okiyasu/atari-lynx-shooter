#include <stdio.h>
#include <stdlib.h>

#include "sound.h"

static unsigned int checks;

static void expect(int condition, const char* message)
{
    ++checks;
    if (!condition) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(EXIT_FAILURE);
    }
}

static void advance_sound(SoundState* sound, unsigned int frames,
    unsigned char freeze_bgm)
{
    unsigned int i;

    for (i = 0u; i < frames; ++i) {
        sound_tick(sound, freeze_bgm);
    }
}

static unsigned int bgm_length(unsigned char bgm_id)
{
    unsigned char i;
    unsigned int length;

    length = 0u;
    for (i = 0u; i < sound_get_bgm_step_count(bgm_id); ++i) {
        length += sound_get_bgm_step(bgm_id, i)->duration;
    }
    return length;
}

static unsigned int bgm_bass_length(unsigned char bgm_id)
{
    unsigned char i;
    unsigned int length;

    length = 0u;
    for (i = 0u; i < sound_get_bgm_bass_step_count(bgm_id); ++i) {
        length += sound_get_bgm_bass_step(bgm_id, i)->duration;
    }
    return length;
}

static void test_sequence_tables(void)
{
    unsigned char bgm;
    unsigned char sfx;
    unsigned char i;
    unsigned char minimum_note[SOUND_BGM_COUNT];
    unsigned char maximum_note[SOUND_BGM_COUNT];
    unsigned char rests[SOUND_BGM_COUNT];

    for (bgm = 0u; bgm < SOUND_BGM_COUNT; ++bgm) {
        minimum_note[bgm] = SOUND_NOTE_COUNT;
        maximum_note[bgm] = 0u;
        rests[bgm] = 0u;
        expect(sound_get_bgm_step_count(bgm) >= 6u,
            "every BGM has a bounded multi-step loop");
        for (i = 0u; i < sound_get_bgm_step_count(bgm); ++i) {
            const SoundStep* step;

            step = sound_get_bgm_step(bgm, i);
            expect(step != (const SoundStep*)0 && step->duration != 0u &&
                step->note <= SOUND_NOTE_COUNT &&
                step->volume <= 31u && step->wave < SOUND_WAVE_COUNT,
                "every BGM step stays inside fixed note duration volume wave bounds");
            if (step->note == SOUND_NOTE_REST) {
                ++rests[bgm];
                expect(step->volume == 0u,
                    "every BGM rest has zero logical volume");
            } else {
                if (step->note < minimum_note[bgm]) {
                    minimum_note[bgm] = step->note;
                }
                if (step->note > maximum_note[bgm]) {
                    maximum_note[bgm] = step->note;
                }
            }
        }
    }
    expect(sound_get_bgm_step(SOUND_BGM_COUNT, 0u) ==
            (const SoundStep*)0 &&
        sound_get_bgm_step(SOUND_BGM_STAGE_ONE,
            sound_get_bgm_step_count(SOUND_BGM_STAGE_ONE)) ==
            (const SoundStep*)0,
        "BGM table lookup rejects invalid song and step IDs");
    expect(sound_get_bgm_step_count(SOUND_BGM_COUNT) == 0u,
        "BGM step count rejects an invalid song ID");
    expect(sound_get_bgm_step(SOUND_BGM_STAGE_ONE, 0u)->duration == 15u &&
        sound_get_bgm_step(SOUND_BGM_STAGE_TWO, 0u)->duration == 5u &&
        sound_get_bgm_step(SOUND_BGM_STAGE_THREE, 0u)->duration == 18u,
        "three songs expose clearly different slow fast and sparse tempos");
    expect(minimum_note[SOUND_BGM_STAGE_THREE] <
            minimum_note[SOUND_BGM_STAGE_TWO] &&
        maximum_note[SOUND_BGM_STAGE_TWO] >
            maximum_note[SOUND_BGM_STAGE_THREE],
        "cave range is lower and flight range is higher than each other");
    expect(minimum_note[SOUND_BGM_STAGE_ONE] >= 1u &&
        maximum_note[SOUND_BGM_STAGE_ONE] <= 7u,
        "APS-024 space melody (Twinkle Twinkle Little Star) stays within a single diatonic octave");
    expect(rests[SOUND_BGM_STAGE_ONE] == 6u &&
        rests[SOUND_BGM_STAGE_TWO] == 0u &&
        rests[SOUND_BGM_STAGE_THREE] == 3u,
        "space now takes one phrase-end breath per phrase (APS-024); flight stays rest-free and cave keeps its frequent rests");
    expect(bgm_length(SOUND_BGM_STAGE_ONE) == 810u &&
        bgm_length(SOUND_BGM_STAGE_TWO) == 40u &&
        bgm_length(SOUND_BGM_STAGE_THREE) == 78u,
        "all three BGM loops have fixed distinct lengths");

    for (sfx = SOUND_SFX_SHOT; sfx < SOUND_SFX_COUNT; ++sfx) {
        unsigned int length;

        length = 0u;
        expect(sound_get_sfx_step_count(sfx) >= 2u,
            "every SFX has a bounded multi-step contour");
        for (i = 0u; i < sound_get_sfx_step_count(sfx); ++i) {
            const SoundStep* step;

            step = sound_get_sfx_step(sfx, i);
            expect(step != (const SoundStep*)0 && step->duration != 0u &&
                step->note > SOUND_NOTE_REST &&
                step->note <= SOUND_NOTE_COUNT &&
                step->volume <= 31u && step->wave < SOUND_WAVE_COUNT,
                "every SFX step stays inside all fixed logical bounds");
            length += step->duration;
        }
        expect(length == sound_get_sfx_length(sfx),
            "reported SFX length equals the sum of fixed step durations");
        expect(sound_get_sfx_priority(sfx) == sfx,
            "seven SFX IDs expose the specified ascending priorities");
    }
    expect(sound_get_sfx_step(SOUND_SFX_NONE, 0u) ==
            (const SoundStep*)0 &&
        sound_get_sfx_step(SOUND_SFX_COUNT, 0u) ==
            (const SoundStep*)0 &&
        sound_get_sfx_step_count(SOUND_SFX_NONE) == 0u &&
        sound_get_sfx_length(SOUND_SFX_COUNT) == 0u &&
        sound_get_sfx_priority(SOUND_SFX_COUNT) == 0u,
        "SFX metadata rejects none and out-of-range IDs");
    expect(sound_get_sfx_length(SOUND_SFX_PLAYER_EXPLOSION) <= 32u,
        "player explosion fits inside all 32 death updates");
    expect(sound_get_sfx_length(SOUND_SFX_BOSS_DEFEAT) +
            sound_get_sfx_length(SOUND_SFX_STAGE_CLEAR) < 120u,
        "boss defeat and deferred clear chain completes inside clear phase");
}

static void test_bgm_start_loop_stage_and_rest(void)
{
    SoundState sound;
    unsigned int stage_one_length;

    sound_init(&sound);
    expect(sound.bgm_active != 0u &&
        sound.bgm_id == SOUND_BGM_STAGE_ONE && sound.bgm_step == 0u &&
        sound.bgm_remaining == 15u && sound.output_bgm.active != 0u &&
        sound.output_sfx.active == 0u,
        "sound init enables stage one BGM at its head with no SFX active");
    stage_one_length = bgm_length(SOUND_BGM_STAGE_ONE);
    advance_sound(&sound, stage_one_length * 2u, 0u);
    expect(sound.bgm_step == 0u && sound.bgm_remaining == 15u &&
        sound.bgm_active != 0u && sound.output_sfx.active == 0u,
        "enabled BGM keeps looping back to its head and channel B stays free");

    sound_set_stage(&sound, 2u);
    expect(sound.bgm_id == SOUND_BGM_STAGE_TWO && sound.bgm_step == 0u &&
        sound.bgm_remaining == 5u && sound.bgm_active != 0u &&
        sound.output_bgm.active != 0u,
        "stage switch restarts the retained BGM metadata enabled at its head");

    sound_set_stage(&sound, 3u);
    expect(sound.bgm_id == SOUND_BGM_STAGE_THREE && sound.bgm_step == 0u &&
        sound.bgm_remaining == 18u && sound.bgm_active != 0u,
        "stage three switch starts the cave motif enabled at its head");
    sound_set_stage(&sound, 0u);
    expect(sound.bgm_id == SOUND_BGM_STAGE_THREE,
        "invalid stage switch leaves the current BGM unchanged");
}

static void test_sfx_priority_retrigger_and_bgm_progress(void)
{
    SoundState sound;
    unsigned char active;
    unsigned char request;

    sound_init(&sound);
    sound_request_sfx(&sound, SOUND_SFX_SHOT);
    expect(sound.sfx_id == SOUND_SFX_SHOT && sound.sfx_step == 0u &&
        sound.sfx_remaining == 4u && sound.output_sfx.note == 15u &&
        sound.output_bgm.active != 0u,
        "shot request starts its first step immediately alongside BGM");
    advance_sound(&sound, 3u, 0u);
    sound_request_sfx(&sound, SOUND_SFX_SHOT);
    expect(sound.sfx_id == SOUND_SFX_SHOT && sound.sfx_step == 0u &&
        sound.sfx_remaining == 4u,
        "same SFX request restarts the active sound from its head");

    for (active = SOUND_SFX_SHOT; active < SOUND_SFX_COUNT; ++active) {
        sound_init(&sound);
        sound_request_sfx(&sound, active);
        for (request = SOUND_SFX_SHOT; request < active; ++request) {
            sound_request_sfx(&sound, request);
            expect(sound.sfx_id == active,
                "every lower-priority request is discarded without replacement");
        }
    }
    for (active = SOUND_SFX_SHOT; active < SOUND_SFX_BOSS_DEFEAT; ++active) {
        sound_init(&sound);
        sound_request_sfx(&sound, active);
        sound_request_sfx(&sound, (unsigned char)(active + 1u));
        expect(sound.sfx_id == (unsigned char)(active + 1u) &&
            sound.sfx_step == 0u,
            "every higher-priority request replaces from the new sound head");
    }

    sound_init(&sound);
    sound_request_sfx(&sound, SOUND_SFX_ENEMY_DEFEAT);
    advance_sound(&sound,
        sound_get_sfx_length(SOUND_SFX_ENEMY_DEFEAT), 0u);
    expect(sound.sfx_id == SOUND_SFX_NONE && sound.bgm_active != 0u,
        "normal SFX finishes while BGM keeps running independently");
    sound_tick(&sound, 0u);
    expect(sound.output_sfx.active == 0u && sound.output_bgm.active != 0u,
        "later ticks leave SFX silent while BGM output keeps sounding");
}

static void test_freeze_pending_and_stops(void)
{
    SoundState sound;
    unsigned int boss_length;
    unsigned int clear_length;
    unsigned char frozen_step;
    unsigned char frozen_remaining;

    sound_init(&sound);
    advance_sound(&sound, 7u, 0u);
    frozen_step = sound.bgm_step;
    frozen_remaining = sound.bgm_remaining;
    sound_request_sfx(&sound, SOUND_SFX_PLAYER_EXPLOSION);
    advance_sound(&sound, 31u, 1u);
    expect(sound.bgm_active != 0u && sound.bgm_step == frozen_step &&
        sound.bgm_remaining == frozen_remaining &&
        sound.sfx_id == SOUND_SFX_PLAYER_EXPLOSION,
        "first 31 death updates freeze the BGM cursor while explosion SFX progresses");
    sound_tick(&sound, 1u);
    expect(sound.sfx_id == SOUND_SFX_NONE &&
        sound.bgm_step == frozen_step &&
        sound.bgm_remaining == frozen_remaining,
        "death update 32 finishes the explosion SFX with the BGM cursor still frozen");
    sound_tick(&sound, 0u);
    expect(sound.output_bgm.active != 0u &&
        sound.bgm_remaining == (unsigned char)(frozen_remaining - 1u),
        "post-respawn update thaws the BGM cursor and resumes its progress");

    sound_init(&sound);
    sound_request_sfx(&sound, SOUND_SFX_BOSS_DEFEAT);
    sound_request_sfx(&sound, SOUND_SFX_STAGE_CLEAR);
    sound_request_sfx(&sound, SOUND_SFX_STAGE_CLEAR);
    expect(sound.sfx_id == SOUND_SFX_BOSS_DEFEAT &&
        sound.pending_stage_clear != 0u,
        "clear request during boss defeat creates one idempotent pending entry");
    boss_length = sound_get_sfx_length(SOUND_SFX_BOSS_DEFEAT);
    clear_length = sound_get_sfx_length(SOUND_SFX_STAGE_CLEAR);
    advance_sound(&sound, boss_length, 0u);
    expect(sound.sfx_id == SOUND_SFX_STAGE_CLEAR &&
        sound.sfx_step == 0u && sound.pending_stage_clear == 0u,
        "boss completion promotes deferred stage clear exactly once from head");
    advance_sound(&sound, clear_length, 0u);
    expect(sound.sfx_id == SOUND_SFX_NONE &&
        boss_length + clear_length < 120u,
        "boss and clear chain ends before stage-clear transition boundary");

    sound_request_sfx(&sound, SOUND_SFX_WARNING);
    sound.pending_stage_clear = 1u;
    sound_set_stage(&sound, 2u);
    expect(sound.bgm_active != 0u && sound.bgm_id == SOUND_BGM_STAGE_TWO &&
        sound.bgm_step == 0u && sound.sfx_id == SOUND_SFX_NONE &&
        sound.pending_stage_clear == 0u,
        "stage switch restarts BGM at the next song head and clears active and pending SFX");
    sound_request_sfx(&sound, SOUND_SFX_BOSS_DEFEAT);
    sound.pending_stage_clear = 1u;
    sound_stop_all(&sound);
    expect(sound.bgm_active == 0u && sound.sfx_id == SOUND_SFX_NONE &&
        sound.pending_stage_clear == 0u &&
        sound.output_bgm.active == 0u && sound.output_bgm.volume == 0u &&
        sound.output_sfx.active == 0u && sound.output_sfx.volume == 0u,
        "terminal stop clears BGM active SFX pending slot and both channel outputs");
    sound_tick(&sound, 0u);
    expect(sound.output_bgm.active == 0u && sound.output_sfx.active == 0u,
        "stopped sound remains silent on both channels across later ticks");
    sound_init(&sound);
    expect(sound.bgm_id == SOUND_BGM_STAGE_ONE && sound.bgm_step == 0u &&
        sound.bgm_active != 0u && sound.sfx_id == SOUND_SFX_NONE &&
        sound.pending_stage_clear == 0u,
        "complete restart returns to stage one song head enabled with no SFX");
}

/* APS-022: the BGM tables are now compiled from the assets/music MML
 * sources by mml2c. This regression pins every generated step to the
 * designed values, proving the MML source is compiled byte-identically.
 * Stage one was replaced in APS-024 ("Twinkle Twinkle Little Star",
 * public domain) to be recognizable as a real melody instead of the
 * APS-020 arpeggio placeholder; stage two/three are unchanged. */
static void test_bgm_exact_mml_migration(void)
{
    static const SoundStep expected_stage_one[48] = {
        { 1u, 15u, 17u, SOUND_WAVE_TONE },
        { 1u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 6u, 15u, 17u, SOUND_WAVE_TONE },
        { 6u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 30u, 17u, SOUND_WAVE_TONE },
        { SOUND_NOTE_REST, 15u, 0u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 2u, 15u, 17u, SOUND_WAVE_TONE },
        { 2u, 15u, 17u, SOUND_WAVE_TONE },
        { 1u, 30u, 17u, SOUND_WAVE_TONE },
        { SOUND_NOTE_REST, 15u, 0u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 2u, 30u, 17u, SOUND_WAVE_TONE },
        { SOUND_NOTE_REST, 15u, 0u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 2u, 30u, 17u, SOUND_WAVE_TONE },
        { SOUND_NOTE_REST, 15u, 0u, SOUND_WAVE_TONE },
        { 1u, 15u, 17u, SOUND_WAVE_TONE },
        { 1u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 15u, 17u, SOUND_WAVE_TONE },
        { 6u, 15u, 17u, SOUND_WAVE_TONE },
        { 6u, 15u, 17u, SOUND_WAVE_TONE },
        { 5u, 30u, 17u, SOUND_WAVE_TONE },
        { SOUND_NOTE_REST, 15u, 0u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 4u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 3u, 15u, 17u, SOUND_WAVE_TONE },
        { 2u, 15u, 17u, SOUND_WAVE_TONE },
        { 2u, 15u, 17u, SOUND_WAVE_TONE },
        { 1u, 30u, 17u, SOUND_WAVE_TONE },
        { SOUND_NOTE_REST, 15u, 0u, SOUND_WAVE_TONE }
    };
    static const SoundStep expected_stage_two[8] = {
        { 7u, 5u, 14u, SOUND_WAVE_PULSE },
        { 9u, 5u, 15u, SOUND_WAVE_PULSE },
        { 11u, 5u, 16u, SOUND_WAVE_PULSE },
        { 13u, 5u, 17u, SOUND_WAVE_PULSE },
        { 15u, 5u, 18u, SOUND_WAVE_METALLIC },
        { 13u, 5u, 16u, SOUND_WAVE_PULSE },
        { 11u, 5u, 15u, SOUND_WAVE_PULSE },
        { 9u, 5u, 14u, SOUND_WAVE_PULSE }
    };
    static const SoundStep expected_stage_three[6] = {
        { 3u, 18u, 18u, SOUND_WAVE_METALLIC },
        { SOUND_NOTE_REST, 9u, 0u, SOUND_WAVE_TONE },
        { 2u, 18u, 17u, SOUND_WAVE_METALLIC },
        { SOUND_NOTE_REST, 9u, 0u, SOUND_WAVE_TONE },
        { 4u, 12u, 16u, SOUND_WAVE_NOISE },
        { SOUND_NOTE_REST, 12u, 0u, SOUND_WAVE_TONE }
    };
    static const SoundStep* const expected[SOUND_BGM_COUNT] = {
        expected_stage_one, expected_stage_two, expected_stage_three
    };
    unsigned char bgm;
    unsigned char i;

    expect(sound_get_bgm_step_count(SOUND_BGM_STAGE_ONE) == 48u &&
        sound_get_bgm_step_count(SOUND_BGM_STAGE_TWO) == 8u &&
        sound_get_bgm_step_count(SOUND_BGM_STAGE_THREE) == 6u,
        "MML-compiled BGM tracks keep the exact APS-020 step counts");
    for (bgm = 0u; bgm < SOUND_BGM_COUNT; ++bgm) {
        for (i = 0u; i < sound_get_bgm_step_count(bgm); ++i) {
            const SoundStep* step;

            step = sound_get_bgm_step(bgm, i);
            expect(step->note == expected[bgm][i].note &&
                step->duration == expected[bgm][i].duration &&
                step->volume == expected[bgm][i].volume &&
                step->wave == expected[bgm][i].wave,
                "every MML-compiled BGM step is byte-identical to APS-020");
        }
    }
}

static void test_bgm_and_sfx_sound_together(void)
{
    SoundState sound;
    unsigned char bgm_remaining_before;

    sound_init(&sound);
    advance_sound(&sound, 3u, 0u);
    bgm_remaining_before = sound.bgm_remaining;
    sound_request_sfx(&sound, SOUND_SFX_SHOT);
    expect(sound.output_bgm.active != 0u && sound.output_sfx.active != 0u,
        "requesting an SFX no longer overwrites the independently active BGM output");
    advance_sound(&sound, 1u, 0u);
    expect(sound.bgm_remaining ==
            (unsigned char)(bgm_remaining_before - 1u) &&
        sound.sfx_step == 0u && sound.sfx_remaining == 3u,
        "BGM keeps advancing on its own 75Hz schedule while SFX plays concurrently");
}

/* APS-023: MIKEY channel C carries a second bassline voice, compiled
 * from assets/music's *_bass.mml sources the same way as the melody
 * (APS-022). These checks pin its table content and behavior. */
static void test_bass_tables_bounds_and_phase_lock(void)
{
    unsigned char bgm;
    unsigned char i;

    for (bgm = 0u; bgm < SOUND_BGM_COUNT; ++bgm) {
        expect(sound_get_bgm_bass_step_count(bgm) >= 2u,
            "every bass track has a bounded multi-step loop");
        for (i = 0u; i < sound_get_bgm_bass_step_count(bgm); ++i) {
            const SoundStep* step;

            step = sound_get_bgm_bass_step(bgm, i);
            expect(step != (const SoundStep*)0 && step->duration != 0u &&
                step->note != SOUND_NOTE_REST &&
                step->note <= SOUND_NOTE_COUNT &&
                step->volume >= 14u && step->volume <= 18u &&
                (step->wave == SOUND_WAVE_TONE ||
                    step->wave == SOUND_WAVE_PULSE),
                "every bass step is a non-rest tone or pulse note inside its designed volume band");
        }
        expect(bgm_bass_length(bgm) == bgm_length(bgm),
            "each stage's bass loop duration matches its melody's exactly so both voices stay phase locked");
    }
    expect(sound_get_bgm_bass_step(SOUND_BGM_COUNT, 0u) ==
            (const SoundStep*)0 &&
        sound_get_bgm_bass_step(SOUND_BGM_STAGE_ONE,
            sound_get_bgm_bass_step_count(SOUND_BGM_STAGE_ONE)) ==
            (const SoundStep*)0 &&
        sound_get_bgm_bass_step_count(SOUND_BGM_COUNT) == 0u,
        "bass table lookup rejects invalid song and step IDs exactly like the melody table");
}

/* Pins every generated bass step to the assets/music bass MML sources,
 * the same way test_bgm_exact_mml_migration pins the melody. */
static void test_bass_exact_mml_compile(void)
{
    static const SoundStep expected_stage_one_bass[6] = {
        { 1u, 135u, 16u, SOUND_WAVE_TONE },
        { 4u, 135u, 16u, SOUND_WAVE_TONE },
        { 5u, 135u, 16u, SOUND_WAVE_TONE },
        { 5u, 135u, 16u, SOUND_WAVE_TONE },
        { 1u, 135u, 16u, SOUND_WAVE_TONE },
        { 4u, 135u, 16u, SOUND_WAVE_TONE }
    };
    static const SoundStep expected_stage_two_bass[2] = {
        { 2u, 20u, 15u, SOUND_WAVE_PULSE },
        { 5u, 20u, 15u, SOUND_WAVE_PULSE }
    };
    static const SoundStep expected_stage_three_bass[3] = {
        { 1u, 27u, 14u, SOUND_WAVE_TONE },
        { 4u, 27u, 14u, SOUND_WAVE_TONE },
        { 1u, 24u, 14u, SOUND_WAVE_TONE }
    };
    static const SoundStep* const expected[SOUND_BGM_COUNT] = {
        expected_stage_one_bass, expected_stage_two_bass,
        expected_stage_three_bass
    };
    static const unsigned char expected_count[SOUND_BGM_COUNT] = {
        6u, 2u, 3u
    };
    unsigned char bgm;
    unsigned char i;

    for (bgm = 0u; bgm < SOUND_BGM_COUNT; ++bgm) {
        expect(sound_get_bgm_bass_step_count(bgm) == expected_count[bgm],
            "every MML-compiled bass track keeps its designed step count");
        for (i = 0u; i < sound_get_bgm_bass_step_count(bgm); ++i) {
            const SoundStep* step;

            step = sound_get_bgm_bass_step(bgm, i);
            expect(step->note == expected[bgm][i].note &&
                step->duration == expected[bgm][i].duration &&
                step->volume == expected[bgm][i].volume &&
                step->wave == expected[bgm][i].wave,
                "every MML-compiled bass step is byte-identical to its designed source");
        }
    }
}

static void test_bass_syncs_with_bgm_start_freeze_stage_and_stop(void)
{
    SoundState sound;
    unsigned int stage_one_length;
    unsigned char frozen_bgm_step;
    unsigned char frozen_bgm_remaining;
    unsigned char frozen_bass_step;
    unsigned char frozen_bass_remaining;

    sound_init(&sound);
    expect(sound.bass_step == 0u &&
        sound.bass_remaining ==
            sound_get_bgm_bass_step(SOUND_BGM_STAGE_ONE, 0u)->duration &&
        sound.output_bgm_bass.active != 0u,
        "sound init enables the stage one bassline at its head alongside the melody");

    stage_one_length = bgm_length(SOUND_BGM_STAGE_ONE);
    advance_sound(&sound, stage_one_length, 0u);
    expect(sound.bgm_step == 0u && sound.bass_step == 0u,
        "melody and bass both wrap back to step zero after one full phase-locked loop");

    advance_sound(&sound, 7u, 0u);
    frozen_bgm_step = sound.bgm_step;
    frozen_bgm_remaining = sound.bgm_remaining;
    frozen_bass_step = sound.bass_step;
    frozen_bass_remaining = sound.bass_remaining;
    sound_request_sfx(&sound, SOUND_SFX_PLAYER_EXPLOSION);
    advance_sound(&sound, 31u, 1u);
    expect(sound.bgm_step == frozen_bgm_step &&
        sound.bgm_remaining == frozen_bgm_remaining &&
        sound.bass_step == frozen_bass_step &&
        sound.bass_remaining == frozen_bass_remaining,
        "the death freeze holds the melody and bass cursors together");
    sound_tick(&sound, 1u);
    expect(sound.bass_step == frozen_bass_step &&
        sound.bass_remaining == frozen_bass_remaining,
        "death update 32 still holds the bass cursor while the explosion SFX finishes");
    sound_tick(&sound, 0u);
    expect(sound.bass_remaining ==
            (unsigned char)(frozen_bass_remaining - 1u),
        "post-respawn update thaws the bass cursor and resumes its progress");

    sound_set_stage(&sound, 2u);
    expect(sound.bass_step == 0u &&
        sound.bass_remaining ==
            sound_get_bgm_bass_step(SOUND_BGM_STAGE_TWO, 0u)->duration &&
        sound.output_bgm_bass.active != 0u,
        "stage switch restarts the bassline at the new stage's head alongside the melody");

    sound_stop_all(&sound);
    expect(sound.output_bgm_bass.active == 0u &&
        sound.output_bgm_bass.volume == 0u,
        "terminal stop silences the bass channel exactly like the melody channel");
    sound_tick(&sound, 0u);
    expect(sound.output_bgm_bass.active == 0u,
        "stopped bass output remains silent across later ticks");
}

int main(void)
{
    test_sequence_tables();
    test_bgm_start_loop_stage_and_rest();
    test_sfx_priority_retrigger_and_bgm_progress();
    test_freeze_pending_and_stops();
    test_bgm_exact_mml_migration();
    test_bgm_and_sfx_sound_together();
    test_bass_tables_bounds_and_phase_lock();
    test_bass_exact_mml_compile();
    test_bass_syncs_with_bgm_start_freeze_stage_and_stop();
    printf("PASS: %u sound logic checks\n", checks);
    return EXIT_SUCCESS;
}
