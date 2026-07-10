#!/usr/bin/env python3
from __future__ import annotations
import argparse, itertools, json, math, zipfile
from pathlib import Path
from collections import Counter
from typing import Tuple, Dict, List
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
Cell=Tuple[int,int]; Board=Dict[Cell,int]
DIRS=((1,0),(0,1),(1,-1))
def hd(a,b=(0,0)):
    dq=a[0]-b[0]; dr=a[1]-b[1]; return max(abs(dq),abs(dr),abs(dq+dr))
def add(a,d,k=1): return (a[0]+d[0]*k,a[1]+d[1]*k)
def xy(c): q,r=c; return (math.sqrt(3)*(q+r/2),1.5*r)
def cells(R):
    return [(q,r) for q in range(-R,R+1) for r in range(-R,R+1) if max(abs(q),abs(r),abs(q+r))<=R]
def rot(c): q,r=c; return (-r,q+r)
def refl(c): q,r=c; return (r,q)
def orbit(c):
    out=[]; x=c
    for _ in range(6): out += [x,refl(x)]; x=rot(x)
    return out
def canon(d): return sorted(set(orbit(d)))[0]
def segs(R,pad=2):
    C=set(cells(R+pad)); S=set()
    for c in C:
        for d in DIRS:
            s=tuple(add(c,d,k) for k in range(6))
            if all(x in C for x in s): S.add(s)
    return sorted(S)
def run_count(B,c,d,p):
    cnt=1; op=0
    for sg in (1,-1):
        for k in range(1,6):
            z=add(c,d,sg*k); v=B.get(z,0)
            if v==p: cnt+=1
            else:
                if v==0: op+=1
                break
    return cnt,op
def hval(B,move,p):
    NB=dict(B); NB[move[0]]=p; NB[move[1]]=p; v=0
    for c in move:
        for d in DIRS:
            m,_=run_count(NB,c,d,p); t,_=run_count(B,c,d,-p)
            v += m*m + (4 if t>=4 else 0)
    v += max(0,6-hd(move[0],move[1]))*.2
    return float(v)
def hitting(edges,maxk=3):
    edges=sorted(set(tuple(sorted(e)) for e in edges))
    if not edges: return 0
    U=sorted(set(x for e in edges for x in e))
    singles={e[0] for e in edges if len(e)==1}
    if len(singles)>maxk: return maxk+1
    for k in range(1,min(maxk,len(U))+1):
        for S in itertools.combinations(U,k):
            SS=set(S)
            if all(any(x in SS for x in e) for e in edges): return k
    return maxk+1
def hyper_edges_after(B,move,p,segments,level='proto'):
    NB=dict(B); NB[move[0]]=p; NB[move[1]]=p
    urgent=[]; proto=[]; terminal=0
    for s in segments:
        vals=[NB.get(c,0) for c in s]
        if any(v==-p for v in vals): continue
        em=tuple(c for c,v in zip(s,vals) if v==0); mine=6-len(em)
        if mine>=6: terminal+=1
        elif mine>=4 and 1<=len(em)<=2: urgent.append(tuple(sorted(em)))
        elif mine>=3 and 1<=len(em)<=3: proto.append(tuple(sorted(em)))
    return sorted(set(urgent)), sorted(set(proto)), terminal
def eval_move(B,move,p,segments):
    urgent, proto, terminal = hyper_edges_after(B,move,p,segments)
    tau_u=hitting(urgent); tau_p=hitting(proto)
    return dict(move=move, urgent=len(urgent), proto=len(proto), tau_urgent=tau_u, tau_proto=tau_p,
                pressure=max(0,tau_u-2), proto_pressure=max(0,tau_p-2), terminal=terminal,
                h=hval(B,move,p), shape=str(canon((move[1][0]-move[0][0],move[1][1]-move[0][1]))))
def candidate_moves(B,C,p,candR,spread,pref):
    E=[c for c in C if c not in B and hd(c)<=candR]
    arr=[]
    for i,a in enumerate(E):
        for b in E[i+1:]:
            if hd(a,b)<=spread: arr.append((hval(B,(a,b),p),a,b))
    arr.sort(reverse=True,key=lambda x:x[0])
    return [(a,b,h) for h,a,b in arr[:pref]]
def opening_pairs(R,spread):
    C=[c for c in cells(R) if c!=(0,0)]; P=[]
    for i,a in enumerate(C):
        for b in C[i+1:]:
            if hd(a,b)<=spread: P.append((a,b))
    return P
def opening_atlas(args):
    C=cells(args.radius); S=segs(args.radius)
    rows=[]
    for oid,wm in enumerate(opening_pairs(args.opening_radius,args.opening_spread)):
        B={(0,0):1, wm[0]:-1, wm[1]:-1}
        best=None
        for a,b,h in candidate_moves(B,C,1,args.candidate_radius,args.max_spread,args.prefilter):
            ev=eval_move(B,(a,b),1,S); ev['h']=h
            score=1000*ev['proto_pressure']+100*ev['pressure']+20*ev['tau_proto']+3*ev['proto']+ev['h']*0.01
            if best is None or score>best[0]: best=(score,ev)
        if best is None: continue
        ev=best[1]; cen=((wm[0][0]+wm[1][0])/2,(wm[0][1]+wm[1][1])/2); x,y=xy(cen)
        rows.append(dict(opening_id=oid,w1_q=wm[0][0],w1_r=wm[0][1],w2_q=wm[1][0],w2_r=wm[1][1],
                         x=x,y=y,min_radius=min(hd(wm[0]),hd(wm[1])),max_radius=max(hd(wm[0]),hd(wm[1])),spread=hd(wm[0],wm[1]),
                         shape=str(canon((wm[1][0]-wm[0][0],wm[1][1]-wm[0][1]))),
                         b1_q=ev['move'][0][0],b1_r=ev['move'][0][1],b2_q=ev['move'][1][0],b2_r=ev['move'][1][1],
                         black_shape=ev['shape'],proto=ev['proto'],tau_proto=ev['tau_proto'],proto_pressure=ev['proto_pressure'],
                         urgent=ev['urgent'],tau_urgent=ev['tau_urgent'],pressure=ev['pressure'],terminal=ev['terminal'],heuristic=ev['h']))
    return pd.DataFrame(rows)
def simple_multiway_from(B,args,tag):
    C=cells(args.radius); S=segs(args.radius)
    states=[dict(id=0,tag=tag,ply=0,B=B,side=1,score=0,mass=1,proto_edges=())]
    events=[]; front=[states[0]]; sid=1
    for ply in range(args.plies):
        new=[]
        for st in front:
            moves=[]
            for a,b,h in candidate_moves(st['B'],C,st['side'],args.candidate_radius,args.max_spread,args.branch_prefilter):
                ev=eval_move(st['B'],(a,b),st['side'],S); ev['h']=h
                ev['score']=2.5*ev['proto_pressure']+0.7*ev['tau_proto']+2*ev['pressure']+0.1*ev['proto']+0.1*np.tanh(h/30)
                moves.append(ev)
            moves.sort(key=lambda e:e['score'],reverse=True); chosen=moves[:args.branch]
            den=sum(math.exp(e['score']) for e in chosen) or 1
            for ev in chosen:
                NB=dict(st['B']); NB[ev['move'][0]]=st['side']; NB[ev['move'][1]]=st['side']
                mass=st['mass']*math.exp(ev['score'])/den
                state=dict(id=sid,tag=tag,ply=ply+1,B=NB,side=-st['side'],score=st['score']+ev['score'],mass=mass,proto_edges=())
                states.append(state); new.append(state)
                events.append(dict(tag=tag,ply=ply+1,from_state=st['id'],to_state=sid,side=st['side'],a=ev['move'][0],b=ev['move'][1],shape=ev['shape'],proto_pressure=ev['proto_pressure'],tau_proto=ev['tau_proto'],proto=ev['proto'],pressure=ev['pressure'],terminal=ev['terminal']))
                sid+=1
        new.sort(key=lambda s:s['mass']*(1+max(0,s['score'])),reverse=True); front=new[:args.beam]
    return states,events
def multiway_selected(atlas,args):
    safe=atlas.sort_values(['proto_pressure','tau_proto','proto','min_radius'],ascending=[True,True,True,False]).head(args.reps)
    risky=atlas.sort_values(['proto_pressure','tau_proto','proto'],ascending=False).head(args.reps)
    selected=pd.concat([safe.assign(tag='safe'),risky.assign(tag='risky')]).drop_duplicates(['w1_q','w1_r','w2_q','w2_r'])
    states=[]; events=[]; off=0
    for _,r in selected.iterrows():
        B={(0,0):1,(int(r.w1_q),int(r.w1_r)):-1,(int(r.w2_q),int(r.w2_r)):-1}
        ss,ee=simple_multiway_from(B,args,f"{r.tag}_{int(r.opening_id)}")
        for s in ss: s['id']+=off
        for e in ee: e['from_state']+=off; e['to_state']+=off
        off+=len(ss); states+=ss; events+=ee
    return selected,pd.DataFrame([{k:v for k,v in s.items() if k!='B'} for s in states]),pd.DataFrame(events)
def plots(atlas,selected,states,events,out):
    fig=out/'figures'; data=out/'data'; fig.mkdir(parents=True,exist_ok=True); data.mkdir(parents=True,exist_ok=True)
    atlas.to_csv(data/'opening_proto_atlas.csv',index=False); selected.to_csv(data/'selected_openings.csv',index=False); states.to_csv(data/'branchial_states.csv',index=False); events.to_csv(data/'multiway_events.csv',index=False)
    plt.figure(figsize=(7,6)); plt.scatter(atlas.x,atlas.y,c=atlas.proto_pressure+0.2*atlas.tau_proto,s=10+12*atlas.tau_proto); plt.gca().set_aspect('equal'); plt.xlabel('opening pair-center x'); plt.ylabel('opening pair-center y'); plt.title('Opening proto-pressure atlas'); plt.colorbar(label='proto-pressure + 0.2 tau'); plt.tight_layout(); plt.savefig(fig/'opening_proto_pressure_atlas.png',dpi=190); plt.close()
    rad=atlas.groupby('min_radius',as_index=False).agg(mean_proto_pressure=('proto_pressure','mean'),min_proto_pressure=('proto_pressure','min'),mean_tau_proto=('tau_proto','mean'),count=('opening_id','size'))
    rad.to_csv(data/'opening_radius_summary.csv',index=False)
    plt.figure(figsize=(7,5)); plt.plot(rad.min_radius,rad.mean_proto_pressure,marker='o',label='mean proto-pressure'); plt.plot(rad.min_radius,rad.min_proto_pressure,marker='o',label='best-case proto-pressure'); plt.plot(rad.min_radius,rad.mean_tau_proto,marker='o',label='mean proto tau'); plt.xlabel('minimum opening radius'); plt.ylabel('value'); plt.title('Opening annulus / breakaway curve'); plt.legend(); plt.tight_layout(); plt.savefig(fig/'opening_annulus_curve.png',dpi=190); plt.close()
    shape=atlas.groupby('shape',as_index=False).agg(mean_proto_pressure=('proto_pressure','mean'),min_proto_pressure=('proto_pressure','min'),mean_tau_proto=('tau_proto','mean'),count=('shape','size')).sort_values(['mean_proto_pressure','mean_tau_proto'],ascending=False)
    shape.to_csv(data/'opening_shape_proto_vulnerability.csv',index=False)
    top=shape.head(20); plt.figure(figsize=(8,5)); plt.bar(np.arange(len(top)),top.mean_proto_pressure); plt.xticks(np.arange(len(top)),top['shape'],rotation=45,ha='right'); plt.ylabel('mean proto-pressure'); plt.title('Opening shape vulnerability spectrum'); plt.tight_layout(); plt.savefig(fig/'opening_shape_vulnerability.png',dpi=190); plt.close()
    # Basic branchial scatter features from event stats by state parent accumulation absent; use ply/tag/mass coords synthetic from state id and ply.
    # Better: plot event shape/proto pressure over ply.
    evsum=events.groupby(['ply','shape'],as_index=False).agg(proto_pressure=('proto_pressure','sum'),count=('shape','size'),tau=('tau_proto','mean')).sort_values('proto_pressure',ascending=False)
    evsum.to_csv(data/'event_shape_attractor_spectrum.csv',index=False)
    top2=evsum.groupby('shape',as_index=False).agg(proto_pressure=('proto_pressure','sum'),count=('count','sum'),tau=('tau','mean')).sort_values('proto_pressure',ascending=False).head(20)
    plt.figure(figsize=(8,5)); plt.bar(np.arange(len(top2)),top2.proto_pressure); plt.xticks(np.arange(len(top2)),top2['shape'],rotation=45,ha='right'); plt.ylabel('multiway proto-pressure mass'); plt.title('Shape attractor spectrum in selected futures'); plt.tight_layout(); plt.savefig(fig/'shape_attractor_spectrum.png',dpi=190); plt.close()
    plt.figure(figsize=(7,5)); plt.scatter(events.proto,events.tau_proto,c=events.proto_pressure,s=20+20*events.terminal); plt.xlabel('proto-threat hyperedges'); plt.ylabel('proto hitting number tau'); plt.title('Multiway event proto-threat hypergraph geometry'); plt.colorbar(label='proto-pressure'); plt.tight_layout(); plt.savefig(fig/'event_proto_tau_scatter.png',dpi=190); plt.close()
    # Shape transition matrix
    shapes=sorted(events['shape'].unique()); idx={s:i for i,s in enumerate(shapes)}; M=np.zeros((len(shapes),len(shapes)))
    for tag,g in events.sort_values('ply').groupby('tag'):
        seq=g['shape'].tolist()
        for a,b in zip(seq,seq[1:]): M[idx[a],idx[b]]+=1
    P=np.divide(M,M.sum(axis=1,keepdims=True),out=np.zeros_like(M),where=M.sum(axis=1,keepdims=True)>0)
    pd.DataFrame(P,index=shapes,columns=shapes).to_csv(data/'shape_transition_matrix.csv')
    plt.figure(figsize=(8,7)); plt.imshow(P); plt.xticks(range(len(shapes)),shapes,rotation=90); plt.yticks(range(len(shapes)),shapes); plt.xlabel('next shape'); plt.ylabel('previous shape'); plt.title('D6 shape transition matrix for selected futures'); plt.colorbar(label='probability'); plt.tight_layout(); plt.savefig(fig/'shape_transition_matrix.png',dpi=190); plt.close()
    return rad,shape,top2
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='hexconnect6_opening_proto_atlas_out'); ap.add_argument('--radius',type=int,default=7); ap.add_argument('--opening-radius',type=int,default=5); ap.add_argument('--opening-spread',type=int,default=7); ap.add_argument('--candidate-radius',type=int,default=5); ap.add_argument('--max-spread',type=int,default=7); ap.add_argument('--prefilter',type=int,default=24); ap.add_argument('--plies',type=int,default=4); ap.add_argument('--beam',type=int,default=20); ap.add_argument('--branch',type=int,default=3); ap.add_argument('--branch-prefilter',type=int,default=20); ap.add_argument('--reps',type=int,default=5)
    args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    atlas=opening_atlas(args); selected,states,events=multiway_selected(atlas,args); rad,shape,top2=plots(atlas,selected,states,events,out)
    metrics=dict(parameters=vars(args),opening_candidates=len(atlas),max_proto_pressure=int(atlas.proto_pressure.max()),mean_proto_pressure=float(atlas.proto_pressure.mean()),best_annulus=rad.sort_values(['min_proto_pressure','mean_proto_pressure']).head(1).to_dict(orient='records')[0],safest_openings=atlas.sort_values(['proto_pressure','tau_proto','proto','min_radius'],ascending=[True,True,True,False]).head(12).to_dict(orient='records'),riskiest_openings=atlas.sort_values(['proto_pressure','tau_proto','proto'],ascending=False).head(12).to_dict(orient='records'),dominant_future_shapes=top2.head(10).to_dict(orient='records'),conjecture='Opening play is governed by proto-obligation rather than immediate threat. Good openings minimize latent three-stone line hypergraphs, while tactical futures renormalize toward a small D6 shape spectrum.')
    (out/'data'/'metrics.json').write_text(json.dumps(metrics,indent=2))
    (out/'README.md').write_text('# Hex Connect-6 opening proto-pressure atlas\n\nThis run measures latent/proto obligation hypergraphs after openings, then samples selected futures.\n')
    z=out.with_suffix('.zip')
    if z.exists(): z.unlink()
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as Z:
        for p in out.rglob('*'): Z.write(p,p.relative_to(out.parent))
        Z.write(Path(__file__),out.name+'/hexconnect6_opening_proto_atlas.py')
    print(json.dumps(metrics,indent=2)); print('wrote',z)
if __name__=='__main__': main()
