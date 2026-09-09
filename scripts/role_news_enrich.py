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
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/5.1 role intelligence','Accept':'application/rss+xml,*/*'})
 with urllib.request.urlopen(req,timeout=20) as r:return r.read()
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
def ctx(p):return (p or {}).get('current_context') or {}
d=load('dashboard.json',{});players=d.get('players',{});names={norm(p.get('name')):pid for pid,p in players.items() if p.get('name')}
# Narrow, manually verified high-impact contexts. These auto-expire and are rechecked when materially changed.
verified={
 'MarShawn Lloyd':{
  'role':'Lead candidate in RB committee','role_boost':3.0,'confidence':96,'as_of':'2026-09-09','expires':'2026-09-16',
  'reason':'Josh Jacobs is on the Commissioner’s Exempt List. Packers reporting says Lloyd is likely to lead the available backs, but the offensive coordinator said Week 1 will begin as a running-back committee, so he should not be modeled as a guaranteed workhorse.',
  'sources':[
   {'name':'Packers.com','url':'https://www.packers.com/news/rb-marshawn-lloyd-as-ready-as-he-s-ever-been-to-help-packers-sep-2-2026'},
   {'name':'NFL.com','url':'https://www.nfl.com/news/nfl-places-packers-rb-josh-jacobs-commissioner-exempt-list'},
   {'name':'CBS Sports / RotoWire','url':'https://www.cbssports.com/fantasy/football/news/packers-marshawn-lloyd-set-to-be-included-in-committee/'}]},
 'Josh Jacobs':{
  'role':'Commissioner’s Exempt List / unavailable','role_boost':-10.0,'confidence':99,'as_of':'2026-09-09','expires':'2026-09-16',
  'reason':'The NFL placed Jacobs on the Commissioner’s Exempt List, which prevents him from practicing or playing while he remains on it.',
  'sources':[{'name':'NFL.com','url':'https://www.nfl.com/news/nfl-places-packers-rb-josh-jacobs-commissioner-exempt-list'}]}
}
query='NFL fantasy football (starter OR starting OR "lead back" OR "feature back" OR committee OR "depth chart" OR promoted OR benched OR injured OR "exempt list" OR suspended) when:2d'
url='https://news.google.com/rss/search?q='+urllib.parse.quote(query)+'&hl=en-US&gl=US&ceid=US:en';items=[]
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
pos_terms=('starter','starting','lead back','feature back','rb1','wr1','te1','promoted','top of the depth chart','atop the depth chart')
neg_terms=('benched','backup','demoted','ruled out','injured reserve','exempt list','suspended')
for item in items:
 nt=norm(item['title']);low=item['title'].lower()
 for pid,p in players.items():
  n=norm(p.get('name'))
  if len(n)<6 or n not in nt:continue
  direction=1 if any(x in low for x in pos_terms) else -1 if any(x in low for x in neg_terms) else 0
  if not direction or ctx(p).get('type')=='verified':continue
  p['current_context']={'type':'headline_signal','active':True,'role':'Fresh positive role signal' if direction>0 else 'Fresh negative availability/role signal','role_boost':1.25*direction,'confidence':58,'as_of':NOW.date().isoformat(),'expires':(NOW+dt.timedelta(days=2)).date().isoformat(),'reason':item['title'],'sources':[{'name':'Google News','url':item['url']}]}
d['role_meta']={'generated_at':NOW.isoformat(),'verified_count':sum(1 for p in players.values() if ctx(p).get('type')=='verified'),'headline_signal_count':sum(1 for p in players.values() if ctx(p).get('type')=='headline_signal'),'policy':'Verified current-role changes can materially affect value. Headline-only signals are modest and cannot independently trigger ACT.'}
(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps(d['role_meta'],indent=2))