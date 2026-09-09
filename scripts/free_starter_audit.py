import json, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data';V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
d=load('dashboard.json',{}) or {};players=d.get('players',{});owned={str(pid) for t in d.get('teams',[]) for pid in t.get('players',[])}
rows=[]
for pid,p in players.items():
 if str(pid) in owned or p.get('pos') not in ('RB','WR') or not p.get('team') or p.get('active') is False:continue
 depth=p.get('depth') or p.get('depth_chart_order');ctx=p.get('current_context') or {};starter=False;why=[]
 try:
  if int(depth)==1:starter=True;why.append('Sleeper depth order 1')
 except:pass
 role=str(ctx.get('role') or '').lower()
 if ctx.get('active') and any(x in role for x in ('rb1','wr1','starter','lead','feature')):
  starter=True;why.append('current verified/news role: '+str(ctx.get('role')))
 if not starter:continue
 s=(p.get('weekly_context') or {}).get('season_summary',{}).get('2025') or {}
 rows.append({'player_id':str(pid),'name':p.get('name'),'pos':p.get('pos'),'team':p.get('team'),'depth':depth,'injury':p.get('injury'),'status':p.get('status'),'role':ctx.get('role') if ctx.get('active') else None,'role_confidence':ctx.get('confidence') if ctx.get('active') else None,'why_flagged':why,'ppg_2025':s.get('ppg') if s else p.get('historical_ppg_prior'),'floor_2025':s.get('p25'),'ceiling_2025':s.get('p90'),'targets_pg':s.get('targets_pg'),'carries_pg':s.get('carries_pg'),'adds_24h':p.get('adds'),'drops_24h':p.get('drops'),'next_game':(p.get('nfl_schedule') or [None])[0]})
rows.sort(key=lambda x:(0 if x['pos']=='RB' else 1,-(x.get('role_confidence') or 0),-(x.get('ppg_2025') or 0)))
out={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'league_id':d.get('league',{}).get('id'),'count':len(rows),'players':rows,'policy':'Free means not rostered by any team in this Sleeper league. Starter flag requires Sleeper depth order 1 or an active lead/starter role signal; external verification is still recommended before acting.'}
(OUT/'free_starters.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))