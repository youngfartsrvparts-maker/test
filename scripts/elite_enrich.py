"""Build advanced transparent player profiles from completed nflverse seasons."""
import json, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data';V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
d=load('dashboard.json',{});hist=load('nflverse_history.json',{});current=int(d['league']['season']);seasons=[str(current-1),str(current-2),str(current-3)];weights={seasons[0]:.72,seasons[1]:.20,seasons[2]:.08}
for pid,p in d.get('players',{}).items():
 years=[]
 for s in seasons:
  z=(hist.get(s) or {}).get(pid)
  if not z:continue
  g=max(1,float(z.get('games') or 0));years.append({'season':int(s),'games':g,'ppg':float(z.get('ppg') or 0),'league_ppg':float(z.get('league_ppg') or 0),'targets_pg':float(z.get('targets') or 0)/g,'carries_pg':float(z.get('carries') or 0)/g,'receptions_pg':float(z.get('receptions') or 0)/g,'rush_yd_pg':float(z.get('rush_yd') or 0)/g,'rec_yd_pg':float(z.get('rec_yd') or 0)/g,'pass_yd_pg':float(z.get('pass_yd') or 0)/g,'fgm_pg':float(z.get('fgm_pg') or 0),'fga_pg':float(z.get('fga_pg') or 0),'xpm_pg':float(z.get('xpm_pg') or 0),'xpa_pg':float(z.get('xpa_pg') or 0),'fg50p_pg':float(z.get('fg50p_pg') or 0)})
 totalw=sum(weights.get(str(y['season']),0)*min(1,y['games']/8) for y in years)
 def wavg(k):return None if not totalw else sum(y[k]*weights.get(str(y['season']),0)*min(1,y['games']/8) for y in years)/totalw
 ppg=wavg('ppg');tgt=wavg('targets_pg');car=wavg('carries_pg');rec=wavg('receptions_pg');volume=(tgt or 0)+(car or 0);latest=next((y for y in years if y['season']==current-1),None);prev=next((y for y in years if y['season']==current-2),None);trend=latest['ppg']-prev['ppg'] if latest and prev else None;volatility=.24 if p.get('pos')=='QB' else .34 if p.get('pos') in ('WR','TE') else .30;floor=max(0,(ppg or 0)*(1-volatility));ceiling=(ppg or 0)*(1+volatility*1.55);evidence=min(100,round(totalw*100))
 p['elite_profile']={'historical_ppg':round(ppg,2) if ppg is not None else None,'targets_pg':round(tgt,2) if tgt is not None else None,'carries_pg':round(car,2) if car is not None else None,'receptions_pg':round(rec,2) if rec is not None else None,'opportunities_pg':round(volume,2),'historical_floor':round(floor,2) if ppg is not None else None,'historical_ceiling':round(ceiling,2) if ppg is not None else None,'yoy_ppg_change':round(trend,2) if trend is not None else None,'evidence':evidence,'seasons':years,'source':'nflverse completed seasons + Sleeper league scoring for K'}
d['elite_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'policy':'Historical evidence normalized by position. Kicker PPG uses league scoring when available.'};(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8');print(json.dumps({'profiles':sum(bool(p.get('elite_profile',{}).get('evidence')) for p in d['players'].values()),'kicker_profiles':sum(p.get('pos')=='K' and (p.get('elite_profile') or {}).get('historical_ppg') is not None for p in d['players'].values())},indent=2))