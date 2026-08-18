#include <fcntl.h>
#include <unistd.h>

#include "static_layer_overlay.h"
#include "static_layer_overlay_data.h"

/* Single shared BSS home for whichever overlay group is currently resident.
 * Sized for the largest group (stage3/cave, 903B) with alignment margin;
 * see scripts/generate-static-layer.py OVERLAY_BUFFER_ALIGN. */
unsigned char static_layer_overlay_buffer[STATIC_LAYER_OVERLAY_BUFFER_SIZE];

/* The cc65 lynx-cart file API has one cart-wide read cursor and ignores the
 * fd passed to read(); title_voice.c hardcodes the same constant. */
#define STATIC_LAYER_OVERLAY_FILE_DESCRIPTOR 1

static void overlay_read(const char* file_name, unsigned size)
{
    open(file_name, O_RDONLY);
    read(STATIC_LAYER_OVERLAY_FILE_DESCRIPTOR, static_layer_overlay_buffer,
        size);
}

void static_layer_overlay_load(unsigned char which)
{
    switch (which) {
    case STATIC_LAYER_OVERLAY_STAGE1:
        overlay_read(STATIC_LAYER_OVERLAY_STAGE1_FILE,
            STATIC_LAYER_OVERLAY_STAGE1_SIZE);
        break;
    case STATIC_LAYER_OVERLAY_STAGE2:
        overlay_read(STATIC_LAYER_OVERLAY_STAGE2_FILE,
            STATIC_LAYER_OVERLAY_STAGE2_SIZE);
        break;
    case STATIC_LAYER_OVERLAY_STAGE3:
        overlay_read(STATIC_LAYER_OVERLAY_STAGE3_FILE,
            STATIC_LAYER_OVERLAY_STAGE3_SIZE);
        break;
    default:
        overlay_read(STATIC_LAYER_OVERLAY_TITLE_FILE,
            STATIC_LAYER_OVERLAY_TITLE_SIZE);
        break;
    }
}
