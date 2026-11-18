"""Manual-only delivery check: python test_telegram.py, with env vars set."""
from notify import send
if __name__=='__main__':
    if not send('✅ 2027 KBO FA 알림 연결 테스트 성공!\n이 메시지는 실제 계약 소식이 아닌 테스트입니다.'):
        raise SystemExit('Telegram test not sent: check secrets and bot Start.')
    print('Telegram test delivered.')
