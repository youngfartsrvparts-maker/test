"""Current role/news context for Jagger GM.
Sleeper remains league authority. External sources may adjust current-role context only when evidence is explicit.
Signals expire automatically and are displayed with source/confidence.
"""
import datetime as dt, email.utils, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; V3=ROOT/'v3'; NOW=dt.datetime.now(dt.timezone.utc)
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/6.6 role intelligence','Accept':'application/rss+xml,*/*'})
 with urllib.request.urlopen(req,timeout=20) as r:return r.read()
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
def ctx(p):return (p or {}).get('current_context') or {}
d=load('dashboard.json',{});players=d.get('players',{});names={norm(p.get('name')):pid for pid,p in players.items() if p.get('name')}
verified={
 'MarShawn Lloyd':{'role':'Lead/feature candidate with Jacobs unavailable','role_boost':3.0,'confidence':96,'as_of':'2026-09-08','expires':'2026-09-16','reason':'Josh Jacobs is on the Commissioner’s Exempt List. Packers reporting says Lloyd is quite likely to handle the lead role, although a committee remains possible.','sources':[{'name':'Packers.com','url':'https://www.packers.com/news/rb-marshawn-lloyd-as-ready-as-he-s-ever-been-to-help-packers-sep-2-2026'},{'name':'NFL.com','url':'https://www.nfl.com/news/nfl-places-packers-rb-josh-jacobs-commissioner-exempt-list'}]},
 'Josh Jacobs':{'role':'Commissioner’s Exempt List / unavailable','role_boost':-10.0,'confidence':99,'as_of':'2026-09-08','expires':'2026-09-16','reason':'The NFL Commissioner’s Exempt List prevents Jacobs from practicing or playing while active.','sources':[{'name':'NFL.com','url':'https://www.nfl.com/news/nfl-places-packers-rb-josh-jacobs-commissioner-exempt-list'}]},
 'Jacory Croskey-Merritt':{'role':'Official Week 1 RB1 on Commanders depth chart','role_boost':1.5,'confidence':98,'as_of':'2026-09-08','expires':'2026-09-14','reason':'Washington’s official Week 1 depth chart lists Croskey-Merritt first at running back ahead of Rachaad White and Kaytron Allen. The Eagles matchup still limits his Week 1 projection.','sources':[{'name':'Commanders.com','url':'https://www.commanders.com/news/commanders-release-2026-week-1-depth-chart'}]},
 'Bhayshul Tuten':{'role':'Week 1 co-starter; illness status must be monitored','role_boost':0.4,'confidence':90,'as_of':'2026-09-08','expires':'2026-09-14','reason':'Jacksonville’s Week 1 depth-chart reporting lists Tuten and Chris Rodriguez Jr. as co-starters, and Tuten recently missed practice with an illness. This is weaker certainty than a clean feature-back role.','sources':[{'name':'Pro Football Reference / RotoWire archive','url':'https://www.pro-football-reference.com/players/news.fcgi?id=TuteBh00'}]},
 'George Kittle':{'role':'Likely active Week 1, but returning from Achilles with snap-limit risk','role_boost':-2.3,'confidence':92,'as_of':'2026-09-08','expires':'2026-09-11','reason':'Kittle is trending toward playing after Achilles rehab, but Week 1 analysis expects a reduced 50–60% snap role and San Francisco listed him limited. This temporary penalty should disappear once he demonstrates a normal workload.','sources':[{'name':'Reuters','url':'https://www.reuters.com/sports/49ers-defensive-end-nick-bosa-going-play-vs-rams--flm-2026-09-08/'},{'name':'FantasyPros','url':'https://www.fantasypros.com/nfl/notes/435116/george-kittle-2026-week-1-outlook.php'}]}
}
query='NFL fantasy football (starter OR starting OR "lead back" OR "feature back" OR committee OR "depth chart" OR promoted OR benched OR injured OR "exempt list" OR suspended) when:2d';url='https://news.google.com/rss/search?q='+urllib.parse.quote(query)+'&hl=en-US&gl=US&ceid=US:en';items=[]
try:
 root=ET.fromstring(get(url))
 for it in root.findall('.//item'):
  title=html.unescape(it.findtext('title') or '').strip();link=(it.findtext('link') or '').strip();pub=it.findtext('pubDate')
  try:published=email.utils.parsedate_to_datetime(pub).astimezone(dt.timezone.utc)
  except:published=None
  if published and published<NOW-dt.timedelta(days=3):continue
  if title and link:items.append({'title':title,'url':link,'published':published.isoformat() if published else pub})
except Exception:pass
for p in players.values():p['current_context']=None
for name,c in verified.items():
 pid=names.get(norm(name))
 if not pid:continue
 try:exp=dt.datetime.fromisoformat(c['expires']+'T23:59:59+00:00')
 except:continue
 if NOW<=exp:players[pid]['current_context']={**c,'type':'verified','active':True}
pos_terms=('starter','starting','lead back','feature back','rb1','wr1','te1','promoted','top of the depth chart','atop the depth chart');neg_terms=('benched','backup','demoted','ruled out','injured reserve','exempt list','suspended')
for item in items:
 nt=norm(item['title']);low=item['title'].lower()
 for pid,p in players.items():
  n=norm(p.get('name'))
  if len(n)<6 or n not in nt:continue
  direction=1 if any(x in low for x in pos_terms) else -1 if any(x in low for x in neg_terms) else 0
  if not direction or ctx(p).get('type')=='verified':continue
  p['current_context']={'type':'headline_signal','active':True,'role':'Fresh positive role signal' if direction>0 else 'Fresh negative availability/role signal','role_boost':1.25*direction,'confidence':58,'as_of':NOW.date().isoformat(),'expires':(NOW+dt.timedelta(days=2)).date().isoformat(),'reason':item['title'],'sources':[{'name':'Google News','url':item['url']}]}
d['role_meta']={'generated_at':NOW.isoformat(),'verified_count':sum(1 for p in players.values() if ctx(p).get('type')=='verified'),'headline_signal_count':sum(1 for p in players.values() if ctx(p).get('type')=='headline_signal'),'policy':'Verified current-role changes can materially affect value. Headline-only signals are modest and cannot independently trigger ACT.'};(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8');print(json.dumps(d['role_meta'],indent=2))