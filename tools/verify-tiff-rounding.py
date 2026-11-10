# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare the real TIFF normalization helper against Windows CRT rounding.

Run in an x64 MSVC developer shell: python verify-tiff-rounding.py SOURCE SDK OUTPUT
The SDK headers must come from the same FFmpeg source revision.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('sdk', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
source = args.source.resolve()
sdk = args.sdk.resolve()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
tiff = (source / 'libavcodec/tiff.c').read_text(encoding='utf-8')
match = re.search(r'static uint16_t av_always_inline dng_process_color16\(.*?\n\}', tiff, re.S)
assert match, 'TIFF normalization helper was not found'
optimized = match.group()
branch = r'#if defined\(_M_X64\).*?#else\n(.*?)#endif'
baseline, count = re.subn(branch, lambda m: m.group(1), optimized, flags=re.S)
assert count == 1 and '_mm_cvtss_si32' in optimized, 'Expected x64 optimization is missing'
preamble = r'''#include <windows.h>
#include <xmmintrin.h>
#include <cstdio>
#include <cmath>
#include <cfenv>
#include <cstdint>
#include <cfloat>
#include <initializer_list>
extern "C" {
#include "libavutil/common.h"
}
#pragma fenv_access(on)
static long (*reference_lrintf)(float);
#define lrintf reference_lrintf
'''
driver = r'''int main(){
 reference_lrintf=reinterpret_cast<long(*)(float)>(GetProcAddress(LoadLibraryW(L"ucrtbase.dll"),"lrintf"));if(!reference_lrintf)return 2;
 uint16_t lut[65536];uint64_t tested=0;int failed=0;
 const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
 const float black[]={0.0f,64.0f,256.0f,640.0f};const float scales[]={0.25f,1.0f,65535.0f/959.0f,65535.0f/3604.0f};
 for(int pattern=0;pattern<2;++pattern){for(unsigned i=0;i<65536;++i)lut[i]=pattern?uint16_t(uint64_t(i)*i/65535):uint16_t(i);
  for(int mode:modes){fesetround(mode);for(float z:black)for(float scale:scales)for(unsigned i=0;i<65536;++i){auto x=baseline_color(uint16_t(i),lut,z,scale);auto y=optimized_color(uint16_t(i),lut,z,scale);++tested;if(x!=y){if(failed++<5)printf("MISMATCH mode=%d i=%u old=%u new=%u\n",mode,i,x,y);}}}
 }
 const float unusual[]={INFINITY,-INFINITY,NAN,FLT_MAX,-FLT_MAX,1e-40f,-1e-40f};
 for(int mode:modes){fesetround(mode);for(float z:black)for(float scale:unusual)for(unsigned i:{0u,1u,1000u,65535u}){auto x=baseline_color(uint16_t(i),lut,z,scale);auto y=optimized_color(uint16_t(i),lut,z,scale);++tested;if(x!=y)++failed;}}
 fesetround(FE_TONEAREST);printf("ROUNDING_RESULT tested=%llu failures=%d\n",(unsigned long long)tested,failed);return failed?1:0;
}
'''
code = preamble + baseline.replace('dng_process_color16', 'baseline_color')
code += '\n#undef lrintf\n' + optimized.replace('dng_process_color16', 'optimized_color') + '\n' + driver
cpp = output / 'rounding.cpp'
exe = output / 'rounding.exe'
cpp.write_text(code, encoding='utf-8')
subprocess.run(['cl', '/nologo', '/O2', '/fp:strict', '/std:c++17', '/EHsc', '/MD',
                '/I' + str(sdk / 'include'), str(cpp), '/Fo' + str(output / 'rounding.obj'),
                '/Fe' + str(exe)], check=True)
run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
print(run.stdout, end='')
assert run.returncode == 0, run.stderr
result = re.search(r'ROUNDING_RESULT tested=(\d+) failures=(\d+)', run.stdout)
assert result and int(result[2]) == 0 and int(result[1]) == 8389056, run.stdout
report = {'cases': int(result[1]), 'failures': int(result[2]), 'rounding_modes': 4,
          'reference': 'ucrtbase.dll!lrintf', 'implementation': str(source / 'libavcodec/tiff.c')}
(output / 'tiff-rounding-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
