# SPDX-License-Identifier: GPL-3.0-or-later
"""Check the Windows SDK interface, codec selection, and HEVC tile output."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

sdk = Path(sys.argv[1]).resolve()
root = Path(__file__).resolve().parents[1]
source = root / 'ffmpeg-8.1'
exe = sdk / 'bin/ffmpeg.exe'
checks = {}

def output(*args):
    result = subprocess.run([str(exe), '-hide_banner', *args], capture_output=True, timeout=120, check=True)
    return (result.stdout + result.stderr).decode('utf-8', errors='replace')

version = output('-version')
assert re.search(r'libavcodec\s+62\.', version), version
assert 'tile_interleave' in output('-h', 'decoder=hevc')
checks['avcodec_major'] = 62
checks['tile_interleave_available'] = True
required = json.loads((root / 'tools/gyroflow-windows-features.json').read_text(encoding='utf-8'))
checks['features'] = {}
missing_features = {}
for category, expected in required.items():
    actual = set()
    for line in output('-' + category).splitlines():
        parts = line.split()
        if category == 'hwaccels':
            if len(parts) == 1 and re.fullmatch('[a-z0-9_]+', parts[0]):
                actual.add(parts[0])
        elif len(parts) >= 2 and re.fullmatch('[A-Z.]+', parts[0]) and parts[1] != '=':
            actual.update(parts[1].split(','))
    missing = sorted(set(expected) - actual)
    checks['features'][category] = dict(required=len(expected), available=len(actual), missing=missing)
    if missing:
        missing_features[category] = missing
Path('verification.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
assert not missing_features, missing_features
assert 'vulkan' in output('-h', 'decoder=dpx'), 'DPX Vulkan decoding is missing'

checks['conformance'] = []
sample_dir = root / 'verification-samples'
sample_dir.mkdir(exist_ok=True)
for name, filename in [('entry-points', 'TILES_A_Cisco_2.bit'), ('slices', 'TILES_B_Cisco_1.bit')]:
    sample = sample_dir / filename
    with urllib.request.urlopen('https://fate-suite.ffmpeg.org/hevc-conformance/' + filename, timeout=60) as response:
        sample.write_bytes(response.read())
    reference = (source / 'tests/ref/fate' / ('hevc-tile-row-order-' + name)).read_text(encoding='utf-8').splitlines()
    for threads in [1, 4]:
        crc = sample_dir / f'{name}-{threads}.framecrc'
        output('-nostdin', '-nostats', '-xerror', '-flags', '+bitexact', '-threads', str(threads),
               '-tile_interleave', '1', '-i', str(sample), '-an', '-pix_fmt', 'yuv420p',
               '-c:v', 'rawvideo', '-threads:v', '1', '-flags:v', '+bitexact', '-fflags', '+bitexact',
               '-f', 'framecrc', '-y', str(crc))
        assert crc.read_text(encoding='utf-8').splitlines() == reference, (name, threads)
        checks['conformance'].append(dict(case=name, threads=threads, matches_reference=True))

patch = root / 'patches/8.1/0038-hevc-tile-row-order.patch'
checks['ffmpeg_base'] = '9047fa1b084f76b1b4d065af2d743df1b40dfb56'
checks['upstream_patch_head'] = '52ac05875001327cef8e29ef8bf52c262e434c5c'
checks['patch_sha256'] = hashlib.sha256(patch.read_bytes()).hexdigest()
checks['dll_sha256'] = hashlib.sha256((sdk / 'bin/avcodec-62.dll').read_bytes()).hexdigest()
Path('verification.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
(sdk / '.gyroflow-hevc-tile-patch.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
print(json.dumps(checks, indent=2))
