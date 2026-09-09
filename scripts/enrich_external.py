import json,csv,io,re,urllib.request,urllib.parse,xml.etree.ElementTree as ET,datetime
from pathlib import Path
OUT=Path('data'); UA={'User-Agent':'Mozilla/5.0 JaggerGM/2.0'}

def get(url,timeout=40):
 req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def load(n,d=None):
 p=OUT/n
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return d
def dump(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
def norm(s):return re.sub(r'[^a-z0-9]','',(s or '').lower())
status=load('status.json',{}); teams=load('teams.json',[]); my=load('my_team.json',{}); fa=load('free_agents.json',[]); season=int(status.get('season') or 2026); week=int(status.get('current_week') or 1)
# nflverse schedule CSV is maintained continuously and includes future 2026 games.
schedule=[]
try:
 raw=get('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv').decode('utf-8-sig',errors='replace')
 for r in csv.DictReader(io.StringIO(raw)):
  if str(r.get('season'))!=str(season) or r.get('game_type')!='REG':continue
  try:w=int(r.get('week') or 0)
  except:w=0
  schedule.append({'id':r.get('game_id'),'date':r.get('gameday'),'time':r.get('gametime'),'week':w,'home':r.get('home_team'),'away':r.get('away_team'),'spread_line':r.get('spread_line'),'total_line':r.get('total_line'),'roof':r.get('roof'),'surface':r.get('surface')})
except Exception:schedule=[]
# Build league-relevant player name set.
names=[]
for t in teams:
 for p in t.get('players',[]):
  if p.get('name'):names.append(p['name'])
seen=set();names=[n for n in names if not(n in seen or seen.add(n))]

def parse_rss(url,source):
 out=[];root=ET.fromstring(get(url,25))
 for item in root.findall('.//item'):
  title=(item.findtext('title') or '').strip();desc=re.sub('<[^>]+>',' ',item.findtext('description') or '').strip();link=(item.findtext('link') or '').strip();pub=(item.findtext('pubDate') or '').strip();text=(title+' '+desc).lower();mentions=[n for n in names if n.lower() in text]
  out.append({'title':title,'summary':re.sub(r'\s+',' ',desc)[:360],'link':link,'published':pub,'source':source,'players_mentioned':mentions})
 return out
news=[]
for url in ['https://www.fantasysp.com/rss/nfl/allplayer/','https://www.fantasysp.com/rss/nfl/headlines/']:
 try:news+=parse_rss(url,'FantasySP')
 except Exception:pass
# Backup broad current NFL fantasy news feed if provider blocks an automated request.
if not news:
 q=urllib.parse.quote('NFL fantasy football injury OR waiver OR starter OR depth chart')
 try:news+=parse_rss(f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en','Google News')
 except Exception:pass
out=[];keys=set()
for n in news:
 k=n.get('title','').lower()
 if not k or k in keys:continue
 keys.add(k);txt=(n.get('title','')+' '+n.get('summary','')).lower()
 if any(x in txt for x in ['injured reserve','ruled out','torn','surgery','suspended','will miss']):impact='negative'
 elif any(x in txt for x in ['questionable','limited','injury','day-to-day','uncertain']):impact='watch'
 elif any(x in txt for x in ['starting','starter','rb1','wr1','full practice','cleared','returns','breakout']):impact='positive'
 else:impact='neutral'
 n['impact']=impact;out.append(n)
out=out[:250]
by={}
for n in out:
 for x in n.get('players_mentioned',[]):by.setdefault(norm(x),[]).append(n)
def enrich(p):
 p=dict(p);k=norm(p.get('name'));p['news']=(by.get(k) or p.get('news') or [])[:5]
 team=p.get('team');p['upcoming_games']=[g for g in schedule if g.get('week',0)>=week and (g.get('home')==team or g.get('away')==team)][:5] if team else []
 return p
for t in teams:t['players']=[enrich(p) for p in t.get('players',[])]
my=next((t for t in teams if t.get('roster_id')==my.get('roster_id')),my);fa=[enrich(p) for p in fa]
status.setdefault('sources',{}).update({'schedule':bool(schedule),'news':bool(out)});status.setdefault('counts',{}).update({'news':len(out),'schedule_games':len(schedule)});status['refreshed_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
dump('schedule.json',schedule);dump('news.json',out);dump('teams.json',teams);dump('my_team.json',my);dump('free_agents.json',fa);dump('status.json',status)
print(json.dumps({'schedule':len(schedule),'news':len(out)},indent=2))
