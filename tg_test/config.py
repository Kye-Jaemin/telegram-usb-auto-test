# -*- coding: utf-8 -*-
"""테스트 설정: 패키지명, 셀렉터 후보(한/영), 타이밍.

셀렉터는 기기/앱 버전/언어에 따라 달라질 수 있으므로 후보 리스트로 관리한다.
실제 화면과 안 맞으면 이 파일만 고치면 된다.
"""

# ── 기기 ──────────────────────────────────────────────────────────
DEVICE_SERIAL = None  # None이면 첫 번째 연결 기기 사용

# ── 패키지 ────────────────────────────────────────────────────────
PKG_TELEGRAM = "org.telegram.messenger"
# ExpressVPN
PKG_VPN = "com.expressvpn.vpn"
VPN_APP_NAME = "ExpressVPN"

# ── 타이밍(초) ────────────────────────────────────────────────────
T_APP_LAUNCH = 6      # 앱 실행 후 안정화 대기
T_UI_SETTLE = 1.5     # 화면 전환 대기
T_AIRPLANE_HOLD = 5   # 비행기모드 On 유지 시간
T_ELEMENT_WAIT = 12   # 엘리먼트 대기 타임아웃

# ── 텔레그램 로그인 상태 판별용 텍스트 후보 ────────────────────────
# 로그아웃 직후 인트로 화면의 강한 마커(계정화면 오탐 방지: '전화번호' 제외)
TG_LOGGED_OUT_TEXTS = [
    "시작하기", "Start Messaging", "메시지 보내기 시작",
]
# 전화번호 입력 화면(시작하기 이후) 마커
TG_NUMBER_SCREEN_TEXTS = [
    "내 전화번호", "전화번호", "Your Phone Number", "Phone Number", "국가", "Country",
]
# 재로그인용 국가코드/전화번호(로그아웃 후 번호가 비어있을 때만 사용하는 폴백)
# 이 폰 계정: 정경애 +82 10-7404-3537
TG_COUNTRY_CODE = "82"
TG_PHONE_NATIONAL = "1074043537"
# 번호 확인 다이얼로그 긍정 버튼(주의: '예'가 아니라 '네')
TG_NUMBER_CONFIRM_TEXTS = ["네", "예", "계속", "OK", "확인", "Yes", "Continue"]
# 로그인 완료 상태(채팅 목록)에서 나타나는 요소
TG_LOGGED_IN_TEXTS = [
    "채팅", "Chats",
]

# ── 셀렉터 후보(각 단계에서 사용) ─────────────────────────────────
# 메뉴(햄버거) 열기 desc 후보
TG_MENU_DESC = ["열기", "Open navigation menu", "메뉴", "Menu"]
# 설정 진입 텍스트
TG_SETTINGS_TEXTS = ["설정", "Settings"]
# 로그아웃 텍스트
TG_LOGOUT_TEXTS = ["로그아웃", "Log Out", "Log out"]
# 로그아웃 확인 다이얼로그의 확인 버튼
TG_LOGOUT_CONFIRM_TEXTS = ["로그아웃", "Log Out", "Log out", "확인", "OK", "예", "Yes"]
# '시작하기' 버튼
TG_START_TEXTS = ["시작하기", "Start Messaging", "메시지 보내기 시작"]

# ── 최종 메시지 발송(정상동작 확인) ───────────────────────────────
TG_TARGET_CONTACT = "뚱재민"   # 정확히 일치하는 대화 이름
TG_TEST_MESSAGE = "test"

# ── ExpressVPN ────────────────────────────────────────────────────
# 위치 변경 진입(선택된 위치 영역/버튼) 텍스트/desc 후보
VPN_CHANGE_LOCATION_TEXTS = [
    "선택된 위치 변경", "Change Location", "위치 변경", "Selected Location",
    "Choose Location", "VPN 위치", "위치", "변경", "Change",
]
# 미국 위치 텍스트 후보
VPN_USA_TEXTS = ["미국", "United States", "USA", "United States "]
# 한국 위치 텍스트 후보
VPN_KOREA_TEXTS = ["대한민국", "한국", "South Korea", "Korea"]
# 위치 검색창 힌트
VPN_SEARCH_TEXTS = ["검색", "Search", "국가 또는 지역 검색", "Search for country or region"]
# VPN 연결 성공 판별용 텍스트 후보
VPN_CONNECTED_TEXTS = ["보호 중", "Protected", "연결됨", "Connected", "연결 완료"]
# 평점/추천/기타 팝업 닫기 버튼 후보
VPN_DISMISS_TEXTS = ["나중에", "Later", "No thanks", "취소", "Cancel", "닫기", "다음에", "확인", "OK"]

# ── 스크린샷/결과 경로 ────────────────────────────────────────────
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
SHOTS_DIR = os.path.join(RESULTS_DIR, "screenshots")
RESULT_JSON = os.path.join(RESULTS_DIR, "result.json")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DOCS_SHOTS_DIR = os.path.join(DOCS_DIR, "screenshots")
