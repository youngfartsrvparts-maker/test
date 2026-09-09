import json, urllib.request, urllib.parse, datetime, re, xml.etree.ElementTree as ET
from pathlib import Path

LEAGUE_ID = "1388315713940262912"
USERNAME = "ChatGPTJagger"
USER_ID = "1394868996146204672"
SLEEPER = "https://api.sleeper.app/v1"
OUT = Path("data")
OUT.mkdir(exist_ok=True)
UA = {"User-Agent":"JaggerGM/2.0 fantasy league assistant"}


def get_json(url, timeout=35):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.load(r)

def get_bytes(url, timeout=35):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read()

def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")

def sleeper(path): return get_json(SLEEPER+path)

def norm(s):
    return re.sub(r"[^a-z0-9]","",(s or "").lower())

league=sleeper(f"/league/{LEAGUE_ID}")
users=sleeper(f"/league/{LEAGUE_ID}/users")
rosters=sleeper(f"/league/{LEAGUE_ID}/rosters")
state=sleeper("/state/nfl")
week=int(state.get("week") or 1)
season=int(league.get("season") or state.get("season") or 2026)

players_path=OUT/"players_nfl.json"
refresh_players=True
if players_path.exists():
    m=datetime.datetime.fromtimestamp(players_path.stat().st_mtime,datetime.timezone.utc)
    refresh_players=m.date()!=datetime.datetime.now(datetime.timezone.utc).date()
if refresh_players:
    players=sleeper("/players/nfl")
    dump("players_nfl.json",players)
else:
    players=json.loads(players_path.read_text(encoding="utf-8"))

user_by_id={u["user_id"]:u for u in users}
rostered=set(pid for r in rosters for pid in (r.get("players") or []))

def pobj(pid):
    p=players.get(pid,{})
    if p:
        return {"player_id":pid,"name":p.get("full_name") or (str(p.get("first_name") or "")+" "+str(p.get("last_name") or "")).strip() or pid,
                "first_name":p.get("first_name"),"last_name":p.get("last_name"),"position":p.get("position"),"team":p.get("team"),
                "status":p.get("status"),"injury_status":p.get("injury_status"),"injury_body_part":p.get("injury_body_part"),
                "practice_participation":p.get("practice_participation"),"depth_chart_position":p.get("depth_chart_position"),
                "years_exp":p.get("years_exp"),"number":p.get("number"),"fantasy_data_id":p.get("fantasy_data_id"),
                "gsis_id":p.get("gsis_id"),"espn_id":p.get("espn_id")}
    return {"player_id":pid,"name":pid,"position":"DEF" if len(pid)<=3 else None,"team":pid if len(pid)<=3 else None}

teams=[]; my_team=None
for r in rosters:
    u=user_by_id.get(r.get("owner_id"),{})
    starters=set(r.get("starters") or [])
    t={"roster_id":r.get("roster_id"),"owner_id":r.get("owner_id"),"display_name":u.get("display_name"),
       "team_name":(u.get("metadata") or {}).get("team_name"),"settings":r.get("settings") or {},"reserve":r.get("reserve") or [],
       "players":[dict(pobj(pid),starter=pid in starters,reserve=pid in (r.get("reserve") or [])) for pid in (r.get("players") or [])]}
    teams.append(t)
    if r.get("owner_id")==USER_ID or u.get("display_name")==USERNAME: my_team=t

matchups=sleeper(f"/league/{LEAGUE_ID}/matchups/{week}")
transactions=sleeper(f"/league/{LEAGUE_ID}/transactions/{week}")
trending_add=sleeper("/players/nfl/trending/add?lookback_hours=24&limit=150")
trending_drop=sleeper("/players/nfl/trending/drop?lookback_hours=24&limit=150")
drafts=sleeper(f"/league/{LEAGUE_ID}/drafts")
draft_picks=[]
for d in drafts:
    try: draft_picks += sleeper(f"/draft/{d['draft_id']}/picks")
    except Exception: pass

free_agents=[]
for pid,p in players.items():
    if pid in rostered or p.get("position") not in {"QB","RB","WR","TE","K"} or p.get("active") is False: continue
    free_agents.append(pobj(pid))

# Schedule / scoreboard snapshot from ESPN public scoreboard API.
schedule=[]
try:
    espn=get_json(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&limit=400")
    for ev in espn.get("events",[]):
        comp=(ev.get("competitions") or [{}])[0]
        competitors=comp.get("competitors") or []
        teams_map={c.get("homeAway"):((c.get("team") or {}).get("abbreviation")) for c in competitors}
        schedule.append({"id":ev.get("id"),"date":ev.get("date"),"name":ev.get("shortName") or ev.get("name"),
                         "status":((ev.get("status") or {}).get("type") or {}).get("name"),"week":((ev.get("week") or {}).get("number")),
                         "home":teams_map.get("home"),"away":teams_map.get("away")})
except Exception:
    schedule=[]

# Weekly stats from an open nflverse-based JSON pipeline; fall back cleanly if week not published yet.
weekly_stats=[]
for w in range(1,max(week,1)+1):
    url=f"https://raw.githubusercontent.com/NityaGehlot/nfl-data/main/data/player_stats_{season}_week{w:02d}.json"
    try:
        rows=get_json(url,timeout=20)
        if isinstance(rows,list): weekly_stats.extend(rows)
    except Exception:
        pass

# Normalize season-to-date stats by player name, keeping fields useful for fantasy decisions.
stats_by_name={}
for row in weekly_stats:
    name=row.get("player_name") or row.get("player_display_name")
    if not name: continue
    k=norm(name); agg=stats_by_name.setdefault(k,{"name":name,"position":row.get("position"),"team":row.get("team"),"games":0,"fantasy_points_ppr":0,
        "targets":0,"receptions":0,"carries":0,"rushing_yards":0,"receiving_yards":0,"rushing_tds":0,"receiving_tds":0,"passing_yards":0,"passing_tds":0,"passing_interceptions":0})
    agg["games"]+=1
    for f in ["fantasy_points_ppr","targets","receptions","carries","rushing_yards","receiving_yards","rushing_tds","receiving_tds","passing_yards","passing_tds","passing_interceptions"]:
        try: agg[f]+=float(row.get(f) or 0)
        except Exception: pass
    agg["last_week"]=row.get("week")
    agg["last_opponent"]=row.get("opponent_team")
    agg["injury_status"]=row.get("injury_status")
    agg["practice_status"]=row.get("practice_status")
    agg["primary_injury"]=row.get("primary_injury")

# News: use public FantasySP NFL player/headline RSS feeds, then tag league-relevant players by headline/description.
news=[]
all_names=[]
for t in teams:
    all_names.extend([p["name"] for p in t["players"] if p.get("name")])
heat_ids=[x.get("player_id") for x in trending_add[:50]]
all_names.extend([players.get(pid,{}).get("full_name") for pid in heat_ids if players.get(pid,{})])
name_set=[]; seen=set()
for n in all_names:
    if n and n not in seen: seen.add(n); name_set.append(n)

def parse_rss(url):
    out=[]
    raw=get_bytes(url,timeout=25)
    root=ET.fromstring(raw)
    for item in root.findall(".//item"):
        title=(item.findtext("title") or "").strip(); desc=re.sub("<[^>]+>"," ",item.findtext("description") or "").strip()
        link=(item.findtext("link") or "").strip(); pub=(item.findtext("pubDate") or "").strip()
        text=(title+" "+desc).lower(); mentions=[n for n in name_set if n.lower() in text]
        out.append({"title":title,"summary":re.sub(r"\s+"," ",desc)[:320],"link":link,"published":pub,"source":"FantasySP","players_mentioned":mentions})
    return out
for url in ["https://www.fantasysp.com/rss/nfl/allplayer/","https://www.fantasysp.com/rss/nfl/headlines/"]:
    try: news.extend(parse_rss(url))
    except Exception: pass
# Dedupe and simple impact classification.
news_out=[]; keys=set()
for a in news:
    k=(a.get("title") or "").lower()
    if not k or k in keys: continue
    keys.add(k); txt=(a.get("title","")+" "+a.get("summary","")).lower()
    if any(x in txt for x in ["out for","injured reserve","torn","surgery","misses practice","ruled out","suspended"]): impact="negative"
    elif any(x in txt for x in ["limited practice","questionable","injury","uncertain"]): impact="watch"
    elif any(x in txt for x in ["starter","starting","breakout","career-high","returns","cleared","full practice"]): impact="positive"
    else: impact="neutral"
    a["impact"]=impact; news_out.append(a)
news_out=news_out[:250]

# Attach compact stats + recent news to player objects used by the app.
news_by_name={}
for a in news_out:
    for n in a.get("players_mentioned") or []:
        news_by_name.setdefault(norm(n),[]).append(a)

def enrich(p):
    q=dict(p); k=norm(q.get("name")); q["stats"]=stats_by_name.get(k); q["news"]=(news_by_name.get(k) or [])[:4]
    if q.get("team"):
        q["upcoming_games"]=[g for g in schedule if g.get("home")==q["team"] or g.get("away")==q["team"]][:4]
    return q
for t in teams: t["players"]=[enrich(p) for p in t["players"]]
my_team=next((t for t in teams if t["roster_id"]==(my_team or {}).get("roster_id")),my_team)
free_agents=[enrich(p) for p in free_agents]

status={"ok":True,"league_id":LEAGUE_ID,"username":USERNAME,"user_id":USER_ID,"season":str(season),"current_week":week,
        "refreshed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"team_count":len(rosters),"my_roster_id":(my_team or {}).get("roster_id"),
        "sources":{"sleeper":True,"schedule":bool(schedule),"weekly_stats":bool(weekly_stats),"news":bool(news_out)},
        "counts":{"free_agents":len(free_agents),"weekly_stat_rows":len(weekly_stats),"news":len(news_out)}}

for name,obj in {"status.json":status,"league.json":league,"users.json":users,"rosters.json":rosters,"teams.json":teams,"my_team.json":my_team,
                 "free_agents.json":free_agents,"matchups.json":matchups,"transactions.json":transactions,"trending.json":{"add":trending_add,"drop":trending_drop},
                 "drafts.json":drafts,"draft_picks.json":draft_picks,"nfl_state.json":state,"schedule.json":schedule,"season_stats.json":stats_by_name,"news.json":news_out}.items(): dump(name,obj)
print(json.dumps(status,indent=2))
