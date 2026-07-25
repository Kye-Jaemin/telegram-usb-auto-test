# -*- coding: utf-8 -*-
"""쿨다운 대기 후 자동 재개 + 쿨다운 실패 로깅.

- 로그인 즉시 시도. 쿨다운('너무 많이 시도')이면:
    * 쿨다운 화면을 덤프에 저장(스크린샷+logcat)
    * 대시보드에 'FAIL' 회차로 기록·푸시
    * RETRY_SEC 대기 후 재시도
- 로그인 성공 시: (best-effort) 디버그 로그 활성화 → 14단계 루프를 TARGET까지 재개
- 회차 사이 로그아웃/쿨다운이면 재로그인·(쿨다운 기록)·대기 후 진행
"""
import os
import sys
import time
import shutil

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from tg_test.device import Device
from tg_test import config, report
import run_test
import subprocess

SERIAL = "R3KL406KDQV"
TARGET = 300
RETRY_SEC = 1200      # 쿨다운 재시도 간격(20분)
MAX_WAIT = 24         # 최대 대기 사이클


def logged_in(d):
    return d(text="연락처").exists or d(textContains="대화 검색").exists or d(text="프로필").exists


def _push():
    try:
        base = config.BASE_DIR
        subprocess.run(["git", "-C", base, "add", "docs"], capture_output=True, text=True)
        subprocess.run(["git", "-C", base, "commit", "-m", "cooldown 실패 기록"], capture_output=True, text=True)
        subprocess.run(["git", "-C", base, "push"], capture_output=True, text=True)
    except Exception:
        pass


def record_cooldown_failure(dev):
    """쿨다운 화면을 덤프에 저장하고 대시보드에 FAIL 회차로 기록·푸시."""
    d = dev.d
    ts = time.strftime("%Y%m%d-%H%M%S")
    dump_dir = os.path.join(config.DUMPS_DIR, f"cooldown-{ts}")
    os.makedirs(dump_dir, exist_ok=True)
    try:
        d.screenshot(os.path.join(dump_dir, "cooldown.png"))
        open(os.path.join(dump_dir, "logcat.txt"), "w", encoding="utf-8").write(dev.logcat_snapshot(2000))
    except Exception:
        pass
    # 대시보드용 실패 아티팩트(마스킹 스크린샷은 step07.png 기준으로 export)
    try:
        os.makedirs(config.SHOTS_DIR, exist_ok=True)
        src = os.path.join(dump_dir, "cooldown.png")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(config.SHOTS_DIR, "step07.png"))
    except Exception:
        pass
    results = [
        {"idx": 7, "title": "로그인 확인",
         "status": "FAIL",
         "detail": "flood 쿨다운: '너무 많이 시도하셨습니다. 나중에 다시 시도하세요' 로 로그인 차단",
         "screenshot": "screenshots/step07.png", "dump": os.path.join(dump_dir, "logcat.txt"),
         "ts": time.strftime("%H:%M:%S")},
    ]
    meta = {"run_id": ts, "model": "SM-F971N", "serial": SERIAL, "android": "17",
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "duration": 0.0, "overall": "FAIL"}
    try:
        hist, run = report.append_run(meta, results)
        arts = report.export_failure_artifacts(meta, results)
        report.build_dashboard(hist, run, arts)
        _push()
        print(f"[resume] 쿨다운 실패 기록됨(run_id={ts}) 누적 {hist['totals']}", flush=True)
    except Exception as ex:
        print(f"[resume] 쿨다운 기록 예외: {ex}", flush=True)


def try_login(dev):
    """로그인 1회 시도. (성공?, 사유) 반환. 쿨다운이면 기록도 수행."""
    d = dev.d
    dev.unlock()
    d.app_start(config.PKG_TELEGRAM, stop=True, use_monkey=True)
    time.sleep(5)
    if logged_in(d):
        return True, "already"
    d(textContains="시작하기").click_exists(timeout=5)
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
    d.click(int(W * 0.90), int(H * 0.58)); time.sleep(3)
    d(text="네").click_exists(timeout=4); time.sleep(5)
    xml = d.dump_hierarchy()
    if any(k in xml for k in ["너무 많이", "나중에 다시", "죄송합니다"]):
        record_cooldown_failure(dev)          # ← 쿨다운 실패 로깅/저장
        d(text="확인").click_exists(timeout=3)
        return False, "cooldown"
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


def attempts():
    return report.load_history()["totals"]["attempts"]


def ensure_login(dev):
    """로그인 확보. 쿨다운이면 기록·대기 반복. 성공 시 True."""
    for _ in range(MAX_WAIT):
        ok, how = try_login(dev)
        print(f"[resume] 로그인 시도: {ok} ({how})", flush=True)
        if ok:
            return True
        if how == "cooldown":
            print(f"[resume] 쿨다운 — {RETRY_SEC}s 대기", flush=True)
            time.sleep(RETRY_SEC)
            dev.__init__(serial=SERIAL)  # 재연결
        else:
            time.sleep(30)
    return False


def main():
    print("[resume] 시작 — 즉시 로그인 확인", flush=True)
    dev = Device(serial=SERIAL)
    if not logged_in(dev.d):
        if not ensure_login(dev):
            print("[resume] 로그인 실패 — 재개 중단", flush=True)
            return 1
    # 디버그 로그 best-effort 활성화
    try:
        el = dev.enable_telegram_debug_logs()
        print(f"[resume] 디버그 로그 활성화: {el}", flush=True)
    except Exception:
        pass

    print(f"[resume] 루프 재개 (누적 {attempts()} → 목표 {TARGET})", flush=True)
    i = 0
    while attempts() < TARGET:
        dev = Device(serial=SERIAL)
        if not logged_in(dev.d):
            if not ensure_login(dev):
                print("[resume] 재로그인 실패 — 중단", flush=True)
                break
        i += 1
        try:
            run_test.run_once(SERIAL, i, TARGET, push=True)
        except Exception as ex:
            print(f"[resume] run_once 예외: {ex}", flush=True)
        time.sleep(3)
    print(f"[resume] 종료. 누적 {attempts()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
