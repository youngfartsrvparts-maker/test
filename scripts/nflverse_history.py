"""Historical production enrichment for Jagger GM.
Live league truth remains Sleeper. nflverse is used ONLY for completed historical NFL seasons.
"""
import csv, io, json, re, urllib.request, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/3.5 historical research','Accept':'text/csv,*/*'})
 with urllib.request.urlopen(req,timeout=40) as r:return r.read().decode('utf-8-sig',errors='replace')
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
d=load('dashboard.json',{});current=int(d['league']['season']); seasons=[current-1,current-2,current-3];players=d['players']; names={}
for pid,p in players.items():names.setdefault(norm(p['name']),[]).append(pid)
history={};health={}
for season in seasons:
 url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv';agg={}
 try:
  rows=csv.DictReader(io.StringIO(get(url)))
  for r in rows:
   if r.get('season_type',r.get('game_type','REG'))!='REG':continue
   name=r.get('player_display_name') or r.get('player_name'); matches=names.get(norm(name),[])
   if len(matches)!=1:continue
   pid=matches[0];z=agg.setdefault(pid,{'games':0,'pts_ppr':0.0,'targets':0.0,'receptions':0.0,'carries':0.0,'rush_yd':0.0,'rec_yd':0.0,'pass_yd':0.0,'pass_td':0.0,'rush_td':0.0,'rec_td':0.0})
   z['games']+=1
   for out,key in [('pts_ppr','fantasy_points_ppr'),('targets','targets'),('receptions','receptions'),('carries','carries'),('rush_yd','rushing_yards'),('rec_yd','receiving_yards'),('pass_yd','passing_yards'),('pass_td','passing_tds'),('rush_td','rushing_tds'),('rec_td','receiving_tds')]:
    try:z[out]+=float(r.get(key) or 0)
    except:pass
  for z in agg.values():z['ppg']=z['pts_ppr']/max(1,z['games'])
  health[str(season)]={'ok':len(agg)>=20,'players':len(agg),'url':url}
 except Exception as e:health[str(season)]={'ok':False,'players':0,'url':url,'error':str(e)[:180]}
 history[str(season)]=agg
weights={str(current-1):.72,str(current-2):.20,str(current-3):.08}
for pid,p in players.items():
 p['history']={s:history[s][pid] for s in history if pid in history[s]};num=den=0.0
 for s,z in p['history'].items():
  w=weights.get(s,0);sample=min(1,float(z['games'])/8);num+=z['ppg']*w*sample;den+=w*sample
 p['historical_ppg_prior']=round(num/den,2) if den else None;p['history_confidence']=round(min(1,den),2)
d['history_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'seasons':seasons,'health':health,'weights':weights,'source':'nflverse historical player stats','policy':'Historical completed-season evidence only. Sleeper remains authoritative for current rosters, availability, injuries, transactions, scoring and live league state.'}
d['source_policy']={'live_fantasy_data':'Sleeper','historical_player_stats':'nflverse','external_news':'headlines only'}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');(OUT/'nflverse_history.json').write_text(json.dumps(history,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'history':health,'players_with_prior':sum(p.get('historical_ppg_prior') is not None for p in players.values())},indent=2))