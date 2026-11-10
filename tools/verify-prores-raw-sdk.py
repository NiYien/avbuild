# SPDX-License-Identifier: GPL-3.0-or-later
"""Check ProRes RAW CFA layouts using a synthetic frame, without user footage."""
import base64
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import sys

# One 16x16 DC-only tile with four distinct components. Pattern 0's hash comes
# from the deployed n9.0.2 SDK. The physical GRBG permutation was independently
# checked against Resolve's bundled ProRes RAW decoder.
PACKET = base64.b64decode(
    "AAAAanBycmYASAAAYXRtMAAQABAAAAAAAADv/z+AAAA/gAAAP4AAAAAAAAAAAAAAAAAAAD+"
    "AAAAAAAAAAAAAAAAAAAA/gAAAP4AAABlkAAAAGEABAAQABAAEoAAfgMAAH4DgAB+A//AfgA=="
)
EXPECTED = {
    0: ("bayer_rggb16le", "ce08466fbec511f879f48a628529aa81f7a566aff3a83e6d0c2870a8c2d0bacf"),
    1: ("bayer_grbg16le", "1f6f3291656d9dbba29fc858229dce0ddeb831564d94d5615d921a1fecbe80b9"),
}
class Packet(c.Structure):
    _fields_ = [("buf", c.c_void_p), ("pts", c.c_int64), ("dts", c.c_int64),
                ("data", c.c_void_p), ("size", c.c_int), ("stream_index", c.c_int)]
class Frame(c.Structure):
    _fields_ = [("data", c.c_void_p * 8), ("linesize", c.c_int * 8),
                ("extended_data", c.c_void_p), ("width", c.c_int), ("height", c.c_int),
                ("nb_samples", c.c_int), ("format", c.c_int)]
def verify(libraries):
    def bind(name, args, result=c.c_int):
        function = next(getattr(lib, name) for lib in libraries if hasattr(lib, name))
        function.argtypes, function.restype = args, result
        return function
    find = bind("avcodec_find_decoder_by_name", [c.c_char_p], c.c_void_p)
    alloc = bind("avcodec_alloc_context3", [c.c_void_p], c.c_void_p)
    option = bind("av_opt_set_int", [c.c_void_p, c.c_char_p, c.c_int64, c.c_int])
    open_codec = bind("avcodec_open2", [c.c_void_p, c.c_void_p, c.c_void_p])
    alloc_packet = bind("av_packet_alloc", [], c.POINTER(Packet))
    new_packet = bind("av_new_packet", [c.POINTER(Packet), c.c_int])
    send = bind("avcodec_send_packet", [c.c_void_p, c.POINTER(Packet)])
    receive = bind("avcodec_receive_frame", [c.c_void_p, c.POINTER(Frame)])
    alloc_frame = bind("av_frame_alloc", [], c.POINTER(Frame))
    pix_name = bind("av_get_pix_fmt_name", [c.c_int], c.c_char_p)
    free_frame = bind("av_frame_free", [c.POINTER(c.POINTER(Frame))], None)
    free_packet = bind("av_packet_free", [c.POINTER(c.POINTER(Packet))], None)
    free_codec = bind("avcodec_free_context", [c.POINTER(c.c_void_p)], None)
    assert bind("avcodec_version", [], c.c_uint)() >> 16 == 63
    codec = find(b"prores_raw")
    assert codec
    checks = []
    for sequence in [[0], [1], [1, 0, 1], [2], [3]]:
        ctx = c.c_void_p(alloc(codec))
        assert ctx
        frame = alloc_frame()
        packet = alloc_packet()
        try:
            for key, value in [(b"threads", 1), (b"thread_type", 2), (b"apply_cropping", 0)]:
                assert option(ctx, key, value, 0) == 0
            assert open_codec(ctx, codec, None) == 0
            for pattern in sequence:
                data = bytearray(PACKET)
                data[25] = pattern
                # av_new_packet replaces the empty packet after the preceding unref.
                assert new_packet(packet, len(data)) == 0
                c.memmove(packet.contents.data, bytes(data), len(data))
                status = send(ctx, packet)
                bind("av_packet_unref", [c.POINTER(Packet)], None)(packet)
                if status == 0:
                    status = receive(ctx, frame)
                if pattern > 1:
                    assert status == -1163346256, (pattern, status)
                    continue
                assert status == 0, (pattern, status)
                value = frame.contents
                assert (value.width, value.height) == (16, 16)
                raw = b"".join(c.string_at(value.data[0] + y * value.linesize[0], 32) for y in range(16))
                actual = (pix_name(value.format).decode(), hashlib.sha256(raw).hexdigest())
                assert actual == EXPECTED[pattern], (pattern, actual, EXPECTED[pattern])
            checks.append(sequence)
        finally:
            free_packet(c.byref(packet))
            free_frame(c.byref(frame))
            free_codec(c.byref(ctx))
    return {"sequences": checks, "pixels_match_deployed_baseline": True,
            "physical_GRBG_layout": True, "unsupported_patterns_remain_rejected": True}

sdk = Path(sys.argv[1]).resolve()
with os.add_dll_directory(str(sdk / "bin")):
    util = c.CDLL(str(sdk / "bin/avutil-61.dll"))
    codec = c.CDLL(str(sdk / "bin/avcodec-63.dll"))
    result = {"split": verify([codec, util]),
              "monolithic": verify([c.CDLL(str(sdk / "bin/ffmpeg-9.dll"))])}
Path("prores-raw-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result), flush=True)
