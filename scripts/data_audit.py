import json, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
d=load('dashboard.json',{}) or {}; ps=d.get('players',{}); teams=d.get('teams',[]); owned={str(x) for t in teams for x in t.get('players',[])}
active=[p for p in ps.values() if p.get('team') and p.get('active') is not False and p.get('pos') in ('QB','RB','WR','TE')]
def y25(p):return next((x for x in (p.get('elite_profile') or {}).get('seasons',[]) if int(x.get('season',0))==2025),None)
checks={
 'players_total':len(ps),'active_skill_players':len(active),'owned_players':len(owned),
 'historical_prior':sum(p.get('historical_ppg_prior') is not None for p in active),
 'elite_profile':sum((p.get('elite_profile') or {}).get('historical_ppg') is not None for p in active),
 '2025_detail':sum(y25(p) is not None for p in active),
 'weekly_distribution':sum((p.get('weekly_context') or {}).get('history_games',0)>0 for p in active),
 'schedule_next_game':sum(bool(p.get('nfl_schedule')) for p in active),
 'current_role_context':sum(bool((p.get('current_context') or {}).get('active')) for p in active)}
problems=[]
for pid in owned:
 p=ps.get(pid,{})
 if p.get('pos') in ('QB','RB','WR','TE') and p.get('historical_ppg_prior') is not None and y25(p) is None:
  problems.append({'type':'owned_history_detail_missing','player':p.get('name'),'id':pid,'historical_prior':p.get('historical_ppg_prior')})
for p in active:
 ep=p.get('elite_profile') or {}; s=y25(p)
 if s and ep.get('historical_ppg') is None:problems.append({'type':'elite_rollup_missing','player':p.get('name'),'id':p.get('id')})
audit={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'checks':checks,'problems':problems[:100],'problem_count':len(problems),'note':'2025 detail is sourced from elite_profile.seasons, generated from nflverse_history.json. UI should use this normalized layer instead of relying on legacy p.history.'}
(OUT/'data_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');d['data_audit']=audit;(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');(ROOT/'v3'/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8');print(json.dumps(audit,indent=2))