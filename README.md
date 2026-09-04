# 주식 타임머신 설치 안내

과거 한국 주식 데이터를 사용하지만 연도와 실제 날짜를 숨기고, 매일 한 거래일씩 자동 진행되는 학교용 모의투자대회입니다.

## 1. Supabase 무료 프로젝트 만들기

1. https://supabase.com 에 가입하고 새 프로젝트를 만듭니다.
2. 왼쪽 메뉴에서 SQL Editor를 열고 New query를 누릅니다.
3. 이 저장소의 schema.sql 전체를 복사해 붙여 넣고 Run을 누릅니다.
4. Project Settings의 API 메뉴에서 Project URL과 service_role key를 확인합니다.

주의: service_role 키는 GitHub 파일에 직접 적으면 안 됩니다.

## 2. GitHub에 파일 올리기

압축을 푼 뒤 안에 있는 파일을 rhkdqo1280-prog/stock-contest 저장소 최상단에 올립니다.
ZIP 파일 자체를 올리지 말고 GitHub 화면에서 app.py와 requirements.txt 등이 바로 보여야 합니다.

## 3. Streamlit에 배포하기

1. https://share.streamlit.io 에 GitHub 계정으로 로그인합니다.
2. Create app을 누릅니다.
3. Repository에는 rhkdqo1280-prog/stock-contest를 선택합니다.
4. Main file path는 app.py로 지정합니다.
5. Advanced settings의 Secrets에 아래 두 줄을 입력합니다.

SUPABASE_URL = "Supabase Project URL"
SUPABASE_SERVICE_KEY = "Supabase service_role key"

6. Deploy를 누릅니다.

## 주요 기능

- 교사는 관리 비밀번호만 입력하면 같은 비밀번호로 만든 대회 목록을 확인합니다.
- 학생 참가 코드는 자동 생성됩니다.
- 학생은 대회 코드, 학번, 이름, 개인 비밀번호로 참가하거나 다시 접속합니다.
- 가격은 한국시간 날짜가 바뀔 때 과거의 다음 거래일로 자동 진행됩니다.
- 교사는 학생별 학번, 이름, 자산, 수익률, 보유 종목과 거래 내역을 확인합니다.
- 시작 자금은 1,000만 원이며 수수료, 세금, 배당, 공매도는 제외합니다.

## 포함된 파일

- app.py: Streamlit 학생 및 교사 화면
- database.py: Supabase 연결
- market.py: 과거 한국 주가 불러오기
- schema.sql: 데이터베이스 표와 안전한 거래 함수
- requirements.txt: 필요한 프로그램
- .streamlit/secrets.toml.example: 비밀 설정 예시
