# -*- coding: utf-8 -*-
"""기기 제어 헬퍼: uiautomator2 연결, adb 명령, 스크린샷, 요소 탐색, 비행기모드."""
import os
import time
import subprocess

import uiautomator2 as u2

from . import config


class Device:
    def __init__(self, serial=None):
        self.serial = serial or config.DEVICE_SERIAL
        self.d = u2.connect(self.serial) if self.serial else u2.connect()
        # 실제 시리얼 확정
        self.serial = self.d.serial
        # 화면 해상도(좌표 비율 계산용) — 기기마다 다름
        try:
            self.w, self.h = self.d.window_size()
        except Exception:
            self.w, self.h = 1080, 2340
        os.makedirs(config.SHOTS_DIR, exist_ok=True)
        # USB 연결 중 화면 항상 켜짐(자동잠금 방지) — 자동화 안정화
        try:
            self.shell("svc power stayon usb")
        except Exception:
            pass

    def tap_ratio(self, rx, ry):
        """화면 비율(0~1)로 좌표 탭 — 해상도 독립."""
        self.d.click(int(self.w * rx), int(self.h * ry))

    # ── adb ───────────────────────────────────────────────────────
    def adb(self, *args, timeout=30):
        cmd = ["adb", "-s", self.serial, *args]
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

    def shell(self, cmd, timeout=30):
        rc, out, err = self.adb("shell", cmd, timeout=timeout)
        return out if rc == 0 else (out + err)

    def logcat_snapshot(self, lines=5000):
        """현재 logcat 버퍼 스냅샷(최근 N줄)을 문자열로 반환."""
        rc, out, err = self.adb("logcat", "-d", "-v", "time", "-t", str(lines), timeout=60)
        return out if rc == 0 else (out + "\n" + err)

    def logcat_clear(self):
        try:
            self.adb("logcat", "-c", timeout=15)
        except Exception:
            pass

    def telegram_debug_logs_enabled(self):
        """텔레그램 디버그 로그 폴더에 파일이 있으면 활성화된 것으로 간주."""
        logdir = "/sdcard/Android/data/org.telegram.messenger/files/logs"
        rc, out, err = self.adb("shell", "ls", logdir, timeout=15)
        return rc == 0 and bool(out.strip()) and "No such" not in (out + err)

    def enable_telegram_debug_logs(self):
        """best-effort: 텔레그램 설정 하단 버전 여러 번 탭 → 디버그 메뉴 → 로그 활성화.
        성공 추정 시 True. (UI가 버전마다 달라 실패할 수 있음)"""
        import re
        d = self.d
        try:
            # 설정 탭
            if not (d(text="설정").click_exists(timeout=4) or d(text="Settings").click_exists(timeout=2)):
                return False
            time.sleep(1.5)
            # 하단으로 스크롤
            for _ in range(10):
                d.swipe_ext("up", scale=0.85)
                time.sleep(0.25)
            xml = d.dump_hierarchy()
            cands = [t for t in re.findall(r'text="([^"]+)"', xml)
                     if ("Telegram" in t) or re.search(r"\bv?\d+\.\d+(\.\d+)?", t)]
            if not cands:
                return False
            el = d(text=cands[-1])
            if not el.exists:
                return False
            for _ in range(12):
                el.click(); time.sleep(0.15)
            time.sleep(1)
            # 디버그 메뉴에서 로그 활성화
            for t in ["로그 활성화", "Enable Logs", "Enable logs", "디버그 로그 활성화", "로깅 사용", "로그 사용"]:
                if d(text=t).click_exists(timeout=1):
                    time.sleep(1)
                    return True
            return False
        except Exception:
            return False

    def pull_telegram_logs(self, dest_dir, count=2):
        """텔레그램 내부 디버그 로그(활성화된 경우) 최신 파일을 dest_dir로 pull.
        디버그 로그 미활성/폴더 없음 시 None. 반환: 받은 파일 경로 리스트."""
        import os
        logdir = "/sdcard/Android/data/org.telegram.messenger/files/logs"
        rc, out, err = self.adb("shell", "ls", "-t", logdir, timeout=15)
        if rc != 0 or not out.strip() or "No such" in (out + err):
            return []
        files = [x.strip() for x in out.strip().splitlines() if x.strip()][:count]
        pulled = []
        for name in files:
            dst = os.path.join(dest_dir, f"tglog_{name}")
            r, _, _ = self.adb("pull", f"{logdir}/{name}", dst, timeout=60)
            if r == 0:
                pulled.append(dst)
        return pulled

    # ── 스크린샷 ──────────────────────────────────────────────────
    def screenshot(self, name):
        path = os.path.join(config.SHOTS_DIR, f"{name}.png")
        try:
            self.d.screenshot(path)
        except Exception:
            # fallback: adb screencap
            self.adb("exec-out", "screencap", "-p", timeout=30)
        return path

    # ── 앱 제어 ───────────────────────────────────────────────────
    def app_start(self, pkg, stop=False):
        self.d.app_start(pkg, stop=stop, use_monkey=True)

    def app_stop(self, pkg):
        self.d.app_stop(pkg)

    def current_pkg(self):
        try:
            return self.d.app_current().get("package")
        except Exception:
            return None

    # ── 요소 탐색(여러 후보 텍스트/desc) ──────────────────────────
    def find_by_texts(self, texts, timeout=None, partial=True):
        """텍스트 후보 리스트 중 먼저 보이는 엘리먼트를 반환. 없으면 None."""
        timeout = config.T_ELEMENT_WAIT if timeout is None else timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            for t in texts:
                el = self.d(text=t)
                if el.exists:
                    return el
                if partial:
                    el = self.d(textContains=t)
                    if el.exists:
                        return el
                el = self.d(description=t)
                if el.exists:
                    return el
                if partial:
                    el = self.d(descriptionContains=t)
                    if el.exists:
                        return el
            time.sleep(0.6)
        return None

    def exists_any_text(self, texts, timeout=3):
        return self.find_by_texts(texts, timeout=timeout) is not None

    def tap_texts(self, texts, timeout=None, partial=True):
        el = self.find_by_texts(texts, timeout=timeout, partial=partial)
        if el is None:
            return False
        el.click()
        return True

    def tap_desc(self, descs, timeout=None):
        timeout = config.T_ELEMENT_WAIT if timeout is None else timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            for de in descs:
                el = self.d(description=de)
                if el.exists:
                    el.click()
                    return True
                el = self.d(descriptionContains=de)
                if el.exists:
                    el.click()
                    return True
            time.sleep(0.5)
        return False

    def tap_bottom_most_text(self, texts):
        """동일 텍스트가 여러 개일 때 화면상 가장 아래(=버튼)를 탭."""
        best = None
        best_y = -1
        for t in texts:
            sel = self.d(text=t)
            n = sel.count
            for i in range(n):
                try:
                    b = sel[i].info["bounds"]
                    cy = (b["top"] + b["bottom"]) / 2
                    if cy > best_y:
                        best_y = cy
                        best = sel[i]
                except Exception:
                    continue
        if best is not None:
            best.click()
            return True
        return False

    def tap_confirm(self, texts):
        """다이얼로그 긍정 버튼을 탭. 동일 텍스트 다수일 때 '클릭가능 & 가장 오른쪽'을 선택.

        일반적으로 확인/로그아웃 등 긍정 버튼은 다이얼로그 우측 하단에 위치한다.
        """
        clickable = []
        allmatch = []
        for t in texts:
            sel = self.d(text=t)
            for i in range(sel.count):
                try:
                    info = sel[i].info
                    b = info["bounds"]
                    cx = (b["left"] + b["right"]) / 2
                    cy = (b["top"] + b["bottom"]) / 2
                    allmatch.append((cx, cy, sel[i]))
                    if info.get("clickable", False):
                        clickable.append((cx, cy, sel[i]))
                except Exception:
                    continue
        pool = clickable if clickable else allmatch
        if not pool:
            return False
        # 긍정 버튼은 다이얼로그 우측에 위치 → 가장 오른쪽 요소 선택
        target = max(pool, key=lambda p: p[0])[2]
        target.click()
        return True

    def tap_coord_of(self, element, side="right"):
        """엘리먼트의 좌표를 직접 탭(커스텀 뷰의 접근성 클릭 미동작 대비).
        side='right'면 우측(전송버튼 등), 'center'면 중앙."""
        try:
            b = element.info["bounds"]
            h = b["bottom"] - b["top"]
            cy = int((b["top"] + b["bottom"]) / 2)
            if side == "right":
                cx = int(b["right"] - h * 0.5)
            else:
                cx = int((b["left"] + b["right"]) / 2)
            self.d.click(cx, cy)
            return True
        except Exception:
            return False

    def scroll_find_text(self, texts, max_swipes=8, partial=True):
        """스크롤하며 텍스트 후보를 찾아 탭. 성공 시 True."""
        for _ in range(max_swipes):
            el = self.find_by_texts(texts, timeout=1.5, partial=partial)
            if el is not None:
                el.click()
                return True
            self.d.swipe_ext("up", scale=0.7)
            time.sleep(0.6)
        # 마지막 한 번 더
        el = self.find_by_texts(texts, timeout=1.5, partial=partial)
        if el is not None:
            el.click()
            return True
        return False

    # ── 비행기모드 ────────────────────────────────────────────────
    def airplane_is_on(self):
        out = self.shell("settings get global airplane_mode_on")
        return out.strip() == "1"

    def set_airplane(self, on):
        """비행기모드 토글. 여러 방식 시도."""
        val = "enable" if on else "disable"
        # 방법1: cmd connectivity (Android 11+, 무루트)
        rc, out, err = self.adb("shell", "cmd", "connectivity", "airplane-mode", val, timeout=15)
        time.sleep(1.5)
        if self.airplane_is_on() == on:
            return True, "cmd connectivity"
        # 방법2: settings + broadcast (루트 필요할 수 있음)
        self.shell(f"settings put global airplane_mode_on {1 if on else 0}")
        self.shell(f"am broadcast -a android.intent.action.AIRPLANE_MODE --ez state {'true' if on else 'false'}")
        time.sleep(1.5)
        if self.airplane_is_on() == on:
            return True, "settings+broadcast"
        return self.airplane_is_on() == on, "unknown"

    # ── Recent(최근 앱) 종료 ──────────────────────────────────────
    def close_recents(self):
        """최근 앱 화면 진입 후 모두 닫기 시도."""
        # Recent 진입
        self.shell("input keyevent KEYCODE_APP_SWITCH")
        time.sleep(config.T_UI_SETTLE)

    def force_stop(self, pkg):
        self.shell(f"am force-stop {pkg}")

    # ── 홈 ────────────────────────────────────────────────────────
    def go_home(self):
        self.d.press("home")
        time.sleep(1)

    def unlock(self):
        try:
            self.d.screen_on()
            self.d.unlock()
        except Exception:
            pass
