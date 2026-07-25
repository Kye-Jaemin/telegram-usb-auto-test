# -*- coding: utf-8 -*-
"""Telegram USB 자동화 테스트 실행 엔트리포인트.

사용법:
    python run_test.py [--serial R3KL406KDQV] [--repeat N] [--push]

동작:
  - 연결된 안드로이드 기기에서 14단계 시나리오를 실행
  - --repeat N: N회 반복(각 회차마다 집계·대시보드·(옵션)푸시)
  - results/history.json 에 누적 집계(총 시도/성공/실패)
  - docs/index.html 대시보드 갱신
  - 실패한 회차만 실패 단계의 마스킹 스크린샷 + 로그를 docs/runs/<id>/ 에 게시
  - --push 지정 시 매 회차 docs를 git commit & push (GitHub Pages 자동 갱신)
"""
import sys
import time
import argparse
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from tg_test.device import Device
from tg_test.steps import Runner
from tg_test import report, config


def git_push_docs(run_id, overall):
    """docs 변경사항을 커밋 & 푸시. 저장소/원격이 없으면 조용히 건너뜀."""
    try:
        base = config.BASE_DIR
        subprocess.run(["git", "-C", base, "add", "docs"], check=False,
                       capture_output=True, text=True)
        msg = f"run {run_id}: {overall}"
        r = subprocess.run(["git", "-C", base, "commit", "-m", msg],
                           capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" in (r.stdout + r.stderr):
            return
        p = subprocess.run(["git", "-C", base, "push"], capture_output=True, text=True)
        print("  git push:", "OK" if p.returncode == 0 else p.stderr.strip()[:120])
    except Exception as e:
        print("  git push 건너뜀:", e)


def run_once(serial, iteration, total, push):
    t0 = time.time()
    dev = Device(serial=serial)
    model = dev.shell("getprop ro.product.model").strip()
    android = dev.shell("getprop ro.build.version.release").strip()
    run_at = time.strftime("%Y-%m-%d %H:%M:%S")
    run_id = time.strftime("%Y%m%d-%H%M%S")

    print(f"\n===== [{iteration}/{total}] 시작 {run_at} · {model} ({dev.serial}) run_id={run_id} =====")
    dev.logcat_clear()  # 이번 회차 로그만 남도록 초기화
    runner = Runner(dev, run_id=run_id)
    results = runner.run_all()

    duration = round(time.time() - t0, 1)
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    last = max(results, key=lambda r: r["idx"]) if results else None
    overall = "PASS" if (n_fail == 0 and last and last["status"] == "PASS") else "FAIL"

    meta = {
        "run_id": run_id, "model": model, "serial": dev.serial, "android": android,
        "run_at": run_at, "duration": duration, "overall": overall,
    }
    hist, run = report.append_run(meta, results)
    failure_arts = report.export_failure_artifacts(meta, results)
    report.build_dashboard(hist, run, failure_arts)

    tot = hist["totals"]
    print(f"----- [{iteration}/{total}] {overall} · {duration}s · "
          f"누적 시도 {tot['attempts']} / 성공 {tot['pass']} / 실패 {tot['fail']} -----")
    if push:
        git_push_docs(run_id, overall)
    return overall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=None, help="adb 기기 시리얼")
    ap.add_argument("--repeat", type=int, default=1, help="반복 횟수")
    ap.add_argument("--push", action="store_true", help="매 회차 docs를 git push")
    ap.add_argument("--gap", type=float, default=3.0, help="회차 간 대기(초)")
    args = ap.parse_args()

    last_overall = "PASS"
    for i in range(1, args.repeat + 1):
        try:
            last_overall = run_once(args.serial, i, args.repeat, args.push)
        except Exception as e:
            print(f"[{i}/{args.repeat}] 회차 예외: {e}")
        if i < args.repeat:
            time.sleep(args.gap)

    return 0 if last_overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
