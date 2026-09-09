"""Historical production enrichment for Jagger GM.
Sleeper = league truth/scoring. nflverse = completed NFL statistical evidence.
This version uses the complete player_stats feed (offense + kicking) and calculates fantasy points with THIS Sleeper league's scoring settings.
"""
import csv, gzip, io, json, re, urllib.request, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
def raw(url):
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/6.0 historical research','Accept':'text/csv,*/*'})
 with urllib.request.urlopen(req,timeout=60) as r:return r.read()
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
def f(r,*keys):
 for k in keys:
  v=r.get(k)
  if v not in (None,'','NA','NaN'):
   try:return float(v)
   except:pass
 return 0.0
def league_points(r,sc):
 # exact scoring categories where nflverse supplies the matching box-score stat
 pts=0.0
 pairs=[
  ('pass_yd',('passing_yards',)),('pass_td',('passing_tds',)),('pass_int',('interceptions','passing_interceptions')),
  ('rush_yd',('rushing_yards',)),('rush_td',('rushing_tds',)),('rec',('receptions',)),('rec_yd',('receiving_yards',)),('rec_td',('receiving_tds',)),
  ('fum_lost',('fumbles_lost',)),('pass_2pt',('passing_2pt_conversions','passing_2pt')),('rush_2pt',('rushing_2pt_conversions','rushing_2pt')),('rec_2pt',('receiving_2pt_conversions','receiving_2pt')),
  ('xpm',('pat_made','extra_points_made','xp_made')),('xpmiss',('pat_missed','extra_points_missed','xp_missed')),
  ('fgm_0_19',('fg_made_0_19','field_goals_made_0_19')),('fgm_20_29',('fg_made_20_29','field_goals_made_20_29')),
  ('fgm_30_39',('fg_made_30_39','field_goals_made_30_39')),('fgm_40_49',('fg_made_40_49','field_goals_made_40_49')),
  ('fgm_50_59',('fg_made_50_59','field_goals_made_50_59')),('fgm_60p',('fg_made_60_','fg_made_60_plus','field_goals_made_60_plus'))]
 for sk,ks in pairs:pts+=float(sc.get(sk,0) or 0)*f(r,*ks)
 # If distance buckets are absent, fall back to 3 pts per FG made only for historical comparison.
 bucket=sum(f(r,*ks) for sk,ks in pairs if sk.startswith('fgm_'))
 fgm=f(r,'fg_made','field_goals_made')
 if fgm and not bucket:pts+=3.0*fgm
 # Sleeper has generic fgmiss=-1. Apply when attempts/makes available.
 fga=f(r,'fg_att','field_goal_attempts','field_goals_attempted')
 if fga and sc.get('fgmiss') is not None:pts+=float(sc.get('fgmiss',0) or 0)*max(0,fga-fgm)
 return pts

d=load('dashboard.json',{});current=int(d['league']['season']);seasons=[current-1,current-2,current-3];players=d['players'];sc=(load('league.json',{}) or {}).get('scoring_settings',{});names={}
for pid,p in players.items():names.setdefault(norm(p['name']),[]).append(pid)
history={str(s):{} for s in seasons};health={};source='https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv.gz'
try:
 blob=raw(source);text=gzip.decompress(blob).decode('utf-8-sig',errors='replace');rows=csv.DictReader(io.StringIO(text));matched={s:0 for s in seasons}
 for r in rows:
  try:season=int(float(r.get('season') or 0))
  except:continue
  if season not in seasons or r.get('season_type',r.get('game_type','REG')) not in ('REG','Regular','regular'):continue
  name=r.get('player_display_name') or r.get('player_name');matches=names.get(norm(name),[])
  if len(matches)!=1:continue
  pid=matches[0];p=players[pid];z=history[str(season)].setdefault(pid,{'games':0,'pts_ppr':0.0,'league_points':0.0,'targets':0.0,'receptions':0.0,'carries':0.0,'rush_yd':0.0,'rec_yd':0.0,'pass_yd':0.0,'pass_td':0.0,'rush_td':0.0,'rec_td':0.0,'fgm':0.0,'fga':0.0,'xpm':0.0,'xpa':0.0,'fg50p':0.0})
  z['games']+=1;matched[season]+=1
  z['pts_ppr']+=f(r,'fantasy_points_ppr');z['league_points']+=league_points(r,sc)
  for out,ks in [('targets',('targets',)),('receptions',('receptions',)),('carries',('carries','rushing_attempts')),('rush_yd',('rushing_yards',)),('rec_yd',('receiving_yards',)),('pass_yd',('passing_yards',)),('pass_td',('passing_tds',)),('rush_td',('rushing_tds',)),('rec_td',('receiving_tds',)),('fgm',('fg_made','field_goals_made')),('fga',('fg_att','field_goal_attempts','field_goals_attempted')),('xpm',('pat_made','extra_points_made','xp_made')),('xpa',('pat_att','extra_point_attempts','extra_points_attempted','xp_att')),('fg50p',('fg_made_50_59','field_goals_made_50_59','fg_made_60_plus','field_goals_made_60_plus'))]:z[out]+=f(r,*ks)
 for season in seasons:
  agg=history[str(season)]
  for pid,z in agg.items():
   g=max(1,z['games']);pos=players[pid].get('pos');lp=z['league_points']/g;std=z['pts_ppr']/g
   # K needs league-calculated kicking points because standard PPR is often 0 for kickers.
   z['ppg']=round(lp if pos=='K' and lp>0 else std,4);z['league_ppg']=round(lp,4)
   z['fgm_pg']=z['fgm']/g;z['fga_pg']=z['fga']/g;z['xpm_pg']=z['xpm']/g;z['xpa_pg']=z['xpa']/g;z['fg50p_pg']=z['fg50p']/g
  health[str(season)]={'ok':len(agg)>=20,'players':len(agg),'matched_rows':matched[season],'source':source}
except Exception as e:
 # Preserve old skill-player feed as a fallback rather than wiping history.
 for season in seasons:
  url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv';agg={}
  try:
   rows=csv.DictReader(io.StringIO(raw(url).decode('utf-8-sig',errors='replace')))
   for r in rows:
    if r.get('season_type',r.get('game_type','REG'))!='REG':continue
    matches=names.get(norm(r.get('player_display_name') or r.get('player_name')),[])
    if len(matches)!=1:continue
    pid=matches[0];z=agg.setdefault(pid,{'games':0,'pts_ppr':0.0,'league_points':0.0,'targets':0.0,'receptions':0.0,'carries':0.0,'rush_yd':0.0,'rec_yd':0.0,'pass_yd':0.0,'pass_td':0.0,'rush_td':0.0,'rec_td':0.0,'fgm':0.0,'fga':0.0,'xpm':0.0,'xpa':0.0,'fg50p':0.0});z['games']+=1
    for out,key in [('pts_ppr','fantasy_points_ppr'),('targets','targets'),('receptions','receptions'),('carries','carries'),('rush_yd','rushing_yards'),('rec_yd','receiving_yards'),('pass_yd','passing_yards'),('pass_td','passing_tds'),('rush_td','rushing_tds'),('rec_td','receiving_tds')]:z[out]+=f(r,key)
   for z in agg.values():z['ppg']=z['pts_ppr']/max(1,z['games'])
   history[str(season)]=agg;health[str(season)]={'ok':len(agg)>=20,'players':len(agg),'source':url,'fallback':True,'primary_error':str(e)[:120]}
  except Exception as ee:health[str(season)]={'ok':False,'players':0,'error':str(ee)[:180],'primary_error':str(e)[:120]}
weights={str(current-1):.72,str(current-2):.20,str(current-3):.08}
for pid,p in players.items():
 p['history']={s:history[s][pid] for s in history if pid in history[s]};num=den=0.0
 for s,z in p['history'].items():
  w=weights.get(s,0);sample=min(1,float(z['games'])/8);num+=float(z.get('ppg') or 0)*w*sample;den+=w*sample
 p['historical_ppg_prior']=round(num/den,2) if den else None;p['history_confidence']=round(min(1,den),2)
d['history_meta']={'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'seasons':seasons,'health':health,'weights':weights,'source':'nflverse complete player_stats','policy':'Completed-season evidence only. Kicker PPG uses this Sleeper league scoring when kicking fields are available.'};d['source_policy']={'live_fantasy_data':'Sleeper','historical_player_stats':'nflverse','external_news':'verified + headline context'}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');(OUT/'nflverse_history.json').write_text(json.dumps(history,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8');print(json.dumps({'history':health,'kickers_with_2025':sum(1 for p in players.values() if p.get('pos')=='K' and p.get('history',{}).get(str(current-1),{}).get('ppg',0)>0),'players_with_prior':sum(p.get('historical_ppg_prior') is not None for p in players.values())},indent=2))