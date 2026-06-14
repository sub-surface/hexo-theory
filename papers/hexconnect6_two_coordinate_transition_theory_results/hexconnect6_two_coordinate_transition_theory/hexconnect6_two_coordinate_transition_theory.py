#!/usr/bin/env python3
"""
hexconnect6_two_coordinate_transition_theory.py

Two-coordinate transition theory for Hex Connect-6 forcing atoms.

Input: boundary-transition-lab results zip/folder with data/transition_events.csv.
Output: model comparison, mutual-information synergy, terminal-lift states, figures.

Core test:
    (bulk atom coordinate, Noether/boundary field coordinate) -> next motif family / pressure class

Bulk coordinate: family, symbol, pressure class, size/integer fingerprint.
Field coordinate: Noether phase, boundary phase.
"""

from pathlib import Path
from collections import Counter
import argparse, zipfile, shutil, json, math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def extract_if_zip(path, work):
    path = Path(path)
    if path.is_file() and path.suffix == ".zip":
        out = work / f"extract_{path.stem}"
        if out.exists(): shutil.rmtree(out)
        out.mkdir(parents=True)
        with zipfile.ZipFile(path) as z: z.extractall(out)
        return out
    return path

def find_file(root, name):
    hits = list(Path(root).rglob(name))
    if not hits: raise FileNotFoundError(name)
    hits.sort(key=lambda p: (0 if p.parent.name == "data" else 1, len(str(p))))
    return hits[0]

def entropy(vals):
    c = Counter(vals); n = sum(c.values())
    return -sum((v/n)*math.log((v/n)+1e-12) for v in c.values()) if n else 0.0

def mi(x, y):
    n = len(x)
    cx, cy, cxy = Counter(x), Counter(y), Counter(zip(x,y))
    s = 0.0
    for (a,b), v in cxy.items():
        pxy, px, py = v/n, cx[a]/n, cy[b]/n
        s += pxy * math.log((pxy/(px*py))+1e-12)
    return s

def key(df, cols):
    if isinstance(cols, str): return df[cols].astype(str)
    return df[list(cols)].astype(str).agg(" | ".join, axis=1)

def loo_group(df, key_col, target):
    glob = df[target].mode().iloc[0]
    groups = {k:g for k,g in df.groupby(key_col, dropna=False)}
    correct = covered = 0
    for i, row in df.iterrows():
        g = groups[row[key_col]]
        rest = g[g.index != i]
        pred = rest[target].mode().iloc[0] if len(rest) else glob
        covered += int(len(rest) > 0)
        correct += int(pred == row[target])
    pure = sum(int(g[target].nunique()==1)*len(g) for g in groups.values()) / max(1, len(df))
    return correct/len(df), covered/len(df), len(groups), len(df)/max(1,len(groups)), pure

def logo_group(df, key_col, target):
    correct = total = 0
    for gid, test in df.groupby("game_id"):
        train = df[df.game_id != gid]
        glob = train[target].mode().iloc[0]
        lookup = {k:g[target].mode().iloc[0] for k,g in train.groupby(key_col, dropna=False)}
        for _, row in test.iterrows():
            correct += int(lookup.get(row[key_col], glob) == row[target])
            total += 1
    return correct/max(1,total)

def backoff_one(train, row, levels, target, min_count=2):
    glob = train[target].mode().iloc[0]
    for cols in levels:
        m = pd.Series(True, index=train.index)
        for c in cols:
            m &= train[c].astype(str).eq(str(row[c]))
        sub = train[m]
        if len(sub) >= min_count:
            return sub[target].mode().iloc[0], "+".join(cols)
    return glob, "global"

def loo_backoff(df, levels, target):
    correct = 0; used = Counter()
    for i, row in df.iterrows():
        pred, lvl = backoff_one(df.drop(index=i), row, levels, target)
        correct += int(pred == row[target]); used[lvl] += 1
    return correct/len(df), dict(used)

def logo_backoff(df, levels, target):
    correct = total = 0; used = Counter()
    for gid, test in df.groupby("game_id"):
        train = df[df.game_id != gid]
        for _, row in test.iterrows():
            pred, lvl = backoff_one(train, row, levels, target)
            correct += int(pred == row[target]); total += 1; used[lvl] += 1
    return correct/max(1,total), dict(used)

def run(df, out):
    out = Path(out); (out/"data").mkdir(parents=True, exist_ok=True); (out/"figures").mkdir(parents=True, exist_ok=True)
    targets = ["next_family", "next_pressure_class", "next_kind"]
    coords = {
        "bulk_family": ["family"], "bulk_symbol": ["symbol"], "bulk_pressure": ["pressure_class"],
        "bulk_integer": ["integer_fingerprint"], "bulk_size": ["size_signature"],
        "field_noether": ["noether_phase"], "field_boundary": ["boundary_phase"],
        "geom_kind": ["kind"], "geom_shape": ["shape"],
        "two_family_noether": ["family","noether_phase"],
        "two_family_boundary": ["family","boundary_phase"],
        "two_symbol_noether": ["symbol","noether_phase"],
        "two_pressure_noether": ["pressure_class","noether_phase"],
        "two_kind_noether": ["kind","noether_phase"],
        "two_shape_boundary": ["shape","boundary_phase"],
    }
    rows=[]; tmp=df.copy()
    for name, cols in coords.items():
        kc=f"key_{name}"; tmp[kc]=key(tmp, cols)
        for target in targets:
            loo, cov, groups, comp, pure = loo_group(tmp, kc, target)
            rows.append({"model":name,"type":"two-coordinate" if name.startswith("two_") else "field" if name.startswith("field_") else "bulk" if name.startswith("bulk_") else "geometry","target":target,"loo_accuracy":loo,"logo_accuracy":logo_group(tmp,kc,target),"covered":cov,"groups":groups,"compression":comp,"purity":pure,"columns":"+".join(cols)})
    backoffs = {
        "backoff_family_noether": [["family","noether_phase"],["family"],["noether_phase"]],
        "backoff_symbol_noether": [["symbol","noether_phase"],["symbol"],["noether_phase"],["family"]],
        "backoff_pressure_noether": [["pressure_class","noether_phase"],["pressure_class"],["noether_phase"],["family"]],
        "backoff_kind_noether": [["kind","noether_phase"],["kind"],["noether_phase"],["family"]],
        "backoff_family_boundary": [["family","boundary_phase"],["family"],["boundary_phase"]],
    }
    for name, levels in backoffs.items():
        for target in targets:
            loo, used = loo_backoff(df, levels, target)
            logo, usedg = logo_backoff(df, levels, target)
            rows.append({"model":name,"type":"two-coordinate-backoff","target":target,"loo_accuracy":loo,"logo_accuracy":logo,"covered":None,"groups":None,"compression":None,"purity":None,"columns":" > ".join("+".join(x) for x in levels),"levels_used":json.dumps(used),"levels_used_logo":json.dumps(usedg)})
    comp=pd.DataFrame(rows)
    comp.to_csv(out/"data"/"two_coordinate_model_comparison.csv", index=False)

    # MI synergy
    syn=[]
    pairs=[("family","noether_phase"),("family","boundary_phase"),("symbol","noether_phase"),("pressure_class","noether_phase"),("kind","noether_phase"),("shape","boundary_phase")]
    for target in targets:
        y=df[target].astype(str).tolist(); hy=entropy(y)
        for b,f in pairs:
            B=df[b].astype(str).tolist(); F=df[f].astype(str).tolist(); BF=(df[b].astype(str)+" | "+df[f].astype(str)).tolist()
            ib, iff, ibf = mi(B,y), mi(F,y), mi(BF,y)
            syn.append({"target":target,"bulk":b,"field":f,"NMI_bulk":ib/hy if hy else 0,"NMI_field":iff/hy if hy else 0,"NMI_pair":ibf/hy if hy else 0,"synergy_over_best":ibf-max(ib,iff),"synergy_over_sum":ibf-ib-iff})
    syn=pd.DataFrame(syn).sort_values(["target","synergy_over_best"], ascending=[True,False])
    syn.to_csv(out/"data"/"two_coordinate_synergy.csv", index=False)

    # lift
    gf=(df.next_pressure_class=="terminal").mean()
    gforce=df.next_pressure_class.isin(["forcing1","forcing2+","terminal"]).mean()
    lift=[]
    for b,f in pairs:
        br=df.groupby(b).next_pressure_class.apply(lambda x:(x=="terminal").mean()).to_dict()
        fr=df.groupby(f).next_pressure_class.apply(lambda x:(x=="terminal").mean()).to_dict()
        for (bv,fv),g in df.groupby([b,f]):
            if len(g)<3: continue
            pt=float((g.next_pressure_class=="terminal").mean())
            pf=float(g.next_pressure_class.isin(["forcing1","forcing2+","terminal"]).mean())
            lift.append({"bulk":b,"field":f,"bulk_value":bv,"field_value":fv,"count":len(g),"p_next_terminal":pt,"p_next_forcing":pf,"terminal_lift_global":pt-gf,"forcing_lift_global":pf-gforce,"terminal_lift_over_bulk":pt-br.get(bv,gf),"terminal_lift_over_field":pt-fr.get(fv,gf),"dominant_next_family":g.next_family.mode().iloc[0]})
    lift=pd.DataFrame(lift).sort_values(["terminal_lift_global","p_next_forcing","count"], ascending=False)
    lift.to_csv(out/"data"/"two_coordinate_lift_states.csv", index=False)

    # figures
    for target in targets:
        sub=comp[comp.target==target].sort_values("logo_accuracy", ascending=False).head(14)
        plt.figure(figsize=(10,5.5)); x=np.arange(len(sub))
        plt.bar(x-.18, sub.loo_accuracy, width=.36, label="LOO")
        plt.bar(x+.18, sub.logo_accuracy, width=.36, label="leave-game-out")
        plt.xticks(x, sub.model, rotation=45, ha="right"); plt.ylabel("accuracy"); plt.title(f"Two-coordinate models predicting {target}"); plt.legend(); plt.tight_layout(); plt.savefig(out/"figures"/f"model_comparison_{target}.png", dpi=190); plt.close()
    top=lift.head(18); labels=top.bulk_value.astype(str).str.slice(0,16)+"\n"+top.field_value.astype(str).str.slice(0,18)
    plt.figure(figsize=(12,6)); x=np.arange(len(top)); plt.bar(x,top.p_next_terminal,label="P(next terminal)"); plt.plot(x,top.p_next_forcing,marker="o",label="P(next forcing)"); plt.xticks(x,labels,rotation=70,ha="right"); plt.ylabel("probability"); plt.title("High-lift two-coordinate states"); plt.legend(); plt.tight_layout(); plt.savefig(out/"figures"/"two_coordinate_terminal_lift.png", dpi=190); plt.close()
    piv=df.pivot_table(index="family", columns="noether_phase", values="next_pressure_class", aggfunc=lambda x:(x=="terminal").mean(), fill_value=0)
    rows=df.family.value_counts().head(12).index; cols=df.noether_phase.value_counts().head(8).index; piv=piv.reindex(index=rows, columns=cols, fill_value=0)
    plt.figure(figsize=(10,7)); plt.imshow(piv.values, aspect="auto"); plt.yticks(np.arange(len(piv.index)),piv.index); plt.xticks(np.arange(len(piv.columns)),piv.columns,rotation=90); plt.colorbar(label="P(next terminal)"); plt.title("P(next terminal) over (family, Noether phase)"); plt.tight_layout(); plt.savefig(out/"figures"/"family_noether_terminal_matrix.png", dpi=190); plt.close()
    return comp, syn, lift

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="hexconnect6_two_coordinate_transition_theory_out")
    a=p.parse_args()
    out=Path(a.out); work=out/"_work"; work.mkdir(parents=True, exist_ok=True)
    root=extract_if_zip(a.input, work)
    df=pd.read_csv(find_file(root,"transition_events.csv")).dropna(subset=["next_family","next_pressure_class","next_kind"]).reset_index(drop=True)
    comp,syn,lift=run(df,out)
    metrics={"rows":int(len(df)),"games":int(df.game_id.nunique()),"best_next_family":comp[comp.target=="next_family"].sort_values("logo_accuracy",ascending=False).head(8).to_dict(orient="records"),"best_next_pressure_class":comp[comp.target=="next_pressure_class"].sort_values("logo_accuracy",ascending=False).head(8).to_dict(orient="records"),"best_synergy":syn.sort_values("synergy_over_best",ascending=False).head(12).to_dict(orient="records"),"top_lift_states":lift.head(12).to_dict(orient="records")}
    with open(out/"data"/"metrics.json","w") as f: json.dump(metrics,f,indent=2)
    (out/"README.md").write_text("# Two-coordinate transition theory\n\nTests (bulk atom, field phase) as a motif-flow coordinate.\n")
    zpath=out.with_suffix(".zip")
    if zpath.exists(): zpath.unlink()
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob("*"):
            if "_work" in pth.parts: continue
            z.write(pth, pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name)/"hexconnect6_two_coordinate_transition_theory.py")
    print(json.dumps(metrics, indent=2))
    print(f"wrote {zpath}")
if __name__=="__main__": main()
