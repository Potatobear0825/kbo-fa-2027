"""Best-effort MLBPark best-list discovery. Never treat community posts as facts.
Respect robots.txt, stop on disallow, cap requests, and keep prior snapshot on errors.
FMKorea has no verified compatible public feed: do not pretend to auto-collect.
"""
import datetime, json, re, time, urllib.parse, urllib.request, urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'community.json'
USER_AGENT='KBOFATrackerCommunity/1.0 (+personal noncommercial digest)'
BASE='https://mlbpark.donga.com'
LIST=BASE+'/mp/best.php?b=kbotown&m=view'
HEADERS={'User-Agent':USER_AGENT}
PLAYERS=json.loads((ROOT/'data.json').read_text(encoding='utf-8'))['players']
NAMES=[x['name'] for x in PLAYERS]
SIGNAL=re.compile(r'FA|에프에이|계약|잔류|이적|썰|오퍼|영입|협상|행선지',re.I)

class Links(HTMLParser):
 def __init__(self):super().__init__();self.found=[];self.a=None
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.a={'href':dict(attrs).get('href',''),'text':''}
 def handle_data(self,data):
  if self.a is not None:self.a['text']+=data
 def handle_endtag(self,tag):
  if tag=='a' and self.a:
   self.found.append(self.a);self.a=None

def allowed(url):
 parsed=urllib.parse.urlsplit(url)
 robots=urllib.robotparser.RobotFileParser()
 robots.set_url(parsed.scheme+'://'+parsed.netloc+'/robots.txt')
 try:robots.read();return robots.can_fetch(USER_AGENT,url)
 except Exception:return False

def get(url):
 if not allowed(url):raise RuntimeError('robots 정책 미확인/접근 불허: '+url)
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=12) as r:
  return r.read(750000).decode('utf-8','replace')

def main():
 old=json.loads(DATA.read_text(encoding='utf-8'))
 try:
  html=get(LIST);p=Links();p.feed(html)
  links=[]
  for a in p.found:
   title=re.sub(r'\s+',' ',a['text']).strip()
   url=urllib.parse.urljoin(BASE,a['href'])
   if not ('mlbpark.donga.com' in urllib.parse.urlsplit(url).netloc and '/mp/b.php' in url):continue
   if not (SIGNAL.search(title) and (any(n in title for n in NAMES) or 'FA' in title.upper())):continue
   if url not in [u for u,t in links]:links.append((url,title))
  records={p['url']:p for p in old.get('posts',[]) if p.get('site')!='MLBPark'}
  # Cap detail requests and keep only verified numeric recommendations.
  for url,title in links[:10]:
   time.sleep(2)
   try:
    page=get(url)
    plain=re.sub(r'<[^>]+>',' ',page)
    plain=re.sub(r'\s+',' ',plain)
    m=re.search(r'추천\s*([0-9,]+)\s*조회',plain)
    if not m:continue
    likes=int(m.group(1).replace(',',''))
    date=re.search(r'글번호\s*\d+\s*\|\s*(20\d\d-\d\d-\d\d\s+\d\d:\d\d)',plain)
    records[url]={'site':'MLBPark','title':title,'url':url,'likes':likes,'posted_at':date.group(1) if date else None}
   except Exception as exc:print('article skipped',url,str(exc)[:100])
  # Keep 14 day window only when timestamp exists, do not show stale undated posts.
  cutoff=(datetime.datetime.now()-datetime.timedelta(days=14)).strftime('%Y-%m-%d')
  kept=[p for p in records.values() if p.get('posted_at') and p['posted_at'][:10]>=cutoff]
  old['posts']=sorted(kept,key=lambda p:(-p['likes'],p['posted_at']))[:60]
  old['checked_at']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds')
  DATA.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print('Community scan: valid posts',len(old['posts']))
 except Exception as exc:print('Community scan unavailable, keeping previous records:',str(exc)[:300])

if __name__=='__main__':main()
