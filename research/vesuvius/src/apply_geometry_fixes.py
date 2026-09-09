#!/usr/bin/env python3
"""Produce a patched copy, never modify the source in place.
GPL-3.0 derivative patch for WillStevens/scrollreading.
Accepts the pinned complete upstream source, or the explicitly labelled retained
selected-method test fixture shipped in this bundle. Refuses all other inputs.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
from pathlib import Path

UPSTREAM_GIT_BLOB='94fa6483b722ea35ea396713ab1286a6baeb42ba'
ROOT=Path(__file__).resolve().parents[1]
RETAINED_SHA256='64a6bfbadc57e380e612fb6f11ede0b20bb7dd89956fc37522df73c4cb3cd97c'

def body_span(text: str, signature: str) -> tuple[int,int]:
    # Only called with unambiguous full method signatures below. Braces in the
    # target bodies' string literals/comments are absent in this pinned source.
    start=text.find(signature)
    if start<0: raise ValueError(f'Missing signature: {signature}')
    opening=text.index('{',start); level=1; end=opening+1
    while level and end<len(text):
        if text[end]=='{': level+=1
        elif text[end]=='}':level-=1
        end+=1
    if level: raise ValueError('Unbalanced source')
    return start,end

def change_function(text: str, signature: str, fn) -> str:
    a,b=body_span(text,signature)
    before=text[a:b];after=fn(before)
    if before==after: raise ValueError(f'No change in {signature}')
    return text[:a]+after+text[b:]

def replace_once(s: str, old: str, new: str) -> str:
    if s.count(old)!=1: raise ValueError(f'Expected one occurrence: {old!r}')
    return s.replace(old,new,1)

def patch(text: str) -> str:
    text=change_function(text,'void Patch::DestroyGrid(void)',lambda s: replace_once(s,
        'free(pointGrid[x-minux][y-minuy]);','delete pointGrid[x-minux][y-minuy];'))
    def destroy_interp(s: str) -> str:
        s=replace_once(s,'free(interpolatedPointGrid[x-minux][y-minuy]);',
                         'delete interpolatedPointGrid[x-minux*QUADMESH_SIZE][y-minuy*QUADMESH_SIZE];')
        s=replace_once(s,'free(interpolatedPointGrid[x-minux]);',
                         'free(interpolatedPointGrid[x-minux*QUADMESH_SIZE]);')
        return s
    text=change_function(text,'void Patch::DestroyInterpolatedGrid(void)',destroy_interp)
    for name in ('void Patch::Interpolate(void)','std::vector<patchPoint> Patch::InterpolateAtZ(int zcoord)'):
        text=change_function(text,name,lambda s:replace_once(s,
            'xs+1<maxux-minux-1','xs+1<maxux-minux+1'))
    import re
    def fix_floor(s: str) -> str:
        pattern=r'int p1x = \(int\)xd, p1y = \(int\)yd;\s*if \(xd<0\) p1x -= 1;\s*if \(yd<0\) p1y -= 1;'
        s,n=re.subn(pattern,'int p1x = static_cast<int>(std::floor(xd));\n        int p1y = static_cast<int>(std::floor(yd));\n        if (xd == maxux) p1x = maxux-1;\n        if (yd == maxuy) p1y = maxuy-1;',s)
        if n!=1: raise ValueError('Floor anchor not unique')
        return s
    text=change_function(text,'bool Patch::FindGlobalXY(std::tuple<float,float,float> patchPosition',fix_floor)
    text=change_function(text,'void Patch::BuildFromPoints(vector<patchPoint> &points, int patchNum)',
                        lambda s:replace_once(s,'abs(minuy>radius)','abs(minuy)>radius'))
    def fix_flip(s: str) -> str:
        anchor='int tmp;'
        added='''// An odd-width grid has an unswapped central column, whose local
    // x coordinates must also be reflected (not necessarily x == 0).
    if ((maxux-minux+1)%2 != 0) {
        const int mid=(maxux-minux)/2;
        for (int y=0; y<=maxuy-minuy; ++y)
            if (pointGrid[mid][y]) pointGrid[mid][y]->x=-pointGrid[mid][y]->x;
    }
    int tmp;'''
        return replace_once(s,anchor,added)
    text=change_function(text,'void Patch::Flip(void)',fix_flip)
    return text

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--allow-retained-fixture',action='store_true')
    args=ap.parse_args();raw=args.source.read_bytes()
    valid=git_blob(raw)==UPSTREAM_GIT_BLOB
    if args.allow_retained_fixture and hashlib.sha256(raw).hexdigest()==RETAINED_SHA256:valid=True
    if not valid:raise SystemExit('Refusing unknown/unpinned source revision')
    if args.output.exists():raise SystemExit('Refusing to overwrite existing output')
    before=raw.decode().replace('\r\n','\n');after=patch(before)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(after)
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
        fromfile='a/pipeline9/common_types.cpp',tofile='b/pipeline9/common_types.cpp'))
    args.output.with_suffix(args.output.suffix+'.patch').write_text(diff)
    print(f'Wrote patched COPY: {args.output}')
if __name__=='__main__':main()
