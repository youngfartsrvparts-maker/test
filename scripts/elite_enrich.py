"""Build advanced, transparent player profiles from completed nflverse seasons.
Live league state remains Sleeper. This file derives historical evidence only.
"""
import json, math, statistics, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
d=load('dashboard.json',{}); hist=load('nflverse_history.json',{})
if not d or not hist:raise SystemExit('dashboard/history missing')
current=int(d['league']['season']); seasons=[str(current-1),str(current-2),str(current-3)]; weights={seasons[0]:.72,seasons[1]:.20,seasons[2]:.08}
for pid,p in d.get('players',{}).items():
 years=[]
 for s in seasons:
  z=(hist.get(s) or {}).get(pid)
  if not z:continue
  g=max(1,float(z.get('games') or 0));years.append({'season':int(s),'games':g,'ppg':float(z.get('ppg') or 0),'targets_pg':float(z.get('targets') or 0)/g,'carries_pg':float(z.get('carries') or 0)/g,'receptions_pg':float(z.get('receptions') or 0)/g,'rush_yd_pg':float(z.get('rush_yd') or 0)/g,'rec_yd_pg':float(z.get('rec_yd') or 0)/g,'pass_yd_pg':float(z.get('pass_yd') or 0)/g})
 totalw=sum(weights.get(str(y['season']),0)*min(1,y['games']/8) for y in years)
 def wavg(k):
  if not totalw:return None
  return sum(y[k]*weights.get(str(y['season']),0)*min(1,y['games']/8) for y in years)/totalw
 ppg=wavg('ppg');tgt=wavg('targets_pg');car=wavg('carries_pg');rec=wavg('receptions_pg');
 volume=(tgt or 0)+(car or 0)
 latest=next((y for y in years if y['season']==current-1),None);prev=next((y for y in years if y['season']==current-2),None)
 trend=None
 if latest and prev:trend=latest['ppg']-prev['ppg']
 # Heuristic bands are explicitly historical estimates, not current projections.
 volatility=0.24 if p.get('pos')=='QB' else 0.34 if p.get('pos') in ('WR','TE') else 0.30
 floor=max(0,(ppg or 0)*(1-volatility));ceiling=(ppg or 0)*(1+volatility*1.55)
 evidence=min(100,round(totalw*100))
 p['elite_profile']={'historical_ppg':round(ppg,2) if ppg is not None else None,'targets_pg':round(tgt,2) if tgt is not None else None,'carries_pg':round(car,2) if car is not None else None,'receptions_pg':round(rec,2) if rec is not None else None,'opportunities_pg':round(volume,2),'historical_floor':round(floor,2) if ppg is not None else None,'historical_ceiling':round(ceiling,2) if ppg is not None else None,'yoy_ppg_change':round(trend,2) if trend is not None else None,'evidence':evidence,'seasons':years,'source':'nflverse completed seasons'}
d['elite_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'policy':'Sleeper live league truth + nflverse completed-season evidence. Scores are decision aids, not guarantees.'}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'players_with_elite_profiles':sum(bool(p.get('elite_profile',{}).get('evidence')) for p in d['players'].values())},indent=2))