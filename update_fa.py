"""KBO 2027 FA: only primary-source club announcements may auto-confirm contracts.
No external dependencies. Fail closed: if an official page cannot be verified, keep pending.
"""
import datetime as dt
import email.utils
import html
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

BASE = pathlib.Path(__file__).resolve().parent
DATA, REVIEW = BASE / 'data.json', BASE / 'review.json'
NOW = dt.datetime.now(ZoneInfo('Asia/Seoul'))
START = dt.date(2026, 11, 16)
# First-party domains verified from the KBO club directory. No news domains.
CLUBS = {
    '삼성': 'samsunglions.com', 'KT': 'ktwiz.co.kr',
    'KIA': 'kiatigers.co.kr', 'LG': 'lgtwins.com',
    '두산': 'doosanbears.com', 'SSG': 'ssglanders.com',
    'NC': 'ncdinos.com', '한화': 'hanwhaeagles.co.kr',
    '롯데': 'giantsclub.com', '키움': 'heroesbaseball.co.kr'
}
# Official notice indexes checked directly in addition to search discovery.
INDEXES = {
    'SSG': ['https://www.ssglanders.com/media/news'],
    '삼성': ['https://www.samsunglions.com/intro/intro02.asp'],
}
# Search-only discovery; links are NEVER accepted without fetching an actual club page.
SPECULATIVE = re.compile(r'가능성|예상|전망|협상|제안|추측|관심|임박|초읽기|미계약|계약설|논의|보류|유력|오보|부인|아직|물망|할까|\?')
TERM = re.compile(r'(?<!\d)(\d+)\s*년?\s*\+\s*(\d+)\s*년|(?<!\d)(\d+)\s*년')
AMOUNT = re.compile(r'(?:총액|최대|계약금과\s*연봉\s*합계)\s*(\d+(?:\.\d+)?)\s*억\s*원?')
DATE = re.compile(r'(?<!\d)(2026|2027)[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})')
CONFIRM = re.compile(r'(?:FA\s*)?계약(?:을|을\s*최종)?\s*(?:체결|마쳤|완료|했다|해)|FA\s*재계약|FA\s*계약')

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks=[];self.anchors=[];self.current_href=None;self.linktext=[];self.hidden=0;self.meta={}
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'):self.hidden+=1
        if tag=='a':self.current_href=attrs.get('href');self.linktext=[]
        if tag=='meta':
            k=(attrs.get('property') or attrs.get('name') or '').lower()
            if k:self.meta[k]=attrs.get('content','')
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript'):self.hidden=max(0,self.hidden-1)
        if tag=='a' and self.current_href is not None:
            self.anchors.append((self.current_href,' '.join(self.linktext)))
            self.current_href=None;self.linktext=[]
    def handle_data(self, data):
        if not self.hidden:
            data=' '.join(data.split())
            if data:self.chunks.append(data)
            if data and self.current_href is not None:self.linktext.append(data)

def host_ok(url, team):
    p=urllib.parse.urlsplit(url)
    host=(p.hostname or '').lower().rstrip('.')
    domain=CLUBS[team]
    return p.scheme=='https' and (host==domain or host=='www.'+domain)

_FETCH_CACHE={}
def fetch(url, team=None):
    if team and not host_ok(url,team):raise ValueError('not a first-party club URL')
    if url in _FETCH_CACHE:return _FETCH_CACHE[url]
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KBO-FA-personal-tracker/1.0)'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        final=resp.geturl()
        if team and not host_ok(final,team):raise ValueError('redirect outside club domain')
        raw=resp.read(850000)
        c=resp.headers.get_content_charset() or 'utf-8'
    try:result=(raw.decode(c,errors='replace'), final)
    except LookupError:result=(raw.decode('utf-8',errors='replace'),final)
    _FETCH_CACHE[url]=result
    return result

def extract_date(page):
    # Metadata date has priority; never confuse a dated historical story with a new one.
    for k in ('article:published_time','datepublished','pubdate','date','article:modified_time'):
        value=page.meta.get(k,'')
        if value:
            try:return dt.date.fromisoformat(value[:10])
            except ValueError:pass
    txt=' '.join(page.chunks[:200])
    for m in DATE.finditer(txt):
        try:
            v=dt.date(*map(int,m.groups()))
            if START<=v<=NOW.date():return v
        except ValueError:pass
    return None

def parse_term(text):
    m=TERM.search(text)
    if not m:return None
    if m.group(1):
        a,b=int(m.group(1)),int(m.group(2))
        return f'{a}+{b}' if 1<=a<=10 and 1<=b<=5 and a+b<=10 else None
    yrs=int(m.group(3));return yrs if 1<=yrs<=10 else None

def analyze_official(url, team, player):
    if not host_ok(url,team):return None
    raw,final=fetch(url,team)
    page=Page();page.feed(raw)
    published=extract_date(page)
    if published is None or published<START or published>NOW.date():return None
    title=html.unescape(page.meta.get('og:title','')) or ' '.join(page.chunks[:8])
    # Do not accept a page about another player merely because footer links mention target.
    main=' '.join(page.chunks)
    if player not in title and player not in main[:1300]:return None
    # A contract statement, name, duration and total must be in ONE local passage,
    # not cobbled together from unrelated sidebar articles or historical stats.
    snippets=[]
    for match in re.finditer(re.escape(player),main):
        if match.start()>6500:break
        s=main[max(0,match.start()-100):match.start()+250]
        if not (CONFIRM.search(s) and ('FA' in s or '자유계약' in s)) :continue
        if SPECULATIVE.search(s):continue
        t=parse_term(s);a=AMOUNT.search(s)
        if t is None or not a:continue
        value=float(a.group(1))
        if 0<value<=500:snippets.append((t,value))
    if not snippets:return None
    if len(set((str(x),y) for x,y in snippets))>1:return None
    years,total=snippets[0]
    # The official page's domain determines SIGNING club; supports transfers.
    return {'team':team,'years':years,'total':total,'date':published.isoformat(),
            'sources':[final], 'verification':'구단 공식 홈페이지 원문 확인'}

def official_links_from_index(index_url,team,players):
    raw,final=fetch(index_url,team)
    page=Page();page.feed(raw)
    links=[]
    for href,title in page.anchors:
        url=urllib.parse.urljoin(final,href)
        if host_ok(url,team) and any(n in title for n in players) and re.search('FA|계약|재계약',title):
            links.append(url)
    # Some club sites render links as JS routes rather than anchor elements.
    if team=='SSG':
        for idx in re.findall(r'(?:detail\?idx=|/detail/)(\d{3,8})',raw):
            links.append(f'https://www.ssglanders.com/media/news/detail?idx={idx}')
    return list(dict.fromkeys(links))[:25]

def search_links(team):
    # One query PER CLUB (not per player), to avoid excessive 503s and delays.
    q=f'site:{CLUBS[team]} "FA" "계약" 2026'
    url='https://www.bing.com/search?'+urllib.parse.urlencode({'q':q,'format':'rss'})
    raw,_=fetch(url)
    root=ET.fromstring(raw)
    links=[]
    for item in root.findall('./channel/item')[:30]:
        link=(item.findtext('link') or '').strip()
        if host_ok(link,team):links.append(link)
    return links

def main():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    unmatched=[p for p in data['players'] if not p.get('contract')]
    names={p['name'] for p in unmatched}
    errors=[];candidates=[];new=[]
    # Repair previously detected false-positive contract without suppressing future real news.
    for p in data['players']:
        c=p.get('contract') or {}
        if p['name']=='구자욱' and c.get('verification','').startswith('언론사 2곳'):
            p.pop('contract',None)
            if p not in unmatched:unmatched.append(p)
            names.add(p['name'])
            print('Removed unverified previous classification: 구자욱')
    by_team={team:[] for team in CLUBS}
    for p in unmatched:
        for team in CLUBS:by_team[team].append(p['name'])
    discovered={team:[] for team in CLUBS}
    for team,urls in INDEXES.items():
        for idx in urls:
            try:discovered[team]+=official_links_from_index(idx,team,names)
            except Exception as exc:errors.append({'player':'공식 발표 검색','team':team,'error':str(exc)[:160]})
    # Search indexes + first-party search links ONCE per team.
    discovery_errors=[]
    for team in CLUBS:
        try:discovered[team]+=search_links(team)
        except Exception as exc:discovery_errors.append({'team':team,'error':str(exc)[:160]})
        discovered[team]=list(dict.fromkeys(discovered[team]))[:35]
    if len(discovery_errors)>=len(CLUBS) and not any(discovered.values()):
        errors.append({'player':'공식 홈페이지 검색','error':'모든 구단 검색 경로 접속 실패'})
    # Fetch a club story once, reuse for all candidate players.
    official_hits={name:[] for name in names}
    for team,links in discovered.items():
        for url in links:
            for p in unmatched:
                try:
                    result=analyze_official(url,team,p['name'])
                    if result:official_hits[p['name']].append(result)
                except Exception as exc:
                    # Blocked pages are not proofs of contracts; record diagnostics only.
                    discovery_errors.append({'team':team,'error':str(exc)[:160]})
                    break
    for p in unmatched:
        name=p['name'];choices=official_hits.get(name,[])
        unique={(c['team'],str(c['years']),c['total']):c for c in choices}
        if len(unique)==1:
            contract=next(iter(unique.values()))
            p['contract']=contract
            new.append({'name':name,'from':p['team'],'to':contract['team'],
                        'years':contract['years'],'total':contract['total'],
                        'sources':contract['sources']})
            print('OFFICIAL VERIFIED:',name,contract['team'],contract['years'],contract['total'])
        elif unique:
            candidates.append({'player':name,'reason':'공식 페이지 간 정보 충돌 / 검토 필요',
                               'sources':[c['sources'][0] for c in unique.values()]})
    data['checked_at']=NOW.isoformat(timespec='seconds')
    if new:data['updated_at']=data['checked_at']
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Existing notify.py only uses new_contracts and errors; compatible schema.
    REVIEW.write_text(json.dumps({'checked_at':data['checked_at'],'new_contracts':new,
        'candidates':candidates,'errors':errors[:15], 'discovery_errors':discovery_errors[:30]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('New confirmed:',len(new),'Errors:',len(errors),'Discovery warnings:',len(discovery_errors),'Review:',len(candidates))

if __name__=='__main__':main()
