"""Jagger GM v4 context enrichment.
Sleeper remains authoritative for league state. nflverse supplies completed historical and current NFL usage/stat context.
"""
import csv, io, json, re, statistics, urllib.request, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/4.0 context engine','Accept':'text/csv,*/*'})
 with urllib.request.urlopen(req,timeout=40) as r:return r.read().decode('utf-8-sig',errors='replace')
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
def pct(vals,q):
 if not vals:return None
 a=sorted(vals);i=(len(a)-1)*q;lo=int(i);hi=min(len(a)-1,lo+1);f=i-lo;return a[lo]*(1-f)+a[hi]*f
d=load('dashboard.json',{}); players=d.get('players',{}); current=int(d['league']['season']); names={}
for pid,p in players.items():names.setdefault(norm(p.get('name')),[]).append(pid)
weekly_by_player={pid:{} for pid in players}; health={}
for season in [current-3,current-2,current-1,current]:
 url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'; matched=0
 try:
  for r in csv.DictReader(io.StringIO(get(url))):
   if r.get('season_type',r.get('game_type','REG'))!='REG':continue
   matches=names.get(norm(r.get('player_display_name') or r.get('player_name')),[])
   if len(matches)!=1:continue
   pid=matches[0]
   try:w=int(float(r.get('week') or 0))
   except:continue
   if w<1:continue
   z={'week':w,'ppr':float(r.get('fantasy_points_ppr') or 0),'targets':float(r.get('targets') or 0),'receptions':float(r.get('receptions') or 0),'carries':float(r.get('carries') or 0),'rush_yd':float(r.get('rushing_yards') or 0),'rec_yd':float(r.get('receiving_yards') or 0),'pass_yd':float(r.get('passing_yards') or 0),'pass_td':float(r.get('passing_tds') or 0),'rush_td':float(r.get('rushing_tds') or 0),'rec_td':float(r.get('receiving_tds') or 0),'opponent':r.get('opponent_team')}
   weekly_by_player[pid].setdefault(str(season),[]).append(z);matched+=1
  health[str(season)]={'ok':True,'matched_rows':matched,'url':url}
 except Exception as e:health[str(season)]={'ok':False,'error':str(e)[:180],'url':url}
# Schedule context from nflverse games dataset (current season only)
schedule=[]; surl='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
try:
 for r in csv.DictReader(io.StringIO(get(surl))):
  if str(r.get('season'))!=str(current) or r.get('game_type')!='REG':continue
  def num(x):
   try:return float(x)
   except:return None
  schedule.append({'week':int(r['week']),'date':r.get('gameday'),'time':r.get('gametime'),'home':r.get('home_team'),'away':r.get('away_team'),'spread':num(r.get('spread_line')),'total':num(r.get('total_line'))})
 schedule.sort(key=lambda x:(x['week'],x.get('date') or ''));health['schedule']={'ok':len(schedule)>=200,'games':len(schedule),'url':surl}
except Exception as e:health['schedule']={'ok':False,'error':str(e)[:180],'url':surl}
# Attach distributions and current-season usage. Current games progressively outweigh history in the JS model.
for pid,p in players.items():
 seasons=weekly_by_player.get(pid,{})
 hist=[]
 for s in [str(current-3),str(current-2),str(current-1)]:hist.extend(seasons.get(s,[]))
 cur=sorted(seasons.get(str(current),[]),key=lambda x:x['week'])
 vals=[x['ppr'] for x in hist]
 p['weekly_context']={'history_games':len(hist),'history_median':round(statistics.median(vals),2) if vals else None,'history_p25':round(pct(vals,.25),2) if vals else None,'history_p75':round(pct(vals,.75),2) if vals else None,'history_p90':round(pct(vals,.90),2) if vals else None,'history_zero_rate':round(sum(1 for v in vals if v<1)/len(vals),3) if vals else None,'current_games':cur,'current_ppg':round(sum(x['ppr'] for x in cur)/len(cur),2) if cur else None,'current_targets_pg':round(sum(x['targets'] for x in cur)/len(cur),2) if cur else None,'current_carries_pg':round(sum(x['carries'] for x in cur)/len(cur),2) if cur else None,'current_opportunities_pg':round(sum(x['targets']+x['carries'] for x in cur)/len(cur),2) if cur else None}
 # next five NFL opponents + betting context where available
 team=p.get('team');games=[]
 for g in schedule:
  if g['week']<int(d['league']['week']) or team not in (g['home'],g['away']):continue
  opp=g['away'] if g['home']==team else g['home'];is_home=g['home']==team
  implied=None
  if g.get('total') is not None and g.get('spread') is not None:
   # nflverse spread_line is home-team spread in many files; treat only as context, not exact projection.
   implied=round(g['total']/2 + ((-g['spread'] if is_home else g['spread'])/2),1)
  games.append({**g,'opponent':opp,'home_game':is_home,'implied_team_points':implied})
  if len(games)>=5:break
 p['nfl_schedule']=games
d['context_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'health':health,'policy':'Sleeper league state + nflverse NFL usage/schedule context. Betting lines are contextual only.'}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'players_with_history_distribution':sum(1 for p in players.values() if p.get('weekly_context',{}).get('history_games',0)>0),'players_with_current_games':sum(1 for p in players.values() if p.get('weekly_context',{}).get('current_games')),'schedule_games':len(schedule),'health':health},indent=2))