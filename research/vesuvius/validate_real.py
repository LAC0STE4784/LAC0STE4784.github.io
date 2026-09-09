#!/usr/bin/env python3
"""GPL-3.0-only. Bounded CPU validation; no dataset or coordinates are published.
Run only with permission to access/use the publicly supplied Scroll 4 data.
This downloads the 1.35 MB author sample, verifies its hash, and preserves 3D
float32 coordinates. TIF grid coordinates are recentered; original binary UV
origins/author placements are not provided in the archive and not assumed.
"""
from pathlib import Path
import sys,os,subprocess,json,hashlib,io,zipfile,urllib.request,re,shutil,time
import numpy as np,tifffile,blosc2
import integrate
R=Path(__file__).resolve().parent
W=Path(sys.argv[1]).resolve();S=Path(sys.argv[2]).resolve();W.mkdir(exist_ok=False)
DATA=W/'data';D=DATA/'patches';D.mkdir(parents=True)
RESULT={'data_source':'https://dl.ash2txt.org/community-uploads/will/scroll4_patches.zip','upstream_commit':'62cbc21bdafbe0313fee11d781d729256a14262e','tests':{},'builds':{},'smoke':{}}
def save(): (W/'summary.json').write_text(json.dumps(RESULT,indent=2));print('SUMMARY='+json.dumps(RESULT),flush=True)
def run(name,cmd,timeout=90,env=None,expected=0,public=True,cwd=None):
 t=time.perf_counter();p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=timeout,env=env,cwd=cwd)
 text=p.stdout+p.stderr;(W/(name+'.log')).write_text(text)
 RESULT['tests'][name]={'returncode':p.returncode,'seconds':time.perf_counter()-t,'log_sha256':hashlib.sha256(text.encode()).hexdigest()}
 print('RUN '+name+' exit='+str(p.returncode),flush=True)
 if public: print(text[-16000:],flush=True)
 if expected is not None and p.returncode!=expected:save();raise RuntimeError(name+' unexpected exit; see run log')
 return p
u=RESULT['data_source'];b=urllib.request.urlopen(u,timeout=60).read(16*1024*1024+1)
assert len(b)<=16*1024*1024
h=hashlib.sha256(b).hexdigest();assert h=='57143fc09d2fbc7ed547e3d7a00435521db37ca819d2843b3171f4b14e5d399e'
RESULT['archive_sha256']=h;z=zipfile.ZipFile(io.BytesIO(b));rows=[]
for name in sorted(z.namelist()):
 if not name.endswith('/meta.json'):continue
 prefix=name.rsplit('/',1)[0];ident=int(prefix.split('_')[1]);meta=json.loads(z.read(name));assert meta['scale']==[0.25,0.25]
 xyz=[tifffile.imread(io.BytesIO(z.read(prefix+'/'+k+'.tif'))) for k in 'xyz']
 assert all(a.dtype==np.float32 and a.shape==xyz[0].shape for a in xyz)
 valid=np.logical_and.reduce([np.isfinite(a)&(a>=0) for a in xyz]);nodata=np.logical_and.reduce([a==-1 for a in xyz])
 assert np.all(valid|nodata),'Unexpected mixed nodata: refusing silently altered input'
 yy,xx=np.nonzero(valid);hh,ww=valid.shape
 q=np.column_stack([xx-ww//2,yy-hh//2,*[a[valid] for a in xyz]]).astype('<f4')
 p=D/(prefix+'.bin');p.write_bytes(q.tobytes())
 for k in range(3):assert np.array_equal(q[:,k+2].view('u4'),xyz[k][valid].view('u4'))
 rows.append({'patch_id':ident,'points':len(q),'shape':[hh,ww],'bin_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
RESULT['patches']=rows;RESULT['points']=sum(x['points'] for x in rows)
RESULT['local_grid_origin']='TIFF integer grid recentered by floor(width/2), floor(height/2)'
RESULT['coordinates_bit_preserved']=True
print('DATA='+json.dumps({k:RESULT[k] for k in ['archive_sha256','points','patches','coordinates_bit_preserved']}),flush=True)
original=W/'original';shutil.copytree(S,original,ignore=shutil.ignore_patterns('*.o','simpaper10'))
fixed=W/'fixed';cached=W/'cached';integrate.prepare(S,fixed,False);integrate.prepare(S,cached,True)
# Cleanup-only control preserves original interpolation/query behaviour.
cleanup=(S/'common_types.cpp').read_text()
for old,new in [('free(pointGrid[x-minux][y-minuy]);','delete pointGrid[x-minux][y-minuy];'),('free(interpolatedPointGrid[x-minux][y-minuy]);','delete interpolatedPointGrid[x-minux*QUADMESH_SIZE][y-minuy*QUADMESH_SIZE];'),('free(interpolatedPointGrid[x-minux]);','free(interpolatedPointGrid[x-minux*QUADMESH_SIZE]);')]:
 assert cleanup.count(old)==1;cleanup=cleanup.replace(old,new)
(W/'common.cleanup.cpp').write_text(cleanup)
score=(S/'scoreplacement.cpp').read_text();diag='printf("pts:%d norms:%d score:%f scoreDec:%f\\n",ptsFound,normFound,score,scoreDecrease);';assert score.count(diag)==1
quiet=W/'score.quiet.cpp';quiet.write_text(score.replace(diag,'((void)0);'))
flags=['g++','-std=c++17','-include','cstdint','-ffp-contract=off','-I'+str(S),'-I'+str(R/'src')]
common=[R/'tests/real_geometry.cpp',R/'src/exact_score_cache.cpp',quiet]
san=['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
for n,source,opt in [('original_san',S/'common_types.cpp',san),('control_san',W/'common.cleanup.cpp',san),('fixed_san',fixed/'common_types.cpp',san),('fixed_fast',fixed/'common_types.cpp',['-O3'])]:
 run('compile_'+n,[*flags,*opt,*common,source,'-o',W/n],timeout=120)
env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:quarantine_size_mb=16')
p=run('real_original_destroy',[W/'original_san',D,'destroy'],env=env,expected=1)
assert 'alloc-dealloc-mismatch' in p.stderr
for variant in ['control','fixed']:
 for mode in ['interpolate','query']:
  p=run('real_'+variant+'_'+mode,[W/(variant+'_san'),D,mode],env=env)
  vals=[json.loads(x) for x in p.stdout.splitlines() if x.startswith('{')]
  RESULT[variant+'_'+mode]=vals[-1]
  if variant=='fixed':
   if mode=='interpolate':assert vals[-1]['total_actual']==vals[-1]['total_expected']
   else:assert vals[-1]['missing']==0 and vals[-1]['coordinate_mismatches']==0
run('real_fixed_sanitized_compare',[W/'fixed_san',D,'compare','0'],env=env,timeout=180)
bench=[]
for k in range(5):
 p=run('real_benchmark_'+str(k),[W/'fixed_fast',D,'compare',str(k)],timeout=90)
 bench.append(json.loads(p.stdout.splitlines()[-1]))
RESULT['real_geometry_generated_pose_benchmarks']=bench
# Complete builds, distinct from component tests.
broot=Path(blosc2.__file__).parent;binc=broot/'include';blib=broot/'lib'
cflags='-O2 -Wall -fopenmp -ffp-contract=off -include cstdint -I'+str(binc)
lflags='-L'+str(blib)+' -Wl,-rpath,'+str(blib)+' -lblosc2 -ltiff'
for label,source in [('original',original),('fixed',fixed),('cached',cached)]:
 param=source/'parameters.h';txt=param.read_text();txt,n=re.subn(r'^#define OUTPUT_DIR .*$', '#define OUTPUT_DIR "'+str(DATA)+'"',txt,flags=re.M);assert n==1;param.write_text(txt)
 p=run('full_build_'+label,['make','-C',source,'-j2','simpaper10','CFLAGS='+cflags,'LFLAGS='+lflags],timeout=240,expected=None)
 RESULT['builds'][label]={'exit':p.returncode}
 if p.returncode==0:RESULT['builds'][label]['binary_sha256']=hashlib.sha256((source/'simpaper10').read_bytes()).hexdigest()
 if p.returncode:save();raise RuntimeError('Complete build failed: '+label)
run('compile_native_aligner',[*flags,'-O2','-I'+str(binc),R/'tests/prepare_alignments.cpp',fixed/'common_types.o',fixed/'align_patches.o',fixed/'bigpatch.o','-L'+str(blib),'-Wl,-rpath,'+str(blib),'-lblosc2','-o',W/'prepare_alignments'],timeout=90)
p=run('native_alignments',[W/'prepare_alignments',D,DATA/'rel.csv'],timeout=90,public=False)
RESULT['native_alignment']=json.loads(next(x for x in reversed(p.stdout.splitlines()) if x.startswith('{')))
# Native command smoke tests use regenerated relations, not author placements.
# No ink inference, raw scan rendering, large downloads, or data publication.
for label,source in [('original',original),('fixed',fixed),('cached',cached)]:
 for args in [['l'],['c'],['n','2','1'],['nm','2','2','1']]:
  for filename in ['annealState.csv','annealState_out.csv','manualBadPatch.csv']:(DATA/filename).unlink(missing_ok=True)
  e=dict(os.environ,OMP_NUM_THREADS='2',SCROLLREADING_VALIDATE_SCORE='1')
  p=run('smoke_'+label+'_'+args[0],[source/'simpaper10',*args],timeout=90,env=e,expected=None,public=False,cwd=W)
  RESULT['smoke'][label+'_'+args[0]]={'exit':p.returncode,'validation_passes':p.stdout.count('CACHE_VALIDATION_PASS'),'stdout_bytes':len(p.stdout),'stderr_bytes':len(p.stderr)}
  if p.returncode:print('SMOKE FAILURE '+label+' '+args[0]+': '+p.stderr[-1000:],flush=True)
RESULT['scope']='Real Scroll 4 mesh components and bounded native command smoke tests; no full-scroll reconstruction or ink recovery claim.'
save()
