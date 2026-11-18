"""Optional Telegram alerts. Credentials only from GitHub Actions Secrets.
Use persistent state for de-duplication; do not acknowledge unsent messages.
"""
import hashlib
import json
import os
import pathlib
import urllib.parse
import urllib.request

BASE=pathlib.Path(__file__).resolve().parent
STATE=BASE/'alert_state.json'


def send(text):
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
    chat=os.getenv('TELEGRAM_CHAT_ID','').strip()
    if not token or not chat:
        print('Telegram credentials not set: alerts skipped.')
        return False
    url=f'https://api.telegram.org/bot{token}/sendMessage'
    payload=urllib.parse.urlencode({'chat_id':chat,'text':text[:3900],'disable_web_page_preview':'true'}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=payload,method='POST'),timeout=20) as response:
            result=json.load(response)
        if not result.get('ok'):raise ValueError('Telegram API rejected message')
        return True
    except Exception as e:
        print('Telegram delivery failed:',type(e).__name__)
        return False


def main():
    review=json.loads((BASE/'review.json').read_text(encoding='utf-8'))
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'notified':[]}
    seen=set(state.get('notified',[]))
    events=[]
    for c in review.get('new_contracts',[]):
        key='signed:'+c['name']+':'+c['to']+':'+str(c['total'])
        line=f"✅ 새 FA 계약 자동 분류: {c['name']}\n{c['from']} → {c['to']} / {c['years']}년 / {c['total']}억 원\n{(c.get('sources') or [''])[0]}\n※ 공식 확정이 아닌 언론 제목 교차검증"
        events.append((key,line))
    for c in review.get('candidates',[]):
        key='review:'+hashlib.sha256((c['player']+'|'+c.get('url','')).encode()).hexdigest()[:20]
        line=f"🔎 FA 계약 검토 필요: {c['player']}\n{c['headline'][:170]}\n{c.get('url','')}"
        events.append((key,line))
    if review.get('errors'):
        failed=', '.join(e['player'] for e in review['errors'])
        # Send once per set of affected players; won't spam every half-hour.
        key='error:'+hashlib.sha256(failed.encode()).hexdigest()[:16]
        events.append((key,f'⚠️ FA 뉴스 검색 오류\n대상: {failed}\nGitHub Actions 실행 기록과 review.json을 확인하세요.'))
    pending=[(k,v) for k,v in events if k not in seen]
    sent=0
    # Limit 10 per run; remaining events will be retried on the next run.
    for key,message in pending[:10]:
        if send(message):
            seen.add(key);sent+=1
        else:
            break
    state['notified']=sorted(seen)[-2000:]
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Notifications delivered: {sent}; pending: {len(pending)-sent}')

if __name__=='__main__':main()
