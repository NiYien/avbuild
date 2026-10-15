# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify native ARM64 binaries, import libraries, codecs, and tile decoding."""
import ctypes
import json
import os
from pathlib import Path
import runpy
import struct
import sys

sdk = Path(sys.argv[1]).resolve()
root = Path(__file__).resolve().parents[1]

def pe_machine(path):
    data = path.read_bytes()
    assert data[:2] == b'MZ', path
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[offset:offset + 4] == b'PE\0\0', path
    return struct.unpack_from('<H', data, offset + 4)[0]

for path in [sdk / 'bin/ffmpeg.exe', *sorted((sdk / 'bin').glob('*.dll'))]:
    assert pe_machine(path) == 0xaa64, ('Not ARM64', path)
for name in ('avcodec', 'avdevice', 'avfilter', 'avformat', 'avutil', 'swresample', 'swscale'):
    assert (sdk / 'lib' / (name + '.lib')).is_file(), name
with os.add_dll_directory(str(sdk / 'bin')):
    assert ctypes.CDLL(str(sdk / 'bin/avcodec-63.dll')).avcodec_version() >> 16 == 63

# Intel QSV and NVIDIA Windows CUDA are not ARM64 platform requirements.
# All portable codecs and the other Windows hardware interfaces stay required.
features = json.loads((root / 'tools/gyroflow-windows-features.json').read_text())
features = {kind: [name for name in names if not any(token in name for token in ('qsv', 'cuvid', 'nvenc', 'cuda'))]
            for kind, names in features.items()}
manifest = root / 'arm64-required-features.json'
manifest.write_text(json.dumps(features, indent=2) + '\n')
sys.argv = [str(root / 'tools/verify-hevc-tile-sdk.py'), str(sdk), str(manifest)]
runpy.run_path(sys.argv[0], run_name='__main__')
result = json.loads(Path('verification.json').read_text())
result.update(architecture='arm64',pe_machine='0xaa64',native_runtime_test=True)
for path in (Path('verification.json'), sdk / '.gyroflow-hevc-tile-patch.json'):
    path.write_text(json.dumps(result, indent=2) + '\n')
