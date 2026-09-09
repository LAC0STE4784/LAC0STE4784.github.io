#!/usr/bin/env python3
"""GPL-3.0-only. Build an isolated patched pipeline9, refusing unknown inputs.
Default adds correctness fixes and an immutable cache scoped to each Anneal run.
Conflict feedback is OFF unless SCROLLREADING_CONFLICT_FEEDBACK=1.
SCROLLREADING_VALIDATE_SCORE=1 compares every cached scalar with the old scorer.
Geometry must remain immutable while an Anneal call runs. No global cache.
"""
from pathlib import Path
import sys,re,shutil,hashlib,difflib,argparse
sys.path.insert(0,str(Path(__file__).parent/'src'))
from apply_geometry_fixes import patch,git_blob
EXPECTED={'common_types.cpp':'94fa6483b722ea35ea396713ab1286a6baeb42ba','anneal.cpp':'608966480161a1e827be8db8076cd3fac6399e0a','common_types.h':'728ac1f4558ab1cfd309f521eec9402765c1b7cf','makefile':'85ef7a928848102a41741ec995ea9a280b0e1e49'}
HELPER=r'''
#include "exact_score_cache.h"
#include <cstdlib>
#include <cstring>
#include <stdexcept>
static float CheckedCachedScore(const ExactScoreCache &cache, AlignmentMap *am,
 std::map<int,Patch> *patches,
 std::unordered_map<int,std::tuple<float,float,float>> &positions,
 std::vector<int> &order,std::set<int> &involved) {
 const char *f=std::getenv("SCROLLREADING_CONFLICT_FEEDBACK");
 const bool feedback=f && std::strcmp(f,"1")==0;
 const float result=cache.score(positions,order,30,feedback?&involved:nullptr).score;
 const char *v=std::getenv("SCROLLREADING_VALIDATE_SCORE");
 if(v && std::strcmp(v,"1")==0) {
  std::set<int> colours,ignored;std::set<std::pair<int,int>> exclusions;
  const float reference=ScorePlacementAreaAndIncon(am,patches,positions,order,
    colours,exclusions,ignored,30,10,false,false,false);
  uint32_t a,b;std::memcpy(&a,&result,4);std::memcpy(&b,&reference,4);
  if(a!=b)throw std::runtime_error("Cached scoring differs from original; validation failed");
  std::printf("CACHE_VALIDATION_PASS patches=%zu\n",order.size());
 }
 return result;
}
'''
def prepare(source:Path,dest:Path,cache:bool=True):
 for n,h in EXPECTED.items():
  if git_blob((source/n).read_bytes())!=h:raise RuntimeError('Unpinned input '+n)
 if dest.exists():raise RuntimeError('Refusing existing output')
 shutil.copytree(source,dest,ignore=shutil.ignore_patterns('*.o','simpaper10'))
 if (source.parent/'LICENSE').exists():shutil.copyfile(source.parent/'LICENSE',dest/'LICENSE')
 original={n:(source/n).read_text() for n in EXPECTED}
 (dest/'common_types.cpp').write_text(patch(original['common_types.cpp']))
 h=original['common_types.h'].replace('#pragma once','#pragma once\n#include <cstdint>\n#include <string>\n#include <tuple>',1)
 (dest/'common_types.h').write_text(h)
 if cache:
  a=original['anneal.cpp'];a=a.replace('#include "PatchSpringSimulation.hpp"','#include "PatchSpringSimulation.hpp"\n'+HELPER,1)
  defs=0;calls=0
  def add_argument(m):
   nonlocal defs,calls
   definition=a[max(0,m.start()-6):m.start()].strip()=='float'
   if definition:defs+=1
   else:calls+=1
   return m.group(0)+('const ExactScoreCache &scoreCache, ' if definition else 'scoreCache, ')
  a=re.sub(r'\bEvaluateState(?:All)?\(',add_argument,a)
  if defs!=2 or calls<4:raise RuntimeError(f'Unexpected evaluation sites: {defs} definitions, {calls} calls')
  a,n=re.subn(r'(void Anneal(?:All)?\([^)]*\)\s*\{)',r'\1\n    const ExactScoreCache scoreCache(*patches);',a)
  if n!=2:raise RuntimeError('Expected two cache owners')
  pat=r'ScorePlacementAreaAndIncon\(am,\s*patches,\s*patchPositionsXYA,\s*(patchOrder|patchOrders\[componentIndex\]),\s*patchesToColour,\s*manualGoodRel,\s*patchesInvolved,\s*30,\s*10,\s*false,\s*false\)'
  a,n=re.subn(pat,r'CheckedCachedScore(scoreCache,am,patches,patchPositionsXYA,\1,patchesInvolved)',a)
  if n!=2:raise RuntimeError('Expected two scorer sites')
  (dest/'anneal.cpp').write_text(a)
  for name in ['exact_score_cache.h','exact_score_cache.cpp']:shutil.copyfile(Path(__file__).parent/'src'/name,dest/name)
  m=original['makefile'];m,n=re.subn(r'^(simpaper10: .*)$',r'\1 exact_score_cache.o',m,count=1,flags=re.M)
  if n!=1:raise RuntimeError('Target missing')
  m+='\nexact_score_cache.o: exact_score_cache.cpp exact_score_cache.h common_types.h\n\t$(CC) -c $< $(CFLAGS)\n'
  (dest/'makefile').write_text(m)
 diff=[]
 for name,before in original.items():
  after=(dest/name).read_text()
  diff.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/pipeline9/'+name,tofile='b/pipeline9/'+name))
 (dest.parent/(dest.name+'.patch')).write_text(''.join(diff))
 print('Prepared '+str(dest)+'; geometry repaired; cache='+str(cache)+'; conflict feedback opt-in')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--geometry-only',action='store_true');a=p.parse_args();prepare(a.source,a.output,not a.geometry_only)
