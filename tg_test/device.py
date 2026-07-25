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
        os.makedirs(config.SHOTS_DIR, exist_ok=True)

    # ── adb ───────────────────────────────────────────────────────
    def adb(self, *args, timeout=30):
        cmd = ["adb", "-s", self.serial, *args]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

    def shell(self, cmd, timeout=30):
        rc, out, err = self.adb("shell", cmd, timeout=timeout)
        return out if rc == 0 else (out + err)

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
