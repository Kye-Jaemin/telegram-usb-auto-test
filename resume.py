# -*- coding: utf-8 -*-
"""쿨다운 대기 후 자동 재개.

- 로그인 시도 → 쿨다운('너무 많이 시도')이면 대기 후 재시도(백오프 없이 고정 간격)
- 로그인 성공 시: (best-effort) 텔레그램 디버그 로그 활성화 → 14단계 루프를 TARGET까지 재개
- 매 회차 대시보드 갱신·푸시. 회차 사이 로그아웃 상태/쿨다운이면 재로그인·대기 후 진행.
"""
import sys
import time
import re

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from tg_test.device import Device
from tg_test import config, report
import run_test

SERIAL = "R3KL406KDQV"
TARGET = 300
RETRY_SEC = 1200      # 쿨다운 재시도 간격(20분)
MAX_WAIT = 24         # 최대 대기 사이클(약 8시간)


def logged_in(d):
    return d(text="연락처").exists or d(textContains="대화 검색").exists or d(text="프로필").exists


def try_login(dev):
    """로그인 1회 시도. (성공?, 사유) 반환."""
    d = dev.d
    dev.unlock()
    d.app_start(config.PKG_TELEGRAM, stop=True, use_monkey=True)
    time.sleep(5)
    if logged_in(d):
        return True, "already"
    if not d(textContains="시작하기").click_exists(timeout=5):
        # 이미 번호화면일 수도
        pass
    time.sleep(3)
    W, H = d.window_size()
    e = d(className="android.widget.EditText")
    if e.count >= 2:
        cc = e[0]
        if (cc.get_text() or "").strip() != "82":
            cc.click(); time.sleep(0.3); cc.clear_text(); cc.set_text("82")
        time.sleep(0.4)
        num = d(className="android.widget.EditText")[1]
        num.click(); time.sleep(0.3); num.clear_text(); time.sleep(0.4)
        num.set_text(config.TG_PHONE_NATIONAL); time.sleep(0.5)
    d.click(int(W * 0.90), int(H * 0.58)); time.sleep(3)   # 화살표
    d(text="네").click_exists(timeout=4); time.sleep(5)
    # 쿨다운?
    xml = d.dump_hierarchy()
    if any(k in xml for k in ["너무 많이", "나중에 다시", "죄송합니다"]):
        d(text="확인").click_exists(timeout=3)
        return False, "cooldown"
    # 이메일 인증 → Google SSO
    if any(k in xml for k in ["이메일을 확인", "Google 계정으로 로그인", "이메일로 로그인"]):
        d(textContains="Google 계정으로 로그인").click_exists(timeout=4); time.sleep(4)
        if not d(text=config.TG_GOOGLE_ACCOUNT_NAME).click_exists(timeout=5):
            d(textContains=config.TG_GOOGLE_ACCOUNT_EMAIL).click_exists(timeout=3)
        time.sleep(6)
        for t in config.TG_SSO_CONSENT_TEXTS:
            if d(text=t).exists:
                d(text=t).click(); break
        time.sleep(6)
    for _ in range(15):
        if logged_in(d):
            return True, "sms/sso"
        time.sleep(3)
    return False, "timeout"


def enable_debug_logs(dev):
    """best-effort: 설정 하단 버전 여러 번 탭 → 로그 활성화."""
    d = dev.d
    try:
        d(text="설정").click_exists(timeout=5); time.sleep(1.5)
        for _ in range(9):
            d.swipe_ext("up", scale=0.85); time.sleep(0.3)
        xml = d.dump_hierarchy()
        cands = [t for t in re.findall(r'text="([^"]+)"', xml)
                 if ("Telegram" in t) or re.search(r"\bv?\d+\.\d+", t)]
        if not cands:
            return False
        el = d(text=cands[-1])
        for _ in range(10):
            el.click(); time.sleep(0.15)
        time.sleep(1)
        for t in ["로그 활성화", "Enable Logs", "Enable logs", "디버그 로그 활성화", "로깅 사용"]:
            if d(text=t).click_exists(timeout=1):
                return True
        return False
    except Exception:
        return False


def attempts():
    return report.load_history()["totals"]["attempts"]


def main():
    print("[resume] 쿨다운 대기 후 재개 시작", flush=True)
    logged = False
    for w in range(MAX_WAIT):
        print(f"[resume] {RETRY_SEC}s 대기 후 로그인 시도 ({w+1}/{MAX_WAIT})", flush=True)
        time.sleep(RETRY_SEC)
        dev = Device(serial=SERIAL)
        ok, how = try_login(dev)
        print(f"[resume] 로그인 결과: {ok} ({how})", flush=True)
        if ok:
            logged = True
            el = enable_debug_logs(dev)
            print(f"[resume] 디버그 로그 활성화: {el}", flush=True)
            break
    if not logged:
        print("[resume] 대기 한도 내 로그인 실패 — 재개 중단", flush=True)
        return 1

    print(f"[resume] 로그인 성공 → 루프 재개 (현재 누적 {attempts()} → 목표 {TARGET})", flush=True)
    i = 0
    while attempts() < TARGET:
        # 회차 시작 전 로그인/쿨다운 보정
        dev = Device(serial=SERIAL)
        if not logged_in(dev.d):
            ok, how = try_login(dev)
            if not ok:
                if how == "cooldown":
                    print(f"[resume] 쿨다운 재발 — {RETRY_SEC}s 대기", flush=True)
                    time.sleep(RETRY_SEC)
                    continue
        i += 1
        try:
            run_test.run_once(SERIAL, i, TARGET, push=True)
        except Exception as ex:
            print(f"[resume] run_once 예외: {ex}", flush=True)
        time.sleep(3)
    print(f"[resume] 목표 도달! 누적 {attempts()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
