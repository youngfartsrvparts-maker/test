"""Pre-lock news intelligence for Jagger's roster only.
Runs every live sync. Uses targeted Google News queries plus Sleeper injury/practice metadata.
Headline signals are deliberately capped; confirmed Sleeper status remains more authoritative.
"""
import datetime as dt, email.utils, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data';V3=ROOT/'v3';NOW=dt.datetime.now(dt.timezone.utc)
def load(n,d=None):
 try:return json.loads((OUT/n).read_text(encoding='utf-8'))
 except:return d
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'JaggerGM/6.5 prelock news','Accept':'application/rss+xml,*/*'})
 with urllib.request.urlopen(req,timeout=20) as r:return r.read()
def norm(s):return re.sub('[^a-z0-9]','',str(s or '').lower())
def parse_pub(s):
 try:return email.utils.parsedate_to_datetime(s).astimezone(dt.timezone.utc)
 except:return None
def kickoff(p):
 g=(p.get('nfl_schedule') or [None])[0]
 if not g or not g.get('date') or not g.get('time'):return None
 try:
  local=dt.datetime.fromisoformat(g['date']+'T'+g['time']).replace(tzinfo=ZoneInfo('America/New_York'))
  return local.astimezone(dt.timezone.utc)
 except:return None
d=load('dashboard.json',{}) or {};players=d.get('players',{});team=next((t for t in d.get('teams',[]) if t.get('id')==d.get('my_team')),None) or {};ids=[str(x) for x in team.get('players',[])];roster=[players[x] for x in ids if x in players]
# Batch roster names to avoid hammering the feed: ~3 requests for a 15-player roster.
items=[]
for i in range(0,len(roster),5):
 names=[p.get('name') for p in roster[i:i+5] if p.get('name')]
 if not names:continue
 ors=' OR '.join('"'+n.replace('"','')+'"' for n in names)
 q=f'({ors}) (injury OR practice OR starter OR starting OR role OR depth chart OR limited OR questionable OR active OR inactive OR suspended OR workload) when:3d'
 url='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en'
 try:
  root=ET.fromstring(get(url))
  for it in root.findall('.//item'):
   title=html.unescape(it.findtext('title') or '').strip();link=(it.findtext('link') or '').strip();pub=parse_pub(it.findtext('pubDate'));src=it.find('source')
   if not title or not link or (pub and pub<NOW-dt.timedelta(days=4)):continue
   items.append({'title':title,'url':link,'published':pub.isoformat() if pub else None,'source':src.text if src is not None else 'Google News'})
 except Exception:pass
pos_terms=('will start','starting','cleared','full practice','full participant','ready to go','lead back','feature back','rb1','wr1','te1','no injury designation','expected to play','set to play','active')
neg_terms=('ruled out','will not play','inactive','injured reserve','ir ','suspended','exempt list','doubtful','miss practice','did not practice','limited practice','questionable','game-time decision','workload limit','snap limit')
severe=('ruled out','will not play','inactive','injured reserve','suspended','exempt list')
reports=[]
for p in roster:
 pn=norm(p.get('name'));hits=[]
 for it in items:
  if pn and pn in norm(it['title']):hits.append(it)
 hits=sorted({x['url']:x for x in hits}.values(),key=lambda x:x.get('published') or '',reverse=True)[:6]
 score=0;reasons=[]
 for x in hits:
  low=x['title'].lower();delta=0
  if any(t in low for t in severe):delta=-3
  elif any(t in low for t in neg_terms):delta=-1
  elif any(t in low for t in pos_terms):delta=1
  score+=delta
  if delta:reasons.append(x['title'])
 # Sleeper status gets priority over headlines.
 injury=str(p.get('injury') or '').lower();practice=str(p.get('practice') or '').lower();status=str(p.get('status') or '').lower()
 if 'out' in injury or 'ir' in injury or 'inactive' in status:score=min(score,-5)
 elif 'doubt' in injury:score=min(score,-3)
 elif 'question' in injury:score=min(score,-1)
 if 'did not' in practice:score-=2
 elif 'limited' in practice:score-=1
 elif 'full' in practice:score+=1
 score=max(-6,min(4,score));modifier=max(-1.5,min(1.0,score*.25));ko=kickoff(p);hours=(ko-NOW).total_seconds()/3600 if ko else None
 urgency='LOCKED' if hours is not None and hours<=0 else 'URGENT' if hours is not None and hours<=6 else 'TODAY' if hours is not None and hours<=24 else 'MONITOR'
 confidence=min(95,45+len(hits)*7+(20 if p.get('injury') else 0)+(10 if p.get('practice') else 0))
 label='Negative availability signal' if score<=-3 else 'Some availability risk' if score<0 else 'Positive/clear signal' if score>0 else 'No material negative news found'
 context={'generated_at':NOW.isoformat(),'urgency':urgency,'hours_to_lock':round(hours,1) if hours is not None else None,'kickoff_utc':ko.isoformat() if ko else None,'score':score,'model_modifier':round(modifier,2),'confidence':confidence,'label':label,'injury':p.get('injury'),'practice':p.get('practice'),'headlines':hits,'reason':reasons[0] if reasons else ('Sleeper injury/practice status is the main signal.' if p.get('injury') or p.get('practice') else 'No material roster-specific risk headline found in the last 3 days.')}
 p['my_team_news']=context;reports.append({'player_id':p['id'],'name':p['name'],**context})
d['my_team_news_meta']={'generated_at':NOW.isoformat(),'players_analyzed':len(reports),'headline_pool':len(items),'policy':'Roster-only pre-lock analysis. Headline-derived model effect is capped at +1.0/-1.5 points; Sleeper injury/practice status has priority.'}
(OUT/'my_team_news.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'dashboard.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8');V3.mkdir(exist_ok=True);(V3/'snapshot.js').write_text('window.GM_SNAPSHOT='+json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n',encoding='utf-8')
print(json.dumps({'players_analyzed':len(reports),'urgent':sum(r['urgency'] in ('URGENT','TODAY') for r in reports),'negative':sum(r['score']<0 for r in reports)},indent=2))