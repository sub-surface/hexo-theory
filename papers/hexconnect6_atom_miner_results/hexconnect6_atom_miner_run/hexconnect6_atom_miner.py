#!/usr/bin/env python3
"""
hexconnect6_atom_miner.py
Primitive forcing atom miner for infinite Hex Connect-6 in finite A2/Eisenstein windows.

Core quantity:
    pressure = max(0, tau(obligation_hypergraph) - 2)
where tau is exact hitting/transversal number and defender capacity is two stones.

This run is intentionally OOM-safe: it mines generated local forcing events, minimises
stones greedily, canonicalises under translation + D6, and compares bulk incidence
fingerprints against coarse boundary/Noether signatures.
"""
from __future__ import annotations
import argparse, itertools, json, math, random, zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Sequence
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

Cell=Tuple[int,int]; Board=Dict[Cell,int]
DIRS=((1,0),(0,1),(1,-1)); NEIGH=((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1))

def hd(a:Cell,b:Cell=(0,0))->int:
    dq=a[0]-b[0]; dr=a[1]-b[1]; return max(abs(dq),abs(dr),abs(dq+dr))
def add(a:Cell,d:Cell,k:int=1)->Cell: return (a[0]+d[0]*k,a[1]+d[1]*k)
def xy(c): q,r=c; return (math.sqrt(3)*(q+r/2),1.5*r)
def cellsR(R:int)->List[Cell]:
    return [(q,r) for q in range(-R,R+1) for r in range(-R,R+1) if max(abs(q),abs(r),abs(q+r))<=R]
def rot(c): q,r=c; return (-r,q+r)
def ref(c): q,r=c; return (r,q)
def trans(c,t):
    x=c
    for _ in range(t//2): x=rot(x)
    if t%2: x=ref(x)
    return x
def orbit(c): return [trans(c,t) for t in range(12)]
def cdelta(d): return sorted(set(orbit(d)))[0]
def shape(move):
    a,b=move; return str(cdelta((b[0]-a[0],b[1]-a[1])))
def segments(R:int,pad:int=2):
    C=set(cellsR(R+pad)); S=set()
    for c in C:
        for d in DIRS:
            seg=tuple(add(c,d,k) for k in range(6))
            if all(x in C for x in seg): S.add(seg)
    return sorted(S)

def obligations_after(board:Board, move:Tuple[Cell,Cell], player:int, segs):
    nb=dict(board); nb[move[0]]=player; nb[move[1]]=player
    exact=[]; proto=[]; terminal=[]
    for seg in segs:
        vals=[nb.get(c,0) for c in seg]
        if any(v==-player for v in vals): continue
        empt=tuple(c for c,v in zip(seg,vals) if v==0); mine=6-len(empt)
        if mine>=6: terminal.append(seg)
        elif mine>=4 and 1<=len(empt)<=2: exact.append(tuple(sorted(empt)))
        elif mine==3 and len(empt)==3: proto.append(tuple(sorted(empt)))
    return sorted(set(exact)), sorted(set(proto)), sorted(set(terminal))

def _simplify_edges(edges, chosen=frozenset()):
    rem=[]
    for e in edges:
        ee=frozenset(e)
        if ee & chosen:
            continue
        rem.append(ee)
    # remove duplicate and dominated edges: if A subset B, B is easier to hit once A hit, keep A
    rem=sorted(set(rem), key=lambda x:(len(x), sorted(x)))
    out=[]
    for e in rem:
        if not any(f <= e for f in out):
            out.append(e)
    return tuple(out)

def _can_hit(edges,k,memo=None):
    if memo is None: memo={}
    edges=_simplify_edges(edges)
    if not edges: return True
    if k<0: return False
    key=(edges,k)
    if key in memo: return memo[key]
    # forced singleton propagation
    forced=set()
    for e in edges:
        if len(e)==1: forced |= set(e)
    if forced:
        if len(forced)>k:
            memo[key]=False; return False
        new_edges=[e for e in edges if not (e & forced)]
        ans=_can_hit(new_edges,k-len(forced),memo)
        memo[key]=ans; return ans
    # lower bound: disjoint greedy matching
    disjoint=0; used=set()
    for e in sorted(edges, key=len):
        if not (set(e)&used):
            used |= set(e); disjoint += 1
            if disjoint>k:
                memo[key]=False; return False
    # branch on smallest edge
    e=min(edges, key=len)
    for v in e:
        if _can_hit([f for f in edges if v not in f], k-1, memo):
            memo[key]=True; return True
    memo[key]=False; return False

def tau(edges:Sequence[Tuple[Cell,...]], maxk:int=8)->int:
    if not edges: return 0
    for k in range(0,maxk+1):
        if _can_hit(edges,k): return k
    return maxk+1

def n_min_trans(edges,t,cap=2000):
    # Count for small vertex sets only; otherwise return cap as a sentinel.
    if not edges or t<=0: return 1
    U=sorted(set(c for e in edges for c in e))
    if len(U)>16 or t>5: return cap
    cnt=0
    for combo in itertools.combinations(U,t):
        S=set(combo)
        if all(any(c in S for c in e) for e in edges):
            cnt+=1
            if cnt>=cap: return cap
    return cnt


def eval_event(board,move,segs,target):
    exact,proto,term=obligations_after(board,move,1,segs)
    edges=exact if target=='exact' else proto
    t=tau(edges)
    return dict(exact=exact,proto=proto,terminal=term,edges=edges,tau=t,pressure=max(0,t-2))

def gen_segment(rng,C,segs,cont,R,target,source='segment'):
    shapes=[(1,0),(2,0),(3,0),(1,-1),(2,-1),(3,-1),(4,-2),(5,0),(6,-2)]
    base=rng.choice([c for c in C if hd(c)<=max(1,R-3)]); d=trans(rng.choice(shapes), rng.randrange(12))
    b=(base[0]+d[0],base[1]+d[1])
    if b not in set(C) or hd(b)>R: return None
    move=tuple(sorted([base,b])); board={}; chosen=[]
    nlines=rng.randint(3,6) if target=='exact' else rng.randint(4,7)
    pool=list(set(cont.get(move[0],[])+cont.get(move[1],[]))); rng.shuffle(pool)
    for seg in pool:
        if len(chosen)>=nlines: break
        if not any(c in seg for c in move): continue
        notmove=[c for c in seg if c not in move]
        es=rng.choice([1,2]) if target=='exact' else 3
        if len(notmove)<es: continue
        empt=tuple(sorted(rng.sample(notmove,es)))
        attackers=[c for c in seg if c not in empt and c not in move]
        if any(board.get(c,1)==-1 for c in attackers): continue
        for c in attackers: board[c]=1
        chosen.append(seg)
    if len(chosen)<3: return None
    protected=set(move); [protected.update(s) for s in chosen]
    cand=[c for c in C if c not in protected and c not in board and hd(c)<=R]
    rng.shuffle(cand)
    for c in cand[:rng.randint(0,5)]: board[c]=-1
    return board,move,target,source

def gen_rail(rng,C,segs,cont,R,target):
    axis=rng.choice(DIRS); start=rng.choice([c for c in C if hd(c)<=2])
    rail=[add(start,axis,k) for k in range(-2,5) if add(start,axis,k) in set(C)]
    if len(rail)<6: return gen_segment(rng,C,segs,cont,R,target,'segment')
    move=tuple(sorted(rng.sample(rail,2))); board={}
    for c in rail:
        if c not in move and rng.random()<0.78: board[c]=1
    pivot=rng.choice(rail); axis2=rng.choice([d for d in DIRS if d!=axis])
    branch=[add(pivot,axis2,k) for k in range(-2,4) if add(pivot,axis2,k) in set(C)]
    for c in branch:
        if c not in move and rng.random()<0.65: board[c]=1
    occ=set(board)|set(move); free=[c for c in C if c not in occ]
    rng.shuffle(free)
    for c in free[:rng.randint(0,4)]: board[c]=-1
    return board,move,target,'rail'

def gen_noisy(rng,C,segs,cont,R,target):
    x=gen_segment(rng,C,segs,cont,R,target,'noisy')
    if x is None: return None
    board,move,target,source=x; occ=set(board)|set(move); free=[c for c in C if c not in occ]
    rng.shuffle(free)
    for c in free[:rng.randint(1,8)]: board[c]=1 if rng.random()<.45 else -1
    return board,move,target,source

def minimise(board,move,target,t0,segs):
    board=dict(board)
    def ok(b):
        ev=eval_event(b,move,segs,target); return ev['tau']>=t0 and ev['pressure']>0
    changed=True
    while changed:
        changed=False
        for c in sorted(list(board), key=lambda x:(hd(x),x)):
            old=board.pop(c)
            if ok(board): changed=True
            else: board[c]=old
    cells=sorted(list(board), key=lambda x:(hd(x),x))
    for c1,c2 in list(itertools.combinations(cells,2)):
        if c1 not in board or c2 not in board: continue
        o1,o2=board.pop(c1),board.pop(c2)
        if not ok(board): board[c1]=o1; board[c2]=o2
    return board

def canon_embedded(board,move,edges):
    ovs=set(c for e in edges for c in e); reps=[]
    for t in range(12):
        items=[]
        for c,v in board.items():
            q,r=trans(c,t); items.append((q,r,'A' if v==1 else 'D'))
        for c in move:
            q,r=trans(c,t); items.append((q,r,'M'))
        for c in ovs:
            q,r=trans(c,t); items.append((q,r,'O'))
        best=None
        for oq,or_,_ in items:
            rep=tuple(sorted((q-oq,r-or_,role) for q,r,role in items))
            best=rep if best is None or rep<best else best
        reps.append(best)
    return str(min(reps))

def canon_edges(edges):
    if not edges: return '()'
    verts=sorted(set(c for e in edges for c in e)); reps=[]
    for t in range(12):
        for origin in [trans(v,t) for v in verts]:
            rep=[]
            for e in edges:
                rep.append(tuple(sorted((trans(c,t)[0]-origin[0], trans(c,t)[1]-origin[1]) for c in e)))
            reps.append(tuple(sorted(rep)))
    return str(min(reps))

def int_fp(edges,t):
    verts=sorted(set(c for e in edges for c in e)); deg=Counter()
    for e in edges:
        for c in e: deg[c]+=1
    inter=[]
    for i,e in enumerate(edges):
        S=set(e)
        for f in edges[i+1:]: inter.append(len(S&set(f)))
    return str((len(edges),len(verts),tuple(sorted(len(e) for e in edges)),tuple(sorted(deg.values(),reverse=True)),tuple(sorted(inter,reverse=True)),t,n_min_trans(edges,t)))

def size_sig(edges,t):
    verts=set(c for e in edges for c in e); return str((len(edges),len(verts),tuple(sorted(Counter(len(e) for e in edges).items())),t))

def noether(board,move,edges,coarse=False):
    ovs=set(c for e in edges for c in e); pts=[]
    for c,v in board.items(): pts.append((c,'A' if v==1 else 'D'))
    for c in move: pts.append((c,'M'))
    for c in ovs: pts.append((c,'O'))
    profs=[]
    for ax in range(3):
        ctr=defaultdict(Counter)
        for (q,r),role in pts:
            val=r if ax==0 else q if ax==1 else q+r
            ctr[val][role]+=1
        arr=[]
        for c in ctr.values():
            tup=(c['A'],c['D'],c['M'],c['O'])
            arr.append(tuple(min(2,x) for x in tup) if coarse else tup)
        profs.append(tuple(sorted(arr)))
    return str(tuple(sorted(profs)))

def boundary(board,move,edges,coarse=False):
    roles={}
    for c,v in board.items(): roles[c]='A' if v==1 else 'D'
    for c in move: roles[c]='M'
    for e in edges:
        for c in e: roles.setdefault(c,'O')
    occ=set(roles); bd=set()
    for c in occ:
        for d in NEIGH:
            n=add(c,d)
            if n not in occ: bd.add(n)
    flux=[]
    for b in bd:
        ctr=Counter()
        for d in NEIGH:
            role=roles.get(add(b,d))
            if role: ctr[role]+=1
        tup=(ctr['A'],ctr['D'],ctr['M'],ctr['O'])
        flux.append(tuple(min(2,x) for x in tup) if coarse else tup)
    return str(tuple(sorted(flux)))

def axis_support(edges):
    vals={'q':set(),'r':set(),'s':set()}
    for e in edges:
        for q,r in e: vals['q'].add(q); vals['r'].add(r); vals['s'].add(q+r)
    return sum(1 for v in vals.values() if len(v)>=2)

def family(row):
    pref='proto' if row['target']=='proto' else 'terminal' if row['terminal_count']>0 else 'exact'
    if '1:' in row['edge_size_hist']: core='singleton_fork'
    elif row['axis_support']>=3: core='triaxial_web'
    elif '(-1, 0)' in row['pair_shape'] or '(-2, 0)' in row['pair_shape']: core='rail_web'
    else: core='bridge_web'
    return f'{pref}_{core}'

def mine(args):
    rng=random.Random(args.seed); C=cellsR(args.radius); segs=segments(args.radius); cont=defaultdict(list)
    for s in segs:
        for c in s: cont[c].append(s)
    gens=[gen_segment,gen_rail,gen_noisy]; targets=['exact','proto'] if args.pressure=='both' else [args.pressure]
    rows=[]; attempts=0; positives=0
    while attempts<args.attempts and positives<args.target_events:
        attempts+=1; target=rng.choice(targets); ev=rng.choice(gens)(rng,C,segs,cont,args.radius,target)
        if ev is None: continue
        board,move,target,source=ev; e0=eval_event(board,move,segs,target)
        if e0['pressure']<=0: continue
        positives+=1; mb=minimise(board,move,target,e0['tau'],segs); e=eval_event(mb,move,segs,target)
        if e['pressure']<=0: continue
        edges=e['edges']; ovs=set(c for ed in edges for c in ed); roles=Counter('A' if v==1 else 'D' for v in mb.values())
        es=Counter(len(ed) for ed in edges); edge_hist=','.join(f'{k}:{v}' for k,v in sorted(es.items()))
        row=dict(raw_id=positives-1,source=source,target=target,tau=e['tau'],pressure=e['pressure'],initial_tau=e0['tau'],terminal_count=len(e['terminal']),num_edges=len(edges),num_vertices=len(ovs),min_transversals=n_min_trans(edges,e['tau']),attacker_stones=roles['A'],defender_stones=roles['D'],total_stones=len(mb)+2,pair_shape=shape(move),edge_size_hist=edge_hist,axis_support=axis_support(edges),canonical_template=canon_embedded(mb,move,edges),abstract_edge_signature=canon_edges(edges),integer_fingerprint=int_fp(edges,e['tau']),size_signature=size_sig(edges,e['tau']),noether_line_signature=noether(mb,move,edges,False),coarse_noether_signature=noether(mb,move,edges,True),boundary_flux_signature=boundary(mb,move,edges,False),coarse_boundary_flux_signature=boundary(mb,move,edges,True),board_json=json.dumps([[q,r,v] for (q,r),v in sorted(mb.items())]),move_json=json.dumps([[move[0][0],move[0][1]],[move[1][0],move[1][1]]]),edges_json=json.dumps([[[q,r] for q,r in ed] for ed in edges]))
        row['coarse_holographic_signature']=str((row['coarse_noether_signature'],row['coarse_boundary_flux_signature'],row['size_signature']))
        row['family']=family(row); rows.append(row)
    raw=pd.DataFrame(rows)
    atoms=[]
    for i,(sig,g) in enumerate(raw.groupby('canonical_template')):
        r=g.iloc[0].to_dict(); r['atom_id']=f'A{i:04d}'; r['frequency']=int(len(g)); r['source_count']=int(g['source'].nunique()); r['generator_sources']=','.join(sorted(g['source'].unique())); atoms.append(r)
    return raw,pd.DataFrame(atoms),attempts

def group_metrics(df,sigs):
    out=[]
    for sig in sigs:
        groups=df.groupby(sig,dropna=False); n=len(df); vals=[]
        for target in ['tau','pressure','family']:
            pure=sum((g[target].nunique()==1)*len(g) for _,g in groups)/n
            vals.append((target,pure))
        out.append(dict(signature=sig,rows=n,groups=int(groups.ngroups),compression_ratio=float(n/max(1,groups.ngroups)),mean_group_size=float(n/max(1,groups.ngroups)),max_group_size=int(max(len(g) for _,g in groups)),tau_purity=vals[0][1],pressure_purity=vals[1][1],family_purity=vals[2][1]))
    return pd.DataFrame(out)

def loo(df,sigs,targets):
    rows=[]
    for sig in sigs:
        gs={k:g for k,g in df.groupby(sig,dropna=False)}
        for target in targets:
            glob=df[target].mode().iloc[0]; corr=0; cov=0
            for idx,row in df.iterrows():
                rest=gs[row[sig]][gs[row[sig]].index!=idx]
                pred=rest[target].mode().iloc[0] if len(rest) else glob
                cov+=int(len(rest)>0); corr+=int(pred==row[target])
            rows.append(dict(signature=sig,target=target,accuracy=corr/len(df),covered_fraction=cov/len(df)))
    return pd.DataFrame(rows)

def twins(atoms):
    rows=[]
    for fp,g in atoms.groupby('integer_fingerprint'):
        if len(g)>1 and (g['coarse_boundary_flux_signature'].nunique()>1 or g['canonical_template'].nunique()>1):
            rows.append(dict(integer_fingerprint=fp,tau=int(g['tau'].iloc[0]),pressure=int(g['pressure'].iloc[0]),atoms=','.join(g['atom_id'].head(12)),n_atoms=len(g),n_boundaries=int(g['coarse_boundary_flux_signature'].nunique()),families=','.join(sorted(g['family'].unique()))))
    return pd.DataFrame(rows).sort_values(['n_atoms','n_boundaries'],ascending=False) if rows else pd.DataFrame()

def failures(atoms):
    rows=[]
    for sig,g in atoms.groupby('coarse_boundary_flux_signature'):
        if len(g)>1 and g['tau'].nunique()>1:
            rows.append(dict(coarse_boundary_flux_signature=sig,n_atoms=len(g),taus=','.join(map(str,sorted(g['tau'].unique()))),atoms=','.join(g['atom_id'].head(12)),families=','.join(sorted(g['family'].unique()))))
    return pd.DataFrame(rows).sort_values('n_atoms',ascending=False) if rows else pd.DataFrame()

def plot_all(raw,atoms,pred,fig):
    plt.figure(figsize=(7,5)); plt.scatter(raw['num_edges'],raw['tau'],s=18+12*raw['pressure']); plt.xlabel('obligation hyperedges'); plt.ylabel('tau'); plt.title('Obligation count vs transversal number'); plt.tight_layout(); plt.savefig(fig/'tau_vs_obligation_count.png',dpi=180); plt.close()
    freq=atoms['frequency'].sort_values(ascending=False).to_numpy(); plt.figure(figsize=(7,5)); plt.plot(np.arange(1,len(freq)+1),freq,marker='o'); plt.xlabel('atom rank'); plt.ylabel('frequency'); plt.title('Primitive atom frequency rank curve'); plt.tight_layout(); plt.savefig(fig/'primitive_atom_rank_frequency.png',dpi=180); plt.close()
    plt.figure(figsize=(7,5)); plt.scatter(atoms['total_stones'],atoms['tau'],s=18+9*atoms['frequency']); plt.xlabel('minimal template size'); plt.ylabel('tau'); plt.title('Pressure vs minimal atom size'); plt.tight_layout(); plt.savefig(fig/'pressure_vs_minimal_atom_size.png',dpi=180); plt.close()
    spec=atoms.groupby('pair_shape',as_index=False).agg(atoms=('atom_id','size'),frequency=('frequency','sum'),mean_tau=('tau','mean')).sort_values('frequency',ascending=False).head(20)
    plt.figure(figsize=(8.5,5)); x=np.arange(len(spec)); plt.bar(x,spec['frequency']); plt.xticks(x,spec['pair_shape'],rotation=45,ha='right'); plt.ylabel('frequency'); plt.title('D6 pair-shape spectrum of primitive atoms'); plt.tight_layout(); plt.savefig(fig/'template_shape_spectrum.png',dpi=180); plt.close()
    taup=pred[pred['target']=='tau'].sort_values('accuracy',ascending=False); plt.figure(figsize=(8.5,5)); x=np.arange(len(taup)); plt.bar(x,taup['accuracy']); plt.xticks(x,taup['signature'],rotation=45,ha='right'); plt.ylabel('LOO tau accuracy'); plt.title('Bulk vs boundary signatures for tau prediction'); plt.tight_layout(); plt.savefig(fig/'bulk_vs_boundary_tau_prediction.png',dpi=180); plt.close()
    # atom diagrams
    top=atoms.sort_values(['frequency','tau'],ascending=False).head(12); cols=4; rows=math.ceil(len(top)/cols); plt.figure(figsize=(cols*3.2, rows*3.1))
    for idx,(_,row) in enumerate(top.iterrows(),start=1):
        ax=plt.subplot(rows,cols,idx); board=json.loads(row['board_json']); move=[tuple(x) for x in json.loads(row['move_json'])]; edges=[[tuple(x) for x in e] for e in json.loads(row['edges_json'])]; ob=sorted(set(c for e in edges for c in e))
        for q,r,v in board:
            X,Y=xy((q,r)); ax.scatter([X],[Y],marker='o' if v==1 else 's',s=80)
        for c in move:
            X,Y=xy(c); ax.scatter([X],[Y],marker='*',s=160)
        for c in ob:
            X,Y=xy(c); ax.scatter([X],[Y],marker='x',s=80)
        ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([]); ax.set_title(f"{row['atom_id']} τ={row['tau']} f={row['frequency']}",fontsize=9)
    plt.suptitle('Top atoms: circles=A, squares=D, stars=move, x=obligation'); plt.tight_layout(); plt.savefig(fig/'top_primitive_atom_diagrams.png',dpi=180); plt.close()
    return spec

def main():
    p=argparse.ArgumentParser(); p.add_argument('--out',default='hexconnect6_atom_miner_out'); p.add_argument('--radius',type=int,default=6); p.add_argument('--attempts',type=int,default=9000); p.add_argument('--target-events',type=int,default=520); p.add_argument('--pressure',choices=['exact','proto','both'],default='both'); p.add_argument('--seed',type=int,default=260511); args=p.parse_args()
    out=Path(args.out); fig=out/'figures'; data=out/'data'; fig.mkdir(parents=True,exist_ok=True); data.mkdir(parents=True,exist_ok=True)
    raw,atoms,attempts=mine(args)
    if raw.empty: raise RuntimeError('No positive pressure events mined')
    raw.to_csv(data/'positive_pressure_events.csv',index=False); atoms.to_csv(data/'primitive_atoms.csv',index=False)
    sigs=['size_signature','integer_fingerprint','abstract_edge_signature','coarse_noether_signature','coarse_boundary_flux_signature','coarse_holographic_signature','family']
    gm=group_metrics(atoms,sigs); pr=loo(atoms,sigs,['tau','pressure','family']); tw=twins(atoms); fa=failures(atoms); spec=plot_all(raw,atoms,pr,fig)
    gm.to_csv(data/'bulk_boundary_group_metrics.csv',index=False); pr.to_csv(data/'bulk_boundary_prediction.csv',index=False); tw.to_csv(data/'holographic_twins.csv',index=False); fa.to_csv(data/'boundary_failures.csv',index=False); spec.to_csv(data/'template_shape_spectrum.csv',index=False)
    examples=[]
    for _,r in atoms.sort_values(['frequency','tau'],ascending=False).head(24).iterrows():
        examples.append(dict(atom_id=r['atom_id'],tau=int(r['tau']),pressure=int(r['pressure']),target=r['target'],family=r['family'],frequency=int(r['frequency']),pair_shape=r['pair_shape'],board=json.loads(r['board_json']),move=json.loads(r['move_json']),edges=json.loads(r['edges_json']),integer_fingerprint=r['integer_fingerprint']))
    (data/'atom_examples.json').write_text(json.dumps(examples,indent=2))
    summary=dict(parameters=vars(args),attempts=attempts,raw_positive_events=int(len(raw)),primitive_atoms=int(len(atoms)),exact_atoms=int((atoms['target']=='exact').sum()),proto_atoms=int((atoms['target']=='proto').sum()),max_tau=int(atoms['tau'].max()),max_pressure=int(atoms['pressure'].max()),top_families=atoms.groupby('family')['frequency'].sum().sort_values(ascending=False).head(10).to_dict(),top_shapes=spec.head(10).to_dict(orient='records'),group_metrics=gm.to_dict(orient='records'),prediction_metrics=pr.to_dict(orient='records'),holographic_twins=int(len(tw)),boundary_failures=int(len(fa)),interpretation='Primitive forcing is treated as a bulk incidence-algebra phenomenon; boundary/Noether signatures describe embeddings and families.')
    (data/'metrics.json').write_text(json.dumps(summary,indent=2))
    (out/'README.md').write_text('# Hex Connect-6 primitive forcing atom miner\n\npressure=max(0,tau(obligation_hypergraph)-2). See data/ and figures/.\n')
    zip_path=out.with_suffix('.zip')
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob('*'): z.write(pth,pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name)/'hexconnect6_atom_miner.py')
    print(json.dumps(summary,indent=2)); print(f'wrote {zip_path}')
if __name__=='__main__': main()
