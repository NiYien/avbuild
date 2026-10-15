#!/usr/bin/env python3
"""Reject an SDK build if the required color ownership patch was skipped."""
import hashlib
import json
import pathlib
import subprocess
import sys

source_root = pathlib.Path(sys.argv[1])
source = source_root / "libavcodec/videotoolboxenc.c"
text = source.read_text()
start = text.index("static void vtenc_reset(")
end = text.index("\nstatic ", start + 1)
reset = text[start:end]
for field in ("color_primaries", "transfer_function", "ycbcr_matrix"):
    assert f"CFRelease(vtctx->{field})" not in reset, f"borrowed {field} is still released"
    assert f"vtctx->{field} = NULL;" in reset, f"{field} is not cleared"
assert "CFRelease(vtctx->session)" in reset
assert "CFRelease(vtctx->supported_props)" in reset
manifest = {
    "ffmpeg_tag": "n9.0.2",
    "ffmpeg_commit": subprocess.check_output(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip(),
    "avbuild_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "patch": "videotoolbox-color-ownership-v1",
    "videotoolboxenc_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
}
for sdk in pathlib.Path.cwd().glob("sdk-*"):
    if sdk.is_dir():
        (sdk / "gyroflow-ffmpeg-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
