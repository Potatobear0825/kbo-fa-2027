"""Conservative KBO FA 2027 tracker. Google News RSS titles are imperfect.
Auto-classifies same-club renewals and explicit destination transfers only if
>=2 independent publishers agree on player, destination, years and max total.
All ambiguities go to review.json; notifications are handled separately.
"""
import datetime as dt
import email.utils
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from zoneinfo import ZoneInfo

BASE = pathlib.Path(__file__).resolve().parent
DATA, REVIEW = BASE/'data.json', BASE/'review.json'
NOW = dt.datetime.now(ZoneInfo('Asia/Seoul'))
TEAM_ALIASES = {
    '삼성':['삼성'], 'KT':['KT'], 'KIA':['KIA','기아'], 'LG':['LG'],
    '두산':['두산'], 'SSG':['SSG'], 'NC':['NC'], '한화':['한화'],
    '롯데':['롯데'], '키움':['키움'],
}
CONFIRM = re.compile(r'(계약\s*(?:체결|완료|확정)|(?:잔류|이적)\s*(?:확정|계약)?|(?:에|와|과)\s*(?:\d+년\s*)?계약|FA\s*계약|입단\s*확정|계약)', re.I)
SPECULATIVE = re.compile(r'(가능성|전망|예상|유력|협상|제안|요구|설|관심|눈앞|임박|초읽기|근접|논의|추진|아직|부인|미계약|불발|백지화|오보|아니다|할까|\?)')
YEARS = re.compile(r'(\d+)\s*년')
MONEY = re.compile(r'(?:최대\s*|총액\s*|약\s*)?(\d+(?:\.\d+)?)\s*억\s*(?:원)?')
AMBIGUOUS_TERM = re.compile(r'\d+\s*\+\s*\d+\s*년|\d+\s*년\s*\+\s*\d+\s*년')


def team_mentions(title):
    out=[]
    for team, aliases in TEAM_ALIASES.items():
        for alias in aliases:
            if re.search(r'(?<![A-Za-z])'+re.escape(alias)+r'(?![A-Za-z])', title, re.I):
                out.append(team)
                break
    return out


def destination(title, original):
    """Explicit target only. Ambiguous headlines are deliberately reviewed."""
    mentions = team_mentions(title)
    if not mentions:
        return None
    # Prefer an explicitly marked new club when old and new teams appear.
    choices=[]
    for team, aliases in TEAM_ALIASES.items():
        for a in aliases:
            token = r'(?<![A-Za-z])'+re.escape(a)+r'(?![A-Za-z])'
            pattern = token+r'\s*(?:행|입단|으로\s*이적|에\s*입단|와\s*계약|과\s*계약|와\s*\d+년|과\s*\d+년)'
            if re.search(pattern, title, re.I):
                choices.append(team)
                break
    choices=list(dict.fromkeys(choices))
    if len(choices)==1:
        team=choices[0]
        if team != original and not re.search(r'이적|입단|행|새\s*둥지|유니폼', title):
            return None
        return team
    if len(choices)>1:
        return None
    # No target syntax: accept clear renewal ONLY with one club mentioned.
    if mentions == [original] and re.search(r'잔류|재계약', title) and not re.search(r'이적', title):
        return original
    return None


def fetch_rss(player):
    query=f'"{player}" (FA 계약 OR 이적 OR 잔류)'
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'ko','gl':'KR','ceid':'KR:ko'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; KBOFAWatcher/2.0)'})
    with urllib.request.urlopen(req,timeout=18) as response:
        root=ET.fromstring(response.read(1000000))
    result=[]
    for el in root.findall('./channel/item'):
        title=(el.findtext('title') or '').strip()
        source=el.find('source')
        publisher=((source.text if source is not None else '') or '').strip()
        link=(el.findtext('link') or '').strip()
        try: published=email.utils.parsedate_to_datetime(el.findtext('pubDate') or '').astimezone(NOW.tzinfo)
        except (ValueError,TypeError): continue
        if not (NOW-dt.timedelta(days=21) <= published <= NOW+dt.timedelta(hours=2)): continue
        result.append({'title':title,'publisher':publisher,'url':link,'published':published.isoformat()})
    return result


def candidate(item, player):
    title=item['title'].split(' - ')[0]
    if player['name'] not in title or not CONFIRM.search(title) or SPECULATIVE.search(title) or AMBIGUOUS_TERM.search(title):
        return None
    years=YEARS.findall(title); money=MONEY.findall(title)
    if len(years)!=1 or len(money)!=1: return None
    years,total=int(years[0]),float(money[0])
    if not (1<=years<=10 and 0<total<=500): return None
    team=destination(title,player['team'])
    if not team: return None
    if team != player['team'] and not re.search(r'이적|입단|행|새\s*둥지|유니폼',title):return None
    return {'years':years,'total':total,'team':team,'source':item}


def main():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    outstanding=[];errors=[];new_contracts=[]
    for player in data['players']:
        if player.get('contract'):continue
        try: items=fetch_rss(player['name'])
        except Exception as exc:
            errors.append({'player':player['name'],'error':str(exc)[:200]})
            continue
        groups=defaultdict(list)
        for item in items:
            heading=item['title'].split(' - ')[0]
            if player['name'] not in heading or not CONFIRM.search(heading) or SPECULATIVE.search(heading):continue
            found=candidate(item,player)
            if found:groups[(found['years'],found['total'],found['team'])].append(item)
            else:outstanding.append({'player':player['name'],'headline':item['title'],'publisher':item['publisher'],'url':item['url']})
        qualified=[]
        for key,sources in groups.items():
            publishers={s['publisher'].casefold() for s in sources if s['publisher']}
            if len(publishers)>=2: qualified.append((key,sources))
            else:
                for s in sources:
                    outstanding.append({'player':player['name'],'headline':s['title'],'publisher':s['publisher'],'url':s['url']})
        # Conflicting amounts/terms/teams = manual review even if both supported by 2 sources.
        if len(qualified)==1 and len(groups)==1:
            (years,total,team),sources=qualified[0]
            player['contract']={'team':team,'years':years,'total':total,
              'date':NOW.date().isoformat(),'sources':list(dict.fromkeys(s['url'] for s in sources))[:4],
              'verification':'언론사 2곳 제목 일치 · 자동 분류 (발표일 아님)'}
            new_contracts.append({'name':player['name'],'from':player['team'],'to':team,'years':years,'total':total,'sources':player['contract']['sources']})
            print('NEW CONTRACT:',player['name'],player['team'],'->',team,years,total)
        elif len(qualified)>1 or len(groups)>1:
            for sources in groups.values():
                for s in sources:
                    outstanding.append({'player':player['name'],'headline':s['title'],'publisher':s['publisher'],'url':s['url']})
        time.sleep(0.25)
    data['checked_at']=NOW.isoformat(timespec='seconds')
    if new_contracts:data['updated_at']=NOW.isoformat(timespec='seconds')
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Preserve candidate URLs so readers can check and correct classification.
    dedup={}
    for item in outstanding:
        dedup[(item['player'],item['url'])]=item
    REVIEW.write_text(json.dumps({'checked_at':data['checked_at'],'new_contracts':new_contracts,'candidates':list(dedup.values())[:120],'errors':errors},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Scanned {len(data['players'])} approved FAs. New:{len(new_contracts)} Review:{len(dedup)} Errors:{len(errors)}")

if __name__=='__main__': main()
