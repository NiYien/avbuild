/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exercise encoder teardown followed by a new session in the same process. */
#include <stdio.h>
#include <string.h>
#include <CoreFoundation/CoreFoundation.h>
#include <libavcodec/avcodec.h>
#include <libavutil/error.h>
#include <libavutil/hwcontext_videotoolbox.h>

static int describe_transfer(enum AVColorTransferCharacteristic trc, char *out, size_t size)
{
    CFStringRef value = av_map_videotoolbox_color_trc_from_av(trc);
    /* Do not retain this borrowed object: doing so could hide the regression. */
    return value && CFStringGetCString(value, out, size, kCFStringEncodingUTF8);
}

static int session(const AVCodec *codec, enum AVColorTransferCharacteristic trc)
{
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    AVFrame *frame = NULL;
    AVPacket *packet = NULL;
    AVDictionary *options = NULL;
    int ret = AVERROR(ENOMEM);
    if (!ctx) goto done;
    ctx->width = 640;
    ctx->height = 360;
    ctx->pix_fmt = AV_PIX_FMT_NV12;
    ctx->time_base = (AVRational){1, 25};
    ctx->framerate = (AVRational){25, 1};
    ctx->bit_rate = 1000000;
    ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    ctx->color_range = AVCOL_RANGE_MPEG;
    ctx->colorspace = AVCOL_SPC_BT709;
    ctx->color_primaries = AVCOL_PRI_BT709;
    ctx->color_trc = trc;
    av_dict_set(&options, "allow_sw", "1", 0);
    av_dict_set(&options, "realtime", "0", 0);
    ret = avcodec_open2(ctx, codec, &options);
    if (ret < 0) goto done;
    frame = av_frame_alloc();
    packet = av_packet_alloc();
    if (!frame || !packet) { ret = AVERROR(ENOMEM); goto done; }
    frame->format = ctx->pix_fmt;
    frame->width = ctx->width;
    frame->height = ctx->height;
    frame->pts = 0;
    frame->color_range = ctx->color_range;
    frame->colorspace = ctx->colorspace;
    frame->color_primaries = ctx->color_primaries;
    frame->color_trc = trc;
    ret = av_frame_get_buffer(frame, 32);
    if (ret < 0) goto done;
    memset(frame->data[0], 16, frame->linesize[0] * frame->height);
    memset(frame->data[1], 128, frame->linesize[1] * frame->height / 2);
    ret = avcodec_send_frame(ctx, frame);
    if (ret < 0) goto done;
    while ((ret = avcodec_receive_packet(ctx, packet)) >= 0) av_packet_unref(packet);
    if (ret != AVERROR(EAGAIN)) goto done;
    ret = avcodec_send_frame(ctx, NULL);
    if (ret < 0) goto done;
    while ((ret = avcodec_receive_packet(ctx, packet)) >= 0) av_packet_unref(packet);
    if (ret == AVERROR_EOF) ret = 0;
done:
    av_packet_free(&packet);
    av_frame_free(&frame);
    avcodec_free_context(&ctx);
    av_dict_free(&options);
    return ret;
}

int main(void)
{
    const AVCodec *codec = avcodec_find_encoder_by_name("h264_videotoolbox");
    char expected[256], actual[256], error[AV_ERROR_MAX_STRING_SIZE];
    const enum AVColorTransferCharacteristic trc = AVCOL_TRC_LOG;
    if (!codec || !describe_transfer(trc, expected, sizeof(expected))) return 1;
    printf("libavcodec=%u transfer=%s\n", avcodec_version(), expected);
    fflush(stdout);
    for (int i = 0; i < 4; ++i) {
        int ret = session(codec, trc);
        if (ret < 0) {
            av_strerror(ret, error, sizeof(error));
            fprintf(stderr, "session %d failed: %s\n", i, error);
            return 1;
        }
        if (!describe_transfer(trc, actual, sizeof(actual)) || strcmp(expected, actual)) return 2;
        printf("session %d closed; CoreVideo cached transfer string remains valid\n", i);
        fflush(stdout);
    }
    puts("VIDEOTOOLBOX_REOPEN_PASS");
    return 0;
}
