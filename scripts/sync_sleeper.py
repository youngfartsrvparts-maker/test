import json, os, urllib.request, datetime
from pathlib import Path

LEAGUE_ID = "1388315713940262912"
USERNAME = "ChatGPTJagger"
USER_ID = "1394868996146204672"
BASE = "https://api.sleeper.app/v1"
OUT = Path("data")
OUT.mkdir(exist_ok=True)


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "SleeperFantasyBridge/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def dump(name, data):
    with open(OUT / name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

league = get(f"/league/{LEAGUE_ID}")
users = get(f"/league/{LEAGUE_ID}/users")
rosters = get(f"/league/{LEAGUE_ID}/rosters")

# Refresh the large player directory once per UTC day.
players_path = OUT / "players_nfl.json"
refresh_players = True
if players_path.exists():
    mtime = datetime.datetime.fromtimestamp(players_path.stat().st_mtime, datetime.timezone.utc)
    refresh_players = mtime.date() != datetime.datetime.now(datetime.timezone.utc).date()
if refresh_players:
    players = get("/players/nfl")
    dump("players_nfl.json", players)
else:
    with open(players_path, encoding="utf-8") as f:
        players = json.load(f)

user_by_id = {u["user_id"]: u for u in users}
rostered = set()
for r in rosters:
    rostered.update(r.get("players") or [])


def player_obj(pid):
    if pid in players:
        p = players[pid]
        return {
            "player_id": pid,
            "name": p.get("full_name") or p.get("first_name") or pid,
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "position": p.get("position"),
            "team": p.get("team"),
            "status": p.get("status"),
            "injury_status": p.get("injury_status"),
            "years_exp": p.get("years_exp"),
        }
    # Team defenses are rostered as abbreviations.
    return {"player_id": pid, "name": pid, "position": "DEF" if len(pid) <= 3 else None, "team": pid if len(pid) <= 3 else None}

teams = []
my_team = None
for r in rosters:
    u = user_by_id.get(r.get("owner_id"), {})
    ids = r.get("players") or []
    starters = set(r.get("starters") or [])
    team = {
        "roster_id": r.get("roster_id"),
        "owner_id": r.get("owner_id"),
        "display_name": u.get("display_name"),
        "team_name": (u.get("metadata") or {}).get("team_name"),
        "settings": r.get("settings") or {},
        "players": [dict(player_obj(pid), starter=(pid in starters)) for pid in ids],
        "reserve": r.get("reserve") or [],
    }
    teams.append(team)
    if r.get("owner_id") == USER_ID or u.get("display_name") == USERNAME:
        my_team = team

# Current NFL week from Sleeper state, then league matchups/transactions for that week.
state = get("/state/nfl")
week = int(state.get("week") or 1)
matchups = get(f"/league/{LEAGUE_ID}/matchups/{week}")
transactions = get(f"/league/{LEAGUE_ID}/transactions/{week}")
trending_add = get("/players/nfl/trending/add?lookback_hours=24&limit=100")
trending_drop = get("/players/nfl/trending/drop?lookback_hours=24&limit=100")
drafts = get(f"/league/{LEAGUE_ID}/drafts")

# Compact free-agent directory for skill positions + kickers; defenses are derived from NFL teams separately.
fantasy_positions = {"QB", "RB", "WR", "TE", "K"}
free_agents = []
for pid, p in players.items():
    if pid in rostered:
        continue
    pos = p.get("position")
    if pos not in fantasy_positions:
        continue
    if p.get("active") is False:
        continue
    free_agents.append(player_obj(pid))
free_agents.sort(key=lambda x: (x.get("position") or "", x.get("name") or ""))

status = {
    "ok": True,
    "league_id": LEAGUE_ID,
    "username": USERNAME,
    "user_id": USER_ID,
    "season": league.get("season"),
    "current_week": week,
    "refreshed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "team_count": len(rosters),
    "my_roster_id": my_team.get("roster_id") if my_team else None,
}

dump("status.json", status)
dump("league.json", league)
dump("users.json", users)
dump("rosters.json", rosters)
dump("teams.json", teams)
dump("my_team.json", my_team)
dump("free_agents.json", free_agents)
dump("matchups.json", matchups)
dump("transactions.json", transactions)
dump("trending.json", {"add": trending_add, "drop": trending_drop})
dump("drafts.json", drafts)
dump("nfl_state.json", state)
print(json.dumps(status, indent=2))
