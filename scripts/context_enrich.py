"""NFL usage/schedule enrichment for Jagger GM.
Sleeper is league truth. nflverse supplies weekly NFL evidence.
Match by stable GSIS/player IDs first, then controlled name aliases. Audit every remaining 2025 gap.
"""
import csv, io, json, re, statistics, urllib.request, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/6.4 context engine','Accept':'text/csv,*/*'})
 with urllib.request.urlopen(req,timeout=45) as r:return r.read().decode('utf-8-sig',errors='replace')
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
def cleanid(s):return str(s or '').strip().replace(' ','')
def pct(vals,q):
 if not vals:return None
 a=sorted(vals);i=(len(a)-1)*q;lo=int(i);hi=min(len(a)-1,lo+1);f=i-lo;return a[lo]*(1-f)+a[hi]*f
def summary(rows):
 if not rows:return None
 vals=[float(x.get('ppr') or 0) for x in rows];g=len(rows)
 def avg(k):return round(sum(float(x.get(k) or 0) for x in rows)/g,2)
 return {'games':g,'ppg':round(sum(vals)/g,2),'median':round(statistics.median(vals),2),'p25':round(pct(vals,.25),2),'p75':round(pct(vals,.75),2),'p90':round(pct(vals,.90),2),'zero_rate':round(sum(1 for v in vals if v<1)/g,3),'targets_pg':avg('targets'),'receptions_pg':avg('receptions'),'carries_pg':avg('carries'),'rush_yd_pg':avg('rush_yd'),'rec_yd_pg':avg('rec_yd'),'pass_yd_pg':avg('pass_yd'),'opportunities_pg':round(sum(float(x.get('targets') or 0)+float(x.get('carries') or 0) for x in rows)/g,2)}
d=load('dashboard.json',{});players=d.get('players',{});rawplayers=load('players_nfl.json',{}) or {};current=int(d['league']['season'])
# Build several cross-source identity indexes. The dashboard intentionally stays compact, so retrieve Sleeper's raw IDs here.
names={};gsis={};aliases={};player_meta={}
for pid,p in players.items():
 rp=rawplayers.get(str(pid),{}) or {};player_meta[pid]=rp
 cand={p.get('name'),rp.get('full_name'),rp.get('search_full_name'),' '.join(x for x in [rp.get('first_name'),rp.get('last_name')] if x)}
 for x in cand:
  k=norm(x)
  if k:names.setdefault(k,[]).append(pid)
 gid=cleanid(rp.get('gsis_id'))
 if gid:gsis.setdefault(gid,[]).append(pid)
 # Extra safe aliases only when unique in Sleeper's player table.
 for x in [rp.get('search_first_name'),rp.get('first_name')]:
  if x and rp.get('last_name'):
   k=norm(str(x)+str(rp.get('last_name')))
   if k:aliases.setdefault(k,[]).append(pid)
def resolve(r):
 # nflverse weekly player_id is normally GSIS-style. Prefer this deterministic join.
 for key in ('player_id','gsis_id'):
  rid=cleanid(r.get(key))
  ids=gsis.get(rid,[]) if rid else []
  if len(ids)==1:return ids[0],'gsis'
 k=norm(r.get('player_display_name') or r.get('player_name') or r.get('name'))
 ids=names.get(k,[])
 if len(ids)==1:return ids[0],'name'
 ids=aliases.get(k,[])
 if len(ids)==1:return ids[0],'alias'
 return None,None
weekly={pid:{} for pid in players};health={};match_modes={}
for season in [current-3,current-2,current-1,current]:
 url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv';matched=0;modes={}
 try:
  for r in csv.DictReader(io.StringIO(get(url))):
   if r.get('season_type',r.get('game_type','REG'))!='REG':continue
   pid,mode=resolve(r)
   if not pid:continue
   try:w=int(float(r.get('week') or 0))
   except:continue
   if w<1:continue
   z={'week':w,'ppr':float(r.get('fantasy_points_ppr') or 0),'targets':float(r.get('targets') or 0),'receptions':float(r.get('receptions') or 0),'carries':float(r.get('carries') or 0),'rush_yd':float(r.get('rushing_yards') or 0),'rec_yd':float(r.get('receiving_yards') or 0),'pass_yd':float(r.get('passing_yards') or 0),'pass_td':float(r.get('passing_tds') or 0),'rush_td':float(r.get('rushing_tds') or 0),'rec_td':float(r.get('receiving_tds') or 0),'opponent':r.get('opponent_team'),'source_player_id':r.get('player_id')}
   weekly[pid].setdefault(str(season),[]).append(z);matched+=1;modes[mode]=modes.get(mode,0)+1
  health[str(season)]={'ok':True,'matched_rows':matched,'match_modes':modes,'url':url};match_modes[str(season)]=modes
 except Exception as e:health[str(season)]={'ok':False,'error':str(e)[:180],'url':url}
schedule=[];surl='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
try:
 for r in csv.DictReader(io.StringIO(get(surl))):
  if str(r.get('season'))!=str(current) or r.get('game_type')!='REG':continue
  def num(x):
   try:return float(x)
   except:return None
  schedule.append({'week':int(r['week']),'date':r.get('gameday'),'time':r.get('gametime'),'home':r.get('home_team'),'away':r.get('away_team'),'spread':num(r.get('spread_line')),'total':num(r.get('total_line'))})
 schedule.sort(key=lambda x:(x['week'],x.get('date') or ''));health['schedule']={'ok':len(schedule)>=200,'games':len(schedule),'url':surl}
except Exception as e:health['schedule']={'ok':False,'error':str(e)[:180],'url':surl}
for pid,p in players.items():
 seasons={s:sorted(rows,key=lambda x:x['week']) for s,rows in weekly.get(pid,{}).items()};summaries={s:summary(rows) for s,rows in seasons.items() if rows}
 hist=[]
 for s in [str(current-3),str(current-2),str(current-1)]:hist.extend(seasons.get(s,[]))
 vals=[x['ppr'] for x in hist];cur=seasons.get(str(current),[]);cur_sum=summaries.get(str(current))
 p['weekly_context']={'history_games':len(hist),'history_median':round(statistics.median(vals),2) if vals else None,'history_p25':round(pct(vals,.25),2) if vals else None,'history_p75':round(pct(vals,.75),2) if vals else None,'history_p90':round(pct(vals,.90),2) if vals else None,'history_zero_rate':round(sum(1 for v in vals if v<1)/len(vals),3) if vals else None,'season_summary':summaries,'season_games':seasons,'current_games':cur,'current_ppg':cur_sum.get('ppg') if cur_sum else None,'current_targets_pg':cur_sum.get('targets_pg') if cur_sum else None,'current_carries_pg':cur_sum.get('carries_pg') if cur_sum else None,'current_opportunities_pg':cur_sum.get('opportunities_pg') if cur_sum else None}
 # Backfill historical prior from the same exact weekly matches so a miss in another enrichment script cannot erase useful history.
 weights={str(current-1):.72,str(current-2):.20,str(current-3):.08};num=den=0
 for s,w in weights.items():
  z=summaries.get(s)
  if z:
   sample=min(1,z['games']/8);num+=z['ppg']*w*sample;den+=w*sample
 if den:p['historical_ppg_prior']=round(num/den,2);p['history_confidence']=round(min(1,den),2)
 team=p.get('team');games=[]
 for g in schedule:
  if g['week']<int(d['league']['week']) or team not in (g['home'],g['away']):continue
  opp=g['away'] if g['home']==team else g['home'];is_home=g['home']==team;implied=None
  if g.get('total') is not None and g.get('spread') is not None:implied=round(g['total']/2+((-g['spread'] if is_home else g['spread'])/2),1)
  games.append({**g,'opponent':opp,'home_game':is_home,'implied_team_points':implied})
  if len(games)>=5:break
 p['nfl_schedule']=games
# Produce a concrete audit instead of silently treating all blanks as data failures.
y25=str(current-1);missing=[]
for pid,p in players.items():
 if p.get('pos') not in ('QB','RB','WR','TE','K') or not p.get('team'):continue
 if (p.get('weekly_context') or {}).get('season_summary',{}).get(y25):continue
 rp=player_meta.get(pid,{}) or {};rookie_year=(rp.get('metadata') or {}).get('rookie_year');reason='no nflverse 2025 weekly match'
 if str(rookie_year)==str(current):reason='2026 rookie — correctly has no 2025 NFL stats'
 missing.append({'player_id':pid,'name':p.get('name'),'pos':p.get('pos'),'team':p.get('team'),'sleeper_gsis_id':cleanid(rp.get('gsis_id')) or None,'rookie_year':rookie_year,'reason':reason})
audit={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'season':y25,'missing_count':len(missing),'players':missing,'match_modes':match_modes}
(OUT/'missing_2025_stats.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
d['context_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'health':health,'missing_2025_count':len(missing),'policy':'Stable GSIS ID match first, unique Sleeper name aliases second; exact nflverse weekly distributions retained per season. Remaining gaps are audited, never silently invented.'}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'players_with_2025_weekly':sum(bool((p.get('weekly_context') or {}).get('season_summary',{}).get(y25)) for p in players.values()),'missing_2025':len(missing),'match_modes':match_modes,'schedule_games':len(schedule)},indent=2))