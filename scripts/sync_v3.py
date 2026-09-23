"""Jagger GM v3 — Sleeper-first league intelligence collector.

Fantasy data source policy:
- Sleeper public API for league, rosters, users, matchups, transactions, draft, players, trends.
- Sleeper stats/projections endpoints for fantasy stats when they return usable current-season data.
- No nflverse/nfldata/GitHub NFL datasets.
- External news is headline-only context and never changes a player score automatically.
- Missing data stays missing; the app never fabricates projections, stats, matchups, or injuries.
"""
from __future__ import annotations
import datetime as dt, email.utils, html, json, re, time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; OUT.mkdir(exist_ok=True)
LEAGUE='1388315713940262912'; USER='1394868996146204672'; V1='https://api.sleeper.app/v1'; SLEEPER_DATA='https://api.sleeper.com'
NOW=dt.datetime.now(dt.timezone.utc); STAMP=NOW.isoformat(); HEALTH={}

def read(name,default=None):
    try:return json.loads((OUT/name).read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def save(name,obj):
    p=OUT/name; t=p.with_suffix('.tmp'); t.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); t.replace(p)

def get(url):
    err=None
    for attempt in range(2):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/3.0 personal fantasy manager','Accept':'application/json, application/rss+xml, */*'})
            with urllib.request.urlopen(req,timeout=20) as r:return r.read()
        except Exception as exc:
            err=exc
            if attempt==0:time.sleep(.45)
    raise RuntimeError(str(err)[:220])

def getj(url):return json.loads(get(url))

def source(key,url,validate,previous):
    try:
        x=getj(url)
        if not validate(x):raise RuntimeError('Response failed validation')
        HEALTH[key]={'ok':True,'url':url,'checked_at':STAMP,'updated_at':STAMP,'retained':False};return x
    except Exception as exc:
        HEALTH[key]={'ok':False,'url':url,'checked_at':STAMP,'updated_at':(read('dashboard.json',{}) or {}).get('updated_at'),'retained':previous is not None,'note':str(exc)[:220]};return previous

league=source('league',f'{V1}/league/{LEAGUE}',lambda x:isinstance(x,dict) and x.get('league_id')==LEAGUE,read('league.json'))
rosters=source('rosters',f'{V1}/league/{LEAGUE}/rosters',lambda x:isinstance(x,list) and len(x)==10,read('rosters.json',[]))
users=source('users',f'{V1}/league/{LEAGUE}/users',lambda x:isinstance(x,list) and any(u.get('user_id')==USER for u in x),read('users.json',[]))
if not league or len(rosters)!=10 or not any(r.get('owner_id')==USER for r in rosters):raise SystemExit('Correct 10-team league snapshot unavailable; refusing to overwrite dashboard')
season=str(league.get('season'))
nfl_state=source('nfl_state',f'{V1}/state/nfl',lambda x:isinstance(x,dict) and str(x.get('season'))==season,read('nfl_state.json',{})) or {}
league_week=int((league.get('settings') or {}).get('leg') or 1)
state_week=int(nfl_state.get('week') or league_week or 1)
week=max(1,min(18,max(league_week,state_week)))

# Sleeper says the large player map should only be fetched about once per day.
players=read('players_nfl.json',{}) or {}; cache=read('players_cache_meta.json',{}) or {}
try:age=(NOW-dt.datetime.fromisoformat(cache.get('fetched_at',''))).total_seconds()
except Exception:age=10**9
if not players or age>86400:
    new=source('players',f'{V1}/players/nfl',lambda x:isinstance(x,dict) and len(x)>1000,players)
    if new:players=new; save('players_nfl.json',players); save('players_cache_meta.json',{'fetched_at':STAMP})
else:HEALTH['players']={'ok':True,'url':f'{V1}/players/nfl','checked_at':STAMP,'updated_at':cache.get('fetched_at'),'retained':True,'note':'Daily cache'}

owned={str(pid) for r in rosters for k in ('players','reserve','taxi') for pid in (r.get(k) or [])}
P={}
def make(pid,p):
    return {'id':str(pid),'name':p.get('full_name') or ' '.join(x for x in [p.get('first_name'),p.get('last_name')] if x) or str(pid),'pos':p.get('position'),'positions':p.get('fantasy_positions') or ([p.get('position')] if p.get('position') else []),'team':p.get('team'),'injury':p.get('injury_status'),'injury_body_part':p.get('injury_body_part'),'practice':p.get('practice_participation'),'depth':p.get('depth_chart_order'),'status':p.get('status'),'experience':p.get('years_exp'),'active':p.get('active'),'stats':None,'season_stats':None,'projection':None,'projected_stats':None,'actual':None,'draft_pick':None,'adds':0,'drops':0}
for pid,p in players.items():
    if str(pid) in owned or (p.get('position') in {'QB','RB','WR','TE','K'} and p.get('team') and p.get('active') is not False):P[str(pid)]=make(pid,p)
for team in 'ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split():
    P.setdefault(team,{'id':team,'name':team+' D/ST','pos':'DEF','positions':['DEF'],'team':team,'injury':None,'injury_body_part':None,'practice':None,'depth':None,'status':'Active','experience':None,'active':True,'stats':None,'season_stats':None,'projection':None,'projected_stats':None,'actual':None,'draft_pick':None,'adds':0,'drops':0})

uidx={u.get('user_id'):u for u in users}; teams=[]
for r in rosters:
    u=uidx.get(r.get('owner_id'),{}); meta=u.get('metadata') or {}; roster_players=list(dict.fromkeys(str(x) for x in (r.get('players') or [])+(r.get('reserve') or [])))
    teams.append({'id':r.get('roster_id'),'user_id':r.get('owner_id'),'owner':u.get('display_name') or f'Manager {r.get("roster_id")}','name':meta.get('team_name') or u.get('display_name') or f'Team {r.get("roster_id")}','players':roster_players,'starters':[str(x) for x in (r.get('starters') or [])],'reserve':[str(x) for x in (r.get('reserve') or [])],'settings':r.get('settings') or {}})
my=next(t['id'] for t in teams if t['user_id']==USER)

trend=source('trending',f'{V1}/players/nfl/trending/add?lookback_hours=24&limit=100',lambda x:isinstance(x,list),read('trending_add_v3.json',[])) or []
drops=source('trending_drops',f'{V1}/players/nfl/trending/drop?lookback_hours=24&limit=100',lambda x:isinstance(x,list),read('trending_drop_v3.json',[])) or []
for x in trend:
    pid=str(x.get('player_id')); 
    if pid in P:P[pid]['adds']=int(x.get('count') or 0)
for x in drops:
    pid=str(x.get('player_id'));
    if pid in P:P[pid]['drops']=int(x.get('count') or 0)

picks=source('draft',f'{V1}/draft/{league.get("draft_id")}/picks',lambda x:isinstance(x,list),read('draft_picks.json',[])) or []
for x in picks:
    pid=str(x.get('player_id'))
    if pid in P:P[pid]['draft_pick']=x.get('pick_no')
matchups=source('matchups',f'{V1}/league/{LEAGUE}/matchups/{week}',lambda x:isinstance(x,list),read('matchups.json',[])) or []
transactions=source('transactions',f'{V1}/league/{LEAGUE}/transactions/{week}',lambda x:isinstance(x,list),read('transactions.json',[])) or []
for m in matchups:
    for pid,pts in (m.get('players_points') or {}).items():
        if str(pid) in P:P[str(pid)]['actual']=pts

# Sleeper stats/projections are an undocumented app feed. In 2026 the useful
# shape is a LIST of rows from api.sleeper.com with season_type/order_by query
# parameters, not the older dict keyed by player id. Normalize both shapes.
def normalize_rows(x):
    if isinstance(x,dict):
        return {str(k):v for k,v in x.items() if isinstance(v,dict)}
    out={}
    if isinstance(x,list):
        for row in x:
            if not isinstance(row,dict): continue
            pid=row.get('player_id') or (row.get('player') or {}).get('player_id')
            if pid is not None:
                # Sleeper nests the actual stat line under stats on some responses.
                stats_obj=row.get('stats') if isinstance(row.get('stats'),dict) else {}
                merged={**row,**stats_obj}
                out[str(pid)]=merged
    return out

def fetch_sleeper_board(kind, season, week=None):
    suffix=f'{season}' + (f'/{week}' if week is not None else '')
    qs='season_type=regular&position[]=DEF&position[]=K&position[]=QB&position[]=RB&position[]=TE&position[]=WR&order_by=pts_ppr'
    urls=[
        f'{SLEEPER_DATA}/{kind}/nfl/{suffix}?{qs}',
        f'{V1}/{kind}/nfl/regular/{season}' + (f'/{week}' if week is not None else ''),
    ]
    previous=read(('stats' if kind=='stats' else 'projections') + ('_week_v3.json' if week is not None else '_season_v3.json'),{}) or {}
    for url in urls:
        try:
            raw=getj(url); norm=normalize_rows(raw)
            real=sum(1 for v in norm.values() if isinstance(v,dict) and (v.get('pts_ppr') is not None or v.get('gp') is not None or v.get('rec') is not None or v.get('rush_att') is not None or v.get('pass_att') is not None))
            if real>=20:
                HEALTH[kind if week is not None else 'season_stats']={'ok':True,'url':url,'checked_at':STAMP,'updated_at':STAMP,'retained':False,'rows':len(norm),'real_rows':real}
                return norm
        except Exception as exc:
            last=str(exc)[:220]
    key=kind if week is not None else 'season_stats'
    HEALTH[key]={'ok':False,'url':urls[0],'checked_at':STAMP,'updated_at':None,'retained':bool(previous),'note':locals().get('last','No usable rows')}
    return previous

stats=fetch_sleeper_board('stats',season,week)
proj=fetch_sleeper_board('projections',season,week)
season_stats=fetch_sleeper_board('stats',season,None)
for pid,p in P.items():
    s=stats.get(pid)
    if isinstance(s,dict):
        p['stats']=s; p['actual']=s.get('pts_ppr',p['actual'])
    ss=season_stats.get(pid)
    if isinstance(ss,dict): p['season_stats']=ss
    pr=proj.get(pid)
    if isinstance(pr,dict) and pr.get('pts_ppr') is not None:
        p['projection']=pr.get('pts_ppr'); p['projected_stats']=pr

# External headlines only. They are context, not a stats source and never alter scores automatically.
news=[]; news_url='https://news.google.com/rss/search?q=NFL+fantasy+football+injury+waiver+when:7d&hl=en-US&gl=US&ceid=US:en'
try:
    root=ET.fromstring(get(news_url)); seen=set()
    for item in root.findall('.//item'):
        title=html.unescape(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip(); src=item.find('source'); pub=item.findtext('pubDate')
        if not title or title in seen or not link.startswith('https://'):continue
        seen.add(title)
        try:d=email.utils.parsedate_to_datetime(pub); pub=d.isoformat();
        except Exception:pass
        mentions=[]; nt=re.sub('[^a-z0-9]','',title.lower())
        for pid,p in P.items():
            if p['pos']!='DEF' and len(p['name'])>4 and re.sub('[^a-z0-9]','',p['name'].lower()) in nt:mentions.append(pid)
        news.append({'title':title,'url':link,'source':src.text if src is not None else 'Google News','published':pub,'players':mentions})
    HEALTH['news']={'ok':bool(news),'url':news_url,'checked_at':STAMP,'updated_at':STAMP if news else None,'retained':False,'note':'Headlines only; never used as statistical evidence.'}
except Exception as exc:HEALTH['news']={'ok':False,'url':news_url,'checked_at':STAMP,'updated_at':None,'retained':False,'note':str(exc)[:220]}

league_out={'id':LEAGUE,'name':league.get('name'),'season':season,'week':week,'slots':league.get('roster_positions') or [],'scoring':league.get('scoring_settings') or {},'settings':league.get('settings') or {}}
dashboard={'schema':3,'built_at':STAMP,'updated_at':HEALTH['rosters'].get('updated_at'),'league':league_out,'my_team':my,'teams':teams,'players':P,'matchups':matchups,'transactions':transactions,'news':news[:100],'sources':HEALTH,'source_policy':{'fantasy_data':'Sleeper only','external_news':'headlines only','nflverse':False}}
# Compact, ChatGPT-friendly live bridge with resolved player names for every roster.
resolved_teams=[]
for t in teams:
    resolved_teams.append({
        'roster_id':t['id'],
        'owner':t['owner'],
        'team_name':t['name'],
        'record':{'wins':(t.get('settings') or {}).get('wins',0),'losses':(t.get('settings') or {}).get('losses',0),'ties':(t.get('settings') or {}).get('ties',0)},
        'players':[dict(P.get(pid,{'id':pid,'name':pid}),starter=(pid in set(t.get('starters') or [])),reserve=(pid in set(t.get('reserve') or []))) for pid in t.get('players',[])]
    })
bridge={
    'refreshed_at_utc':STAMP,
    'league':league_out,
    'my_roster_id':my,
    'teams':resolved_teams,
    'matchups':matchups,
    'transactions':transactions,
    'trending_add':trend,
    'trending_drop':drops,
    'sources':HEALTH
}
status={
    'ok':True,
    'league_id':LEAGUE,
    'season':season,
    'current_week':week,
    'league_week':league_week,
    'nfl_state_week':state_week,
    'my_roster_id':my,
    'team_count':len(teams),
    'refreshed_at_utc':STAMP,
    'sources':{k:bool(v.get('ok')) for k,v in HEALTH.items()}
}
save('dashboard.json',dashboard); save('chatgpt_bridge.json',bridge); save('status.json',status); save('nfl_state.json',nfl_state); save('league.json',league); save('rosters.json',rosters); save('users.json',users); save('trending_add_v3.json',trend); save('trending_drop_v3.json',drops); save('draft_picks.json',picks); save('matchups.json',matchups); save('transactions.json',transactions)
if stats:save('stats_week_v3.json',stats)
if proj:save('projections_week_v3.json',proj)
if season_stats:save('stats_season_v3.json',season_stats)
(ROOT/'v3').mkdir(exist_ok=True); (ROOT/'v3'/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(dashboard,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
save('health_v3.json',{'built_at':STAMP,'season':season,'week':week,'sources':HEALTH,'players':len(P),'fantasy_data':'Sleeper only'})
print(json.dumps({'season':season,'week':week,'players':len(P),'stats':len(stats),'projections':len(proj),'source_policy':dashboard['source_policy']},indent=2))
