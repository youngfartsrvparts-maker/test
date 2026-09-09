"""Enrich Jagger GM dashboard with forward Sleeper scenarios.
Sleeper-only fantasy data. No third-party player/stat datasets.
Attempts future league matchups and weekly Sleeper projections; unavailable data is explicit.
"""
import json, urllib.request, time, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'
LEAGUE='1388315713940262912'; V1='https://api.sleeper.app/v1'; DATA='https://api.sleeper.com'

def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d

def getj(url):
 err=None
 for a in range(2):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/3.3 personal fantasy manager','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=18) as r:return json.load(r)
  except Exception as e:
   err=e
   if a==0:time.sleep(.35)
 raise RuntimeError(str(err)[:180])

def valid_proj(x):
 return isinstance(x,dict) and sum(1 for v in x.values() if isinstance(v,dict) and v.get('pts_ppr') is not None)>=20

d=load('dashboard.json',{})
if not d:raise SystemExit('dashboard missing')
season=str(d['league']['season']); current=int(d['league']['week']); maxweek=18
matchups={}; projection_weeks={}; health={}
for w in range(1,maxweek+1):
 try:
  m=getj(f'{V1}/league/{LEAGUE}/matchups/{w}')
  if isinstance(m,list) and m:matchups[str(w)]=m
 except Exception as e:
  if w==current:health['matchups_error']=str(e)[:160]
# Sleeper projections are optional/undocumented. Probe current + future weeks; never fabricate missing weeks.
for w in range(current,maxweek+1):
 url=f'{DATA}/projections/nfl/regular/{season}/{w}'
 try:
  p=getj(url)
  if valid_proj(p):projection_weeks[str(w)]={pid:row.get('pts_ppr') for pid,row in p.items() if isinstance(row,dict) and row.get('pts_ppr') is not None}
 except Exception as e:
  if w==current:health['projection_error']=str(e)[:160]
# Identify fantasy opponent roster per week for the user's roster.
my=int(d['my_team']); fantasy_schedule={}
for ws,rows in matchups.items():
 mine=next((x for x in rows if x.get('roster_id')==my),None)
 if not mine or mine.get('matchup_id') is None:continue
 opp=next((x for x in rows if x.get('matchup_id')==mine.get('matchup_id') and x.get('roster_id')!=my),None)
 fantasy_schedule[ws]={'my_roster_id':my,'opponent_roster_id':opp.get('roster_id') if opp else None,'matchup_id':mine.get('matchup_id')}
d['forecast']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'matchups':matchups,'fantasy_schedule':fantasy_schedule,'weekly_projections':projection_weeks,'projection_weeks_available':sorted(int(x) for x in projection_weeks),'projection_source':'Sleeper only','projection_note':'Point deltas use Sleeper projections only when a validated week is available. Otherwise the UI labels results as power deltas, not projected points.','health':health}
# Rebuild the embedded snapshot atomically.
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'matchup_weeks':len(matchups),'projection_weeks':sorted(projection_weeks),'fantasy_schedule_weeks':len(fantasy_schedule)},indent=2))
