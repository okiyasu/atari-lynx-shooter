#include <fcntl.h>
#include <unistd.h>

#include "title_voice.h"
#include "game_over_voice_data.h"
#include "title_voice_data.h"
#include "title_voice_stream.h"

#define TITLE_VOICE_FILE_NAME "1"
#define GAME_OVER_VOICE_FILE_NAME "2"
#define TITLE_VOICE_FILE_DESCRIPTOR 1
#define TITLE_VOICE_CHUNK_SAMPLES 256u
#define TITLE_VOICE_ADPCM_CHUNK_SIZE 128u

static unsigned char adpcm_buffers[5][TITLE_VOICE_ADPCM_CHUNK_SIZE];
static unsigned staged_length;
static unsigned char staged_buffer;
static unsigned remaining_samples;
static unsigned char next_buffer;
static unsigned char stream_active;
static unsigned char stream_underrun;

static unsigned fill_buffer(unsigned char* output)
{
    unsigned samples;
    unsigned bytes;
    int received;

    samples = remaining_samples;
    if (samples > TITLE_VOICE_CHUNK_SAMPLES) {
        samples = TITLE_VOICE_CHUNK_SAMPLES;
    }
    if (samples == 0u) {
        return 0u;
    }
    bytes = (samples + 1u) / 2u;
    received = read(TITLE_VOICE_FILE_DESCRIPTOR, output, bytes);
    if (received != (int)bytes) {
        stream_underrun = 1u;
        remaining_samples = 0u;
        return 0u;
    }

    remaining_samples = (unsigned)(remaining_samples - samples);
    return samples;
}

static void queue_staged_buffer(void)
{
    if (staged_length == 0u ||
        title_voice_stream_can_queue() == 0u) {
        return;
    }
    title_voice_stream_set_queue_source(adpcm_buffers[staged_buffer]);
    if (title_voice_stream_queue(staged_length) != 0u) {
        staged_length = 0u;
    } else {
        stream_underrun = 1u;
    }
}

void title_voice_init(void)
{
    title_voice_stream_stop();
    remaining_samples = 0u;
    staged_length = 0u;
    next_buffer = 0u;
    staged_buffer = 0u;
    stream_active = 0u;
    stream_underrun = 0u;
}

static unsigned char voice_start(const char* file_name,
    unsigned sample_count)
{
    unsigned first_length;
    unsigned second_length;

    if (stream_active != 0u) {
        return 0u;
    }
    title_voice_init();
    if (open(file_name, O_RDONLY) < 0) {
        return 0u;
    }
    remaining_samples = sample_count;
    first_length = fill_buffer(adpcm_buffers[0]);
    if (first_length == 0u) {
        return 0u;
    }
    title_voice_stream_set_source(adpcm_buffers[0]);

    second_length = fill_buffer(adpcm_buffers[1]);
    if (second_length != 0u) {
        title_voice_stream_set_queue_source(adpcm_buffers[1]);
        if (title_voice_stream_queue(second_length) == 0u) {
            title_voice_stop();
            return 0u;
        }
        for (staged_buffer = 2u; staged_buffer < 4u; ++staged_buffer) {
            staged_length = fill_buffer(adpcm_buffers[staged_buffer]);
            if (staged_length == 0u) {
                break;
            }
            title_voice_stream_set_queue_source(
                adpcm_buffers[staged_buffer]);
            if (title_voice_stream_queue(staged_length) == 0u) {
                title_voice_stop();
                return 0u;
            }
        }
        staged_buffer = 4u;
        staged_length = fill_buffer(adpcm_buffers[staged_buffer]);
        next_buffer = 0u;
    } else {
        next_buffer = 2u;
    }
    title_voice_stream_start(first_length);
    stream_active = title_voice_stream_is_playing();
    return stream_active;
}

unsigned char title_voice_start(void)
{
    return voice_start(TITLE_VOICE_FILE_NAME, TITLE_VOICE_SAMPLE_COUNT);
}

unsigned char game_over_voice_start(void)
{
    return voice_start(GAME_OVER_VOICE_FILE_NAME,
        GAME_OVER_VOICE_SAMPLE_COUNT);
}

void title_voice_pump(void)
{
    if (stream_active == 0u) {
        return;
    }
    queue_staged_buffer();
    if (remaining_samples != 0u && staged_length == 0u) {
        staged_buffer = next_buffer;
        staged_length = fill_buffer(adpcm_buffers[staged_buffer]);
        ++next_buffer;
        if (next_buffer >= 5u) {
            next_buffer = 0u;
        }
        queue_staged_buffer();
    }
    if (title_voice_stream_is_playing() == 0u) {
        if (remaining_samples != 0u) {
            stream_underrun = 1u;
            remaining_samples = 0u;
        }
        stream_active = 0u;
    }
}

void title_voice_stop(void)
{
    title_voice_stream_stop();
    remaining_samples = 0u;
    staged_length = 0u;
    stream_active = 0u;
}

unsigned char title_voice_is_playing(void)
{
    return stream_active;
}

unsigned char title_voice_had_underrun(void)
{
    return stream_underrun;
}
