/* mml2c: compile-time MML-style music compiler (APS-022).
 *
 * Host-only tool. Parses text tracks written in a small MML-like
 * language and emits fixed const SoundStep arrays as C source, so the
 * Lynx ROM never carries a runtime text parser. Strict C89, no dynamic
 * memory allocation, no floating point.
 *
 * Usage:
 *   mml2c <output-base> <name>=<file.mml> [<name>=<file.mml> ...]
 * Writes <output-base>.h and <output-base>.c. Every track becomes
 *   const SoundStep sound_bgm_<name>_steps[...]
 * plus a step-count macro SOUND_BGM_<NAME>_STEP_COUNT.
 *
 * Language (75Hz logic ticks, 16-entry scale from include/sound.h):
 *   ; comment to end of line      | bar separator (ignored)
 *   t<1-255>  default note length in ticks
 *   v<0-31>   volume              w<0-3>  wave (0 tone, 1 metallic,
 *                                          2 noise, 3 pulse)
 *   o<1-3>    octave              >  octave up      <  octave down
 *   c d e f g a b  scale degrees 1..7 of the current octave; the scale
 *             index is (octave - 1) * 7 + degree and must stay <= 16.
 *   n<1-16>   direct scale index escape hatch
 *   r         rest (index 0, volume 0, wave tone)
 *   A note, n or r may be followed by digits overriding its length in
 *   ticks for that step only (example: g12 or n15,12 for the n form).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TRACKS 8
#define MAX_STEPS 64
#define MAX_NAME 32
#define NOTE_INDEX_MAX 16
#define OCTAVE_MIN 1
#define OCTAVE_MAX 3

typedef struct Step {
    unsigned char note;
    unsigned char duration;
    unsigned char volume;
    unsigned char wave;
} Step;

typedef struct Track {
    char name[MAX_NAME];
    Step steps[MAX_STEPS];
    int step_count;
} Track;

static Track tracks[MAX_TRACKS];
static int track_count;

static void fail(const char* file, int line, const char* message)
{
    if (file != NULL) {
        fprintf(stderr, "mml2c: %s:%d: %s\n", file, line, message);
    } else {
        fprintf(stderr, "mml2c: %s\n", message);
    }
    exit(EXIT_FAILURE);
}

static int degree_for_letter(int letter)
{
    switch (letter) {
    case 'c': return 1;
    case 'd': return 2;
    case 'e': return 3;
    case 'f': return 4;
    case 'g': return 5;
    case 'a': return 6;
    case 'b': return 7;
    default: return 0;
    }
}

static int read_number(FILE* input, int* found)
{
    int value;
    int c;

    value = 0;
    *found = 0;
    for (;;) {
        c = fgetc(input);
        if (c < '0' || c > '9') {
            if (c != EOF) {
                ungetc(c, input);
            }
            return value;
        }
        *found = 1;
        value = value * 10 + (c - '0');
        if (value > 9999) {
            return value;
        }
    }
}

static void append_step(Track* track, const char* file, int line,
    int note, int duration, int volume, int wave)
{
    Step* step;

    if (track->step_count >= MAX_STEPS) {
        fail(file, line, "track exceeds the fixed 64 step limit");
    }
    if (duration < 1 || duration > 255) {
        fail(file, line, "step duration must stay within 1..255 ticks");
    }
    step = &track->steps[track->step_count];
    step->note = (unsigned char)note;
    step->duration = (unsigned char)duration;
    step->volume = (unsigned char)volume;
    step->wave = (unsigned char)wave;
    ++track->step_count;
}

static void parse_track(Track* track, const char* file)
{
    FILE* input;
    int line;
    int c;
    int octave;
    int volume;
    int wave;
    int default_ticks;
    int value;
    int found;

    input = fopen(file, "r");
    if (input == NULL) {
        fail(NULL, 0, "cannot open input track file");
    }
    line = 1;
    octave = 1;
    volume = 20;
    wave = 0;
    default_ticks = 8;

    for (;;) {
        c = fgetc(input);
        if (c == EOF) {
            break;
        }
        if (c == '\n') {
            ++line;
            continue;
        }
        if (c == ' ' || c == '\t' || c == '\r' || c == '|') {
            continue;
        }
        if (c == ';') {
            do {
                c = fgetc(input);
            } while (c != EOF && c != '\n');
            if (c == '\n') {
                ++line;
            }
            continue;
        }
        if (c == 't') {
            value = read_number(input, &found);
            if (!found || value < 1 || value > 255) {
                fail(file, line, "t needs a tick count within 1..255");
            }
            default_ticks = value;
            continue;
        }
        if (c == 'v') {
            value = read_number(input, &found);
            if (!found || value > 31) {
                fail(file, line, "v needs a volume within 0..31");
            }
            volume = value;
            continue;
        }
        if (c == 'w') {
            value = read_number(input, &found);
            if (!found || value > 3) {
                fail(file, line, "w needs a wave id within 0..3");
            }
            wave = value;
            continue;
        }
        if (c == 'o') {
            value = read_number(input, &found);
            if (!found || value < OCTAVE_MIN || value > OCTAVE_MAX) {
                fail(file, line, "o needs an octave within 1..3");
            }
            octave = value;
            continue;
        }
        if (c == '>') {
            if (octave >= OCTAVE_MAX) {
                fail(file, line, "> would leave the 1..3 octave range");
            }
            ++octave;
            continue;
        }
        if (c == '<') {
            if (octave <= OCTAVE_MIN) {
                fail(file, line, "< would leave the 1..3 octave range");
            }
            --octave;
            continue;
        }
        if (c == 'n') {
            int note;
            int ticks;

            note = read_number(input, &found);
            if (!found || note < 1 || note > NOTE_INDEX_MAX) {
                fail(file, line, "n needs a scale index within 1..16");
            }
            ticks = default_ticks;
            c = fgetc(input);
            if (c == ',') {
                ticks = read_number(input, &found);
                if (!found) {
                    fail(file, line, "',' needs a tick count after it");
                }
            } else if (c != EOF) {
                ungetc(c, input);
            }
            append_step(track, file, line, note, ticks, volume, wave);
            continue;
        }
        if (c == 'r') {
            value = read_number(input, &found);
            append_step(track, file, line, 0,
                found ? value : default_ticks, 0, 0);
            continue;
        }
        if (degree_for_letter(c) != 0) {
            int note;

            note = (octave - 1) * 7 + degree_for_letter(c);
            if (note > NOTE_INDEX_MAX) {
                fail(file, line, "note leaves the 16 entry scale table");
            }
            value = read_number(input, &found);
            append_step(track, file, line, note,
                found ? value : default_ticks, volume, wave);
            continue;
        }
        fail(file, line, "unknown MML command character");
    }
    fclose(input);
    if (track->step_count < 1) {
        fail(file, line, "track defines no steps");
    }
}

static void write_upper(FILE* output, const char* name)
{
    const char* p;

    for (p = name; *p != '\0'; ++p) {
        if (*p >= 'a' && *p <= 'z') {
            fputc(*p - 'a' + 'A', output);
        } else {
            fputc(*p, output);
        }
    }
}

static const char* base_name(const char* path)
{
    const char* slash;

    slash = strrchr(path, '/');
    return slash != NULL ? slash + 1 : path;
}

static void write_header(const char* output_base)
{
    char path[512];
    FILE* output;
    int i;

    sprintf(path, "%s.h", output_base);
    output = fopen(path, "w");
    if (output == NULL) {
        fail(NULL, 0, "cannot open generated header for writing");
    }
    fprintf(output,
        "/* Generated by tools/mml2c from assets/music. Do not edit. */\n"
        "#ifndef MUSIC_DATA_H\n#define MUSIC_DATA_H\n\n"
        "#include \"sound.h\"\n\n");
    for (i = 0; i < track_count; ++i) {
        fprintf(output, "#define SOUND_BGM_");
        write_upper(output, tracks[i].name);
        fprintf(output, "_STEP_COUNT %du\n", tracks[i].step_count);
        fprintf(output, "extern const SoundStep sound_bgm_%s_steps[];\n\n",
            tracks[i].name);
    }
    fprintf(output, "#endif\n");
    fclose(output);
}

static void write_source(const char* output_base)
{
    char path[512];
    FILE* output;
    int i;
    int j;

    sprintf(path, "%s.c", output_base);
    output = fopen(path, "w");
    if (output == NULL) {
        fail(NULL, 0, "cannot open generated source for writing");
    }
    fprintf(output,
        "/* Generated by tools/mml2c from assets/music. Do not edit. */\n"
        "#include \"%s.h\"\n", base_name(output_base));
    for (i = 0; i < track_count; ++i) {
        fprintf(output,
            "\nconst SoundStep sound_bgm_%s_steps[] = {\n",
            tracks[i].name);
        for (j = 0; j < tracks[i].step_count; ++j) {
            const Step* step;

            step = &tracks[i].steps[j];
            fprintf(output, "    { %uu, %uu, %uu, %uu }%s\n",
                (unsigned int)step->note, (unsigned int)step->duration,
                (unsigned int)step->volume, (unsigned int)step->wave,
                j + 1 < tracks[i].step_count ? "," : "");
        }
        fprintf(output, "};\n");
    }
    fclose(output);
}

int main(int argc, char** argv)
{
    int i;

    if (argc < 3 || argc > MAX_TRACKS + 2) {
        fprintf(stderr,
            "usage: mml2c <output-base> <name>=<file.mml> ...\n");
        return EXIT_FAILURE;
    }
    track_count = 0;
    for (i = 2; i < argc; ++i) {
        const char* equals;
        Track* track;
        size_t name_length;

        equals = strchr(argv[i], '=');
        if (equals == NULL || equals == argv[i]) {
            fail(NULL, 0, "track arguments must look like name=file.mml");
        }
        name_length = (size_t)(equals - argv[i]);
        if (name_length >= MAX_NAME) {
            fail(NULL, 0, "track name is too long");
        }
        track = &tracks[track_count];
        memcpy(track->name, argv[i], name_length);
        track->name[name_length] = '\0';
        track->step_count = 0;
        parse_track(track, equals + 1);
        ++track_count;
    }
    write_header(argv[1]);
    write_source(argv[1]);
    return EXIT_SUCCESS;
}
