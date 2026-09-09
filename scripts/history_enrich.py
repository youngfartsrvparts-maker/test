"""Attach validated Sleeper historical production to the Jagger GM snapshot.
Uses Sleeper only for fantasy/player data. Historical seasons become priors, never current-year stats.
"""
import json, time, urllib.request, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'; BASE='https://api.sleeper.com'

def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d

def getj(url):
 err=None
 for a in range(2):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/3.4 personal fantasy manager','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
  except Exception as e:
   err=e
   if a==0:time.sleep(.4)
 raise RuntimeError(str(err)[:180])

def valid(x):return isinstance(x,dict) and sum(1 for v in x.values() if isinstance(v,dict) and v.get('pts_ppr') is not None)>=20

d=load('dashboard.json',{})
if not d:raise SystemExit('dashboard missing')
current=int(d['league']['season']); seasons=[current-1,current-2,current-3]
history={}; health={}
for season in seasons:
 s=str(season); year={}; good=0
 # Prefer season totals when Sleeper exposes them.
 urls=[f'{BASE}/stats/nfl/regular/{s}']
 totals=None
 for url in urls:
  try:
   x=getj(url)
   if valid(x):totals=x;break
  except Exception as e:health[s]={'ok':False,'note':str(e)[:160]}
 if totals:
  for pid,row in totals.items():
   if not isinstance(row,dict) or row.get('pts_ppr') is None:continue
   games=row.get('gp') or row.get('games') or row.get('gms_active') or 17
   try:games=max(1,float(games))
   except:games=17
   year[str(pid)]={'pts_ppr':float(row.get('pts_ppr') or 0),'games':games,'ppg':float(row.get('pts_ppr') or 0)/games,'targets':row.get('rec_tgt'),'receptions':row.get('rec'),'carries':row.get('rush_att'),'rush_yd':row.get('rush_yd'),'rec_yd':row.get('rec_yd'),'pass_yd':row.get('pass_yd'),'pass_td':row.get('pass_td'),'rush_td':row.get('rush_td'),'rec_td':row.get('rec_td'),'source':'Sleeper season totals'}
  good=len(year);health[s]={'ok':True,'players':good,'mode':'season'}
 else:
  # Fall back to validated weekly Sleeper stats and aggregate them ourselves.
  for w in range(1,19):
   url=f'{BASE}/stats/nfl/regular/{s}/{w}'
   try:x=getj(url)
   except:continue
   if not valid(x):continue
   for pid,row in x.items():
    if not isinstance(row,dict) or row.get('pts_ppr') is None:continue
    z=year.setdefault(str(pid),{'pts_ppr':0.0,'games':0,'targets':0.0,'receptions':0.0,'carries':0.0,'rush_yd':0.0,'rec_yd':0.0,'pass_yd':0.0,'pass_td':0.0,'rush_td':0.0,'rec_td':0.0,'source':'Sleeper weekly aggregate'})
    z['pts_ppr']+=float(row.get('pts_ppr') or 0);z['games']+=1
    for out,key in [('targets','rec_tgt'),('receptions','rec'),('carries','rush_att'),('rush_yd','rush_yd'),('rec_yd','rec_yd'),('pass_yd','pass_yd'),('pass_td','pass_td'),('rush_td','rush_td'),('rec_td','rec_td')]:
     z[out]+=float(row.get(key) or 0)
  for z in year.values():z['ppg']=z['pts_ppr']/max(1,z['games'])
  good=len(year);health[s]={'ok':good>=20,'players':good,'mode':'weekly aggregate' if good else 'unavailable'}
 history[s]=year
# Attach a transparent recency-weighted prior. 2025 matters most before Week 1; older seasons decay sharply.
weights={str(current-1):0.72,str(current-2):0.20,str(current-3):0.08}
for pid,p in d.get('players',{}).items():
 years={s:history.get(s,{}).get(pid) for s in map(str,seasons) if history.get(s,{}).get(pid)};p['history']=years
 num=den=0.0
 for s,row in years.items():
  w=weights.get(s,0)
  # Do not treat tiny samples like full-season evidence.
  sample=min(1.0,float(row.get('games') or 0)/8.0)
  num+=float(row.get('ppg') or 0)*w*sample;den+=w*sample
 p['historical_ppg_prior']=round(num/den,2) if den else None
 p['history_confidence']=round(min(1,den),2)
d['history_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'seasons':seasons,'health':health,'policy':'Sleeper only; historical PPR is a prior, never labeled as current-year production.','weights':weights}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');(OUT/'history_sleeper.json').write_text(json.dumps(history,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'history':health,'players_with_prior':sum(1 for p in d.get('players',{}).values() if p.get('historical_ppg_prior') is not None)},indent=2))
