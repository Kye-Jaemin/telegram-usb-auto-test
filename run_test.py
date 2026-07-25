# -*- coding: utf-8 -*-
"""Telegram USB 자동화 테스트 실행 엔트리포인트.

사용법:
    python run_test.py [--serial R3CX10LL48E] [--push]

동작:
  - 연결된 안드로이드 기기에서 13단계 시나리오를 실행
  - results/history.json 에 이번 실행을 누적 집계(총 시도/성공/실패)
  - docs/index.html 대시보드 갱신(총 시도/성공/실패 실시간 표시)
  - 실패한 실행일 때만 실패 단계의 마스킹 스크린샷 + 로그를 docs/runs/<id>/ 에 게시
  - --push 지정 시 docs 변경을 git commit & push (GitHub Pages 자동 갱신)
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
        subprocess.run(["git", "-C", base, "add", "docs"], check=False)
        msg = f"test run {run_id}: {overall}"
        r = subprocess.run(["git", "-C", base, "commit", "-m", msg], capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" in (r.stdout + r.stderr):
            print("git: 변경 없음")
            return
        p = subprocess.run(["git", "-C", base, "push"], capture_output=True, text=True)
        print("git push:", "OK" if p.returncode == 0 else p.stderr.strip())
    except Exception as e:
        print("git push 건너뜀:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=None, help="adb 기기 시리얼")
    ap.add_argument("--push", action="store_true", help="실행 후 docs를 git push")
    args = ap.parse_args()

    t0 = time.time()
    dev = Device(serial=args.serial)
    model = dev.shell("getprop ro.product.model").strip()
    android = dev.shell("getprop ro.build.version.release").strip()
    run_at = time.strftime("%Y-%m-%d %H:%M:%S")
    run_id = time.strftime("%Y%m%d-%H%M%S")

    print("=== Telegram 자동화 테스트 시작 ===")
    print(f"기기: {model} ({dev.serial}), Android {android}, run_id={run_id}")

    runner = Runner(dev)
    results = runner.run_all()

    duration = round(time.time() - t0, 1)
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    last = max(results, key=lambda r: r["idx"]) if results else None
    overall = "PASS" if (n_fail == 0 and last and last["status"] == "PASS") else "FAIL"

    meta = {
        "run_id": run_id, "model": model, "serial": dev.serial, "android": android,
        "run_at": run_at, "duration": duration, "overall": overall,
    }

    # 누적 집계 + 실패 아티팩트(문제 시에만) + 대시보드 생성
    hist, run = report.append_run(meta, results)
    failure_arts = report.export_failure_artifacts(meta, results)
    out = report.build_dashboard(hist, run, failure_arts)

    tot = hist["totals"]
    print(f"\n=== 결과: {overall} (이번 실행 FAIL {n_fail}건) ===")
    print(f"누적: 총 시도 {tot['attempts']} / 성공 {tot['pass']} / 실패 {tot['fail']}")
    print(f"대시보드: {out}")

    if args.push:
        git_push_docs(run_id, overall)

    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
