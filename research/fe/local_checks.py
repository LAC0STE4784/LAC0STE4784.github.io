"""Bounded local EVM checks; no RPC provider, real wallet, or broadcast path."""
from __future__ import annotations
import base64, hashlib, importlib.metadata, json, os, random, time, traceback
from pathlib import Path
from eth_tester import EthereumTester, PyEVMBackend
from eth_abi import encode
from eth_utils import keccak
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get('RESULTS_DIR', 'results')).resolve()
BIN = Path(os.environ.get('FE_OUTPUT', 'source/contracts/out')).resolve()
OUT.mkdir(parents=True, exist_ok=True)
SOLVED = list(range(1,16)) + [0]
UNSOLVED = list(range(1,14)) + [15,14,0]
ONE_MOVE = list(range(1,15)) + [0,15]
NAMES = ['Game','Game2D','GameEnum','GameBitboard','GameMonadic','GameNested','GameTrait']
DETAILS = []
SUMMARY = {'scope':'Fresh local EVM deployments ONLY. No live-chain claim or bytecode-match assertion.',
           'source_commit':'5137aa481073dfb67947fed0fa3843ae207362b6',
           'compiler':'26.1.0', 'tests':[], 'errors':[], 'started_at':time.time(),
           'versions':{p: importlib.metadata.version(p) for p in ['eth-tester','py-evm','eth-abi','cryptography']}}

def pack(board):
    assert sorted(board) == list(range(16))
    return sum(v << (4*i) for i,v in enumerate(board))

def adjacent(a,b):
    return abs(a//4-b//4)+abs(a%4-b%4)==1

def selector(sig):
    return keccak(text=sig)[:4]

def data(sig, types=(), values=()):
    return '0x'+(selector(sig)+encode(list(types),list(values))).hex()

def bytecode(name):
    p = BIN/(name+'.bin')
    raw=p.read_bytes()
    try:
        s=raw.decode().strip()
        if s.startswith('0x'): s=s[2:]
        if s and all(c in '0123456789abcdefABCDEF' for c in s):
            raw=bytes.fromhex(s)
    except UnicodeDecodeError:
        pass
    if not raw: raise ValueError('Empty compiler output: '+name)
    return raw

def deploy(t, account, name, types, vals):
    payload=bytecode(name)+encode(types,vals)
    h=t.send_transaction({'from':account,'gas':15000000,'data':'0x'+payload.hex()})
    r=t.get_transaction_receipt(h)
    if r['status'] != 1 or r['contract_address'] is None:
        raise RuntimeError('Local deployment failed: '+name)
    return r['contract_address']

def get(t, account, target, payload):
    x=t.call({'from':account,'to':target,'gas':2000000,'data':payload})
    return int(x,16)

def board(t, account, target, name):
    if name=='Game2D':
        return [get(t,account,target,data('getBoard(uint256,uint256)',('uint256','uint256'),divmod(i,4))) for i in range(16)]
    return [get(t,account,target,data('getBoard(uint256)',('uint256',),(i,))) for i in range(16)]

def move_data(name,index):
    if name=='Game2D':
        return data('moveField(uint256,uint256)',('uint256','uint256'),divmod(index,4))
    return data('moveField(uint256)',('uint256',),(index,))

def send(t, account, target, payload):
    h=t.send_transaction({'from':account,'to':target,'gas':2000000,'data':payload})
    return t.get_transaction_receipt(h)['status']==1

def legal_transition(before,after):
    if before==after: return True
    if sorted(after)!=list(range(16)): return False
    a=before.index(0); b=after.index(0)
    expected=before.copy(); expected[a],expected[b]=expected[b],expected[a]
    return adjacent(a,b) and after==expected

def seal():
    key=AESGCM.generate_key(bit_length=256); nonce=os.urandom(12)
    pub=serialization.load_pem_public_key((ROOT/'results_public.pem').read_bytes())
    wrapped=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    ct=AESGCM(key).encrypt(nonce,json.dumps(DETAILS,sort_keys=True).encode(),b'Fe-local-checks-v1')
    (OUT/'details.encrypted.json').write_text(json.dumps({'v':1,'key':base64.b64encode(wrapped).decode(),'nonce':base64.b64encode(nonce).decode(),'ciphertext':base64.b64encode(ct).decode()}))
    SUMMARY['elapsed_seconds']=time.time()-SUMMARY['started_at']
    (OUT/'summary.json').write_text(json.dumps(SUMMARY,indent=2))

for name in NAMES:
    rec={'name':name,'positive_controls':False,'differential_cases':0,'malformed_cases':0,'counterexamples':0,'apparent_solutions':0,'completed':False}
    started=time.monotonic()
    try:
        t=EthereumTester(PyEVMBackend())
        a=t.get_accounts()[0]
        validator=deploy(t,a,'DummyLockValidator',['bool'],[False])
        good=deploy(t,a,name,['address','uint256'],[validator,pack(SOLVED)])
        assert board(t,a,good,name)==SOLVED
        assert get(t,a,good,data('isSolved()'))==1
        one=deploy(t,a,name,['address','uint256'],[validator,pack(ONE_MOVE)])
        assert send(t,a,one,move_data(name,15))
        assert get(t,a,one,data('isSolved()'))==1
        rejecting=deploy(t,a,'DummyLockValidator',['bool'],[True])
        denied=deploy(t,a,name,['address','uint256'],[rejecting,pack(UNSOLVED)])
        assert not send(t,a,denied,move_data(name,14))
        assert board(t,a,denied,name)==UNSOLVED
        rec['positive_controls']=True
        target=deploy(t,a,name,['address','uint256'],[validator,pack(UNSOLVED)])
        before=board(t,a,target,name)
        assert before==UNSOLVED and get(t,a,target,data('isSolved()'))==0
        code=t.get_code(target)
        rec['runtime_sha256']=hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()
        rng=random.Random(29062026)
        history=[]
        for n in range(96):
            if time.monotonic()-started>40:
                rec['time_limit_hit']=True; break
            legal=[j for j in range(16) if adjacent(before.index(0),j)]
            choices=[0,1,3,4,7,11,14,15,16,17,666,2**64-1,2**64,2**128,2**255,2**256-1]
            idx=rng.choice(legal) if n%3 else rng.choice(choices)
            payload=move_data(name,idx)
            success=send(t,a,target,payload)
            expected=before.copy(); should=idx<16 and adjacent(before.index(0),idx)
            if should:
                e=before.index(0); expected[e],expected[idx]=expected[idx],expected[e]
            after=board(t,a,target,name)
            solved=get(t,a,target,data('isSolved()'))
            history.append(payload)
            rec['differential_cases']+=1
            if success!=should or after!=expected or solved!=(after==SOLVED):
                rec['counterexamples']+=1
                DETAILS.append({'kind':'differential','name':name,'before':before,'after':after,'index':idx,'success':success,'expected_success':should,'isSolved':solved,'history':history.copy()})
            if solved:
                rec['apparent_solutions']+=1
                DETAILS.append({'kind':'apparent_solution','name':name,'history':history.copy(),'board':after})
                break
            if not legal_transition(before,after):
                break
            before=after
        original=bytes.fromhex(move_data(name,14)[2:])
        malformed=[original[:n] for n in [0,1,2,3,4,5,10,20,34,35]]
        malformed += [original+b'\0'*32, b'\xff'*4+b'\0'*64, b'\0'*68]
        for raw in malformed:
            if time.monotonic()-started>48:
                rec['time_limit_hit']=True; break
            payload='0x'+raw.hex()
            success=send(t,a,target,payload)
            after=board(t,a,target,name)
            solved=get(t,a,target,data('isSolved()'))
            history.append(payload)
            rec['malformed_cases']+=1
            if (not success and after!=before) or not legal_transition(before,after) or solved!=(after==SOLVED):
                rec['counterexamples']+=1
                DETAILS.append({'kind':'malformed','name':name,'before':before,'after':after,'success':success,'isSolved':solved,'history':history.copy()})
            if solved:
                rec['apparent_solutions']+=1
                DETAILS.append({'kind':'apparent_solution','name':name,'history':history.copy(),'board':after})
                break
            before=after
        rec['completed']=rec['differential_cases']==96 and rec['malformed_cases']==13
    except Exception as exc:
        rec['execution_error']=type(exc).__name__
        DETAILS.append({'kind':'execution_error','name':name,'traceback':traceback.format_exc()})
        SUMMARY['errors'].append({'name':name,'type':type(exc).__name__})
    rec['elapsed_seconds']=time.monotonic()-started
    SUMMARY['tests'].append(rec)
    seal()
    print(json.dumps(rec),flush=True)
seal()
