# 2027 KBO FA 자동 업데이트 사이트 — 초보자 설치 설명서

이 폴더의 파일을 GitHub에 올리면 **약 30분 간격**으로 Google News RSS의 새 기사 제목을 검색합니다. 원소속팀 잔류와 타 구단 이적 모두 자동 분류하지만 **서로 다른 언론사 2곳 이상이 선수·계약 구단·계약 기간·최대 총액을 같은 내용으로 보도한 경우만** 계약란에 반영합니다. 불분명한 기사는 `review.json`에 남깁니다. 이 기준은 **언론 기사 교차검증**이지 구단 공식 발표를 확인했다는 의미가 아닙니다.

> 주의: 뉴스 제목 검색에는 누락·오보·잘못된 분류 가능성이 있습니다. 선수 이름이 같은 동명이인, 제목에 포함되지 않은 조건부 옵션, 기사 제목 수정에 따른 오류가 있을 수 있습니다. 중요한 계약 정보는 반드시 구단 공식 발표를 수동으로 대조하세요.

## 1. 들어 있는 파일

- `index.html`: 공개 웹사이트 화면
- `data.json`: FA 승인 선수 22명과 현재 확인 계약 (2026-11-18 초기 데이터)
- `update_fa.py`: 30분마다 새 계약 후보 수집·검증·자동 기록
- `notify.py`: 텔레그램으로 새 계약/검토 필요/검색 오류 알림
- `alert_state.json`: 같은 기사의 반복 알림 방지
- `review.json`: 검토가 필요한 기사 목록
- `test_telegram.py`: 텔레그램 연결 테스트
- `.github/workflows/update.yml`: 예약 실행 설정 (이 경로가 매우 중요)

## 2. GitHub 가입·사이트 파일 올리기

1. PC 브라우저에서 https://github.com/signup 접속 → 무료 계정 생성.
2. https://github.com/new 접속 → `Repository name`에 `kbo-fa-2027` 입력 → `Public` 선택 → `Create repository`.
3. 제공 ZIP 파일을 **압축 해제**하세요. ZIP 자체를 업로드하면 안 됩니다.
4. 저장소에서 `Add file` → `Upload files`로 파일 업로드: `index.html`, `data.json`, `update_fa.py`, `notify.py`, `test_telegram.py`, `alert_state.json`, `review.json`, `README.md`.
5. **`.github/workflows/update.yml`은 GitHub 웹사이트에서 따로 생성하는 것이 쉽습니다.** 저장소 `Add file` → `Create new file` → 파일 이름을 `.github/workflows/update.yml`로 입력 → ZIP에 포함된 동일 파일 내용을 붙여넣기 → `Commit changes`.
6. 확인: 저장소 첫 화면에 `index.html`이 있고, `.github` 폴더 안에 `workflows/update.yml`이 있어야 합니다.

## 3. 공개 사이트 켜기

1. 저장소 상단 `Settings` → 왼쪽 `Pages`.
2. `Build and deployment`: `Source` = `Deploy from a branch`.
3. `Branch` = `main`, 폴더 = `/(root)` → `Save`.
4. 몇 분 뒤 `https://사용자아이디.github.io/kbo-fa-2027/` 에 접속. 실제 아이디로 바꾸세요.

## 4. 예약 실행 켜기

1. 저장소 `Settings` → `Actions` → `General` → `Workflow permissions`에서 `Read and write permissions` 선택 → `Save`. (관리 권한이 있어야 변경 가능)
2. 저장소 `Actions` → `KBO FA 30-minute update` → `Run workflow` → `Run workflow`.
3. 생성된 실행을 클릭한 뒤 `check` 작업에 초록 체크가 뜨면 정상입니다. `data.json`의 `checked_at`이 바뀌면 실행 증거입니다.
4. `schedule` 항목은 UTC 기준 매시 **07분/37분**에 예약되어 있으며 한국 시간에도 매시 **07분/37분**에 해당합니다. 실제 시작은 밀리거나 누락될 수 있습니다.

## 5. 텔레그램 알림 연결하기 (선택, 추천)

1. 스마트폰에 Telegram 앱 설치 → 가입 및 로그인.
2. 텔레그램 검색에서 **공식 `@BotFather`** 대화 열기 → `/newbot` 입력 → 원하는 봇 이름과 `bot`으로 끝나는 사용자 이름 입력.
3. BotFather가 반환한 **API token**을 복사해서 개인적으로 보관. **토큰을 공개 파일이나 채팅에 공유하지 마세요.**
4. 방금 생성된 내 봇을 텔레그램에서 열고 `Start`를 누른 후 `안녕` 메시지를 보냅니다.
5. **자신의 브라우저** 주소창에 아래 주소를 입력하세요. `내봇토큰` 부분은 실제 토큰으로 교체합니다.

   `https://api.telegram.org/bot내봇토큰/getUpdates`

   JSON 응답의 `result` 배열에서 `message` → `chat` → `id` 숫자를 찾습니다. 예시: `"chat":{"id":123456789,...}`이면 채팅 ID는 `123456789`입니다. 비어 있으면 봇에게 새 메시지를 보내고 다시 접속합니다. 이 주소에는 토큰이 포함되므로 남에게 전달하지 마세요.
6. GitHub 저장소에서 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`.
7. 첫 번째 저장: Name `TELEGRAM_BOT_TOKEN`, Secret = 내 봇 토큰.
8. 두 번째 저장: Name `TELEGRAM_CHAT_ID`, Secret = 위에서 확인한 채팅 ID.
9. 저장소 `Actions` → 워크플로를 다시 `Run workflow`. `notify.py`는 새 소식이 있어야 메시지를 보내므로, 초기 실행 후 텔레그램 알림이 바로 오지 않을 수도 있습니다. 실제 발송 테스트는 아래 항목 참고.

### 알림만 테스트하려면

GitHub `Actions` → `KBO FA 30-minute update` → `Run workflow`에서 **`telegram_test` 체크박스**를 켜고 실행하세요. 설정이 맞다면 실제 계약과 무관하게 텔레그램으로 **“알림 연결 테스트 성공!”**이라는 메시지가 옵니다. 보안상 토큰을 웹사이트나 공개 파일에 입력할 필요가 없습니다.

## 6. 알림 메시지 종류

- ✅ 새 잔류·이적 계약이 두 언론사 제목에서 일치 → 사이트 자동 반영과 동시에 알림.
- 🔎 출처가 부족하거나 기사 내용이 모호함 → 수동 검토 알림. 사이트 `review.json` 확인.
- ⚠️ 검색 실패 → 오류 알림.

동일한 기사 URL은 `alert_state.json`에 기록해 중복 알림을 막습니다. 단, 기사 URL이 변경되거나 실패 선수 집합이 달라지면 새로운 알림이 올 수 있습니다. 알림이 도착해도 **'공식 발표 확정'이라는 의미는 아닙니다.**

## 7. 자주 발생하는 문제

- `404`: Pages 배포 대기, 저장소 이름/주소/브랜치 설정을 확인.
- `데이터 로드 실패`: HTML을 PC에서 직접 여는 대신 Pages 주소로 열기.
- `Permission denied` / `403`: 저장소 Actions의 읽기·쓰기 권한 확인.
- 예약 실행 안 됨: `.github/workflows/update.yml` 경로, Actions 활성화 상태 확인. GitHub는 공개 저장소에서 60일간 활동이 없으면 예약 워크플로를 비활성화할 수 있습니다.
- 텔레그램이 안 옴: 봇에게 Start 했는지, `getUpdates`의 chat ID 및 두 Secret 이름에 오타 없는지 확인. 새 소식이 없으면 알림도 없습니다.
- 언론 제목과 실제 계약이 다름: `data.json`에서 해당 선수의 `contract`를 수동 수정하거나 삭제하고 `Commit changes`하면 됩니다.

## 기술 및 운영 한계

- 외부 API 및 뉴스 제공 서비스의 접근 정책이 변경될 수 있습니다.
- 30분 실행은 '검색 주기'이며, 계약 발표 후 반드시 30분 안에 업데이트된다는 보장은 없습니다.
- 기사 제목에 기간과 금액 중 하나라도 없으면 자동 기록하지 않습니다.
- 다른 언론사가 같은 최초 보도를 전재하는 경우까지 완벽하게 구별하진 못합니다.
- 자동 계약 확인일은 실제 계약 발표일과 다를 수 있습니다.
- 알림 봇 토큰은 GitHub **Secrets**에서만 보관해야 하며 공개 저장소에 입력하면 안 됩니다.
