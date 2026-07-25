# -*- coding: utf-8 -*-
"""테스트 시나리오 12단계 구현.

시나리오:
 1. 텔레그램 실행
 2. 설정 > 내 계정 > 로그아웃
 3. 로그아웃 확인
 4. Recent 진입 후 텔레그램 종료
 5. 텔레그램 재실행 > 시작하기
 6. 로그인 화살표(다음) 선택
 7. 로그인 확인
 8. 비행기모드 On
 9. 5초 후 비행기모드 Off
10. Thunder VPN 실행
11. 서버 위치 미국으로 변경
12. 텔레그램 재실행 정상 → 최종 Pass
"""
import time

from . import config


class Runner:
    def __init__(self, dev):
        self.dev = dev
        self.d = dev.d
        self.results = []

    # 결과 기록(+스크린샷)
    def record(self, idx, title, status, detail):
        shot = f"step{idx:02d}"
        path = self.dev.screenshot(shot)
        self.results.append({
            "idx": idx,
            "title": title,
            "status": status,          # PASS / FAIL / WARN / INFO
            "detail": detail,
            "screenshot": f"screenshots/{shot}.png",
            "ts": time.strftime("%H:%M:%S"),
        })
        print(f"[{status}] {idx:02d}. {title} - {detail}")
        return status == "PASS"

    # ── 로그인 상태 판별 ─────────────────────────────────────────
    def _is_logged_in(self, timeout=8):
        # 로그인 상태에서만 나타나는 하단 탭(연락처/프로필) 또는 검색창
        return self.dev.exists_any_text(
            ["대화 검색", "연락처", "프로필", "Contacts", "Settings"], timeout=timeout)

    def _is_logged_out(self, timeout=6):
        # 인트로(시작하기) 화면
        if self.dev.exists_any_text(config.TG_LOGGED_OUT_TEXTS, timeout=timeout):
            return True
        # 번호 입력 화면이면서 로그인 탭이 없으면 로그아웃 상태
        if self.dev.exists_any_text(config.TG_NUMBER_SCREEN_TEXTS, timeout=2) \
                and not self._is_logged_in(timeout=1):
            return True
        return False

    # ── STEP 1 ───────────────────────────────────────────────────
    def step01_launch_telegram(self):
        self.dev.unlock()
        # 신규 실행(stop=True): 하위화면이 아닌 채팅목록 루트에서 시작
        self.dev.app_start(config.PKG_TELEGRAM, stop=True)
        time.sleep(config.T_APP_LAUNCH)
        # 혹시 하위화면이면 루트까지 뒤로
        for _ in range(3):
            if self.dev.exists_any_text(["대화", "채팅", "Chats"], timeout=1):
                break
            self.d.press("back")
            time.sleep(0.8)
        pkg = self.dev.current_pkg()
        on_tg = self._is_logged_in(timeout=4) or self._is_logged_out(timeout=2) or pkg == config.PKG_TELEGRAM
        return self.record(1, "텔레그램 실행",
                           "PASS" if on_tg else "FAIL",
                           f"현재 앱: {pkg}, 텔레그램 채팅목록 감지: {on_tg}")

    # ── STEP 2 ───────────────────────────────────────────────────
    def step02_logout(self):
        # 설정 탭
        if not self.dev.tap_texts(config.TG_SETTINGS_TEXTS, timeout=8, partial=False):
            return self.record(2, "설정>내 계정>로그아웃", "FAIL", "설정 탭을 찾지 못함")
        time.sleep(config.T_UI_SETTLE)
        # 내 계정
        if not self.dev.tap_texts(["내 계정", "My Account", "계정"], timeout=8):
            return self.record(2, "설정>내 계정>로그아웃", "FAIL", "'내 계정' 진입 실패")
        time.sleep(config.T_UI_SETTLE)
        # 계정 화면의 '로그아웃' 탭 → 로그아웃 옵션 화면 진입
        if not self.dev.scroll_find_text(config.TG_LOGOUT_TEXTS, max_swipes=8):
            return self.record(2, "설정>내 계정>로그아웃", "FAIL", "'로그아웃' 항목을 찾지 못함")
        time.sleep(config.T_UI_SETTLE)
        # 옵션 화면에서 하단 빨간 '로그아웃' 버튼 탭
        tapped_btn = self.dev.tap_bottom_most_text(config.TG_LOGOUT_TEXTS)
        time.sleep(2)
        # 최종 확인 다이얼로그: 우측 긍정버튼('로그아웃') 탭
        confirmed = self.dev.tap_confirm(config.TG_LOGOUT_CONFIRM_TEXTS)
        time.sleep(config.T_APP_LAUNCH)
        done = self._is_logged_out(timeout=6)
        return self.record(2, "설정>내 계정>로그아웃",
                           "PASS" if done else "WARN",
                           f"옵션화면 로그아웃버튼:{tapped_btn}, 확인:{confirmed}, 로그아웃됨:{done}")

    # ── STEP 3 ───────────────────────────────────────────────────
    def step03_verify_logout(self):
        logged_out = self._is_logged_out(timeout=10)
        return self.record(3, "로그아웃 확인",
                           "PASS" if logged_out else "FAIL",
                           f"로그인 화면(시작하기/전화번호) 감지: {logged_out}")

    # ── STEP 4 ───────────────────────────────────────────────────
    def step04_close_via_recents(self):
        # 최근 앱 진입
        self.dev.close_recents()  # KEYCODE_APP_SWITCH + settle
        # 최근앱 화면에서 앞 카드(텔레그램) 위로 스와이프하여 종료
        w, h = 1080, 2340
        try:
            self.d.swipe(w // 2, int(h * 0.6), w // 2, int(h * 0.1), 0.25)
        except Exception:
            pass
        time.sleep(1.5)
        # 종료 여부 확인
        pid = self.dev.shell(f"pidof {config.PKG_TELEGRAM}").strip()
        closed = (pid == "")
        if not closed:
            # 확실히 종료
            self.dev.force_stop(config.PKG_TELEGRAM)
            time.sleep(1)
            pid2 = self.dev.shell(f"pidof {config.PKG_TELEGRAM}").strip()
            closed = (pid2 == "")
            self.dev.go_home()
            return self.record(4, "Recent 진입 후 텔레그램 종료",
                               "PASS" if closed else "FAIL",
                               f"최근앱 스와이프 후 잔여 pid='{pid}', 강제종료 후 종료됨: {closed}")
        self.dev.go_home()
        return self.record(4, "Recent 진입 후 텔레그램 종료",
                           "PASS", "최근앱에서 스와이프로 종료 완료")

    # ── STEP 5 ───────────────────────────────────────────────────
    def step05_relaunch_and_start(self):
        self.dev.app_start(config.PKG_TELEGRAM, stop=False)
        time.sleep(config.T_APP_LAUNCH)
        # 시작하기 버튼(있으면 탭). 이미 번호화면이면 통과.
        tapped = self.dev.tap_texts(config.TG_START_TEXTS, timeout=8)
        time.sleep(config.T_UI_SETTLE)
        # 시작하기가 없어도 번호 입력/로그인 화면이면 진행 가능
        ok = tapped or self.dev.exists_any_text(config.TG_NUMBER_SCREEN_TEXTS, timeout=4)
        return self.record(5, "텔레그램 재실행 > 시작하기",
                           "PASS" if ok else "WARN",
                           f"'시작하기' 탭: {tapped}, 로그인 진행화면 감지: {ok}")

    # ── STEP 6 ───────────────────────────────────────────────────
    def step06_login_arrow(self):
        # 번호 화면: 국가코드(82) 확인/입력 + 전화번호 확인 + 다음 + '네' 확인
        cc_set = num_set = False
        edits = self.d(className="android.widget.EditText")
        if edits.count >= 2:
            try:
                cc = edits[0]
                if (cc.get_text() or "").strip() != config.TG_COUNTRY_CODE:
                    cc.click(); time.sleep(0.3)
                    cc.set_text(config.TG_COUNTRY_CODE)
                cc_set = True
            except Exception:
                pass
            time.sleep(0.8)
            try:
                num = self.d(className="android.widget.EditText")[1]
                cur = (num.get_text() or "").replace(" ", "")
                if not cur.isdigit() or len(cur) < 9:
                    num.click(); time.sleep(0.3)
                    num.set_text(config.TG_PHONE_NATIONAL)
                num_set = True
            except Exception:
                pass
            time.sleep(0.8)
        # 다음(파란 화살표) — desc 후보 우선, 없으면 우하단 FAB 좌표
        tapped = self.dev.tap_desc(["다음", "Next", "완료", "Done", "Continue"], timeout=4)
        if not tapped:
            try:
                self.d.click(940, 1450)
                tapped = True
            except Exception:
                pass
        time.sleep(3)
        # 번호 확인 다이얼로그: '네' 등 긍정 버튼
        confirmed = self.dev.tap_texts(config.TG_NUMBER_CONFIRM_TEXTS, timeout=6, partial=False)
        return self.record(6, "로그인 화살표(다음) 선택",
                           "PASS" if tapped else "WARN",
                           f"국가코드82:{cc_set}, 번호:{num_set}, 다음:{tapped}, 확인(네):{confirmed} — SMS 자동입력 대기")

    # ── STEP 7 ───────────────────────────────────────────────────
    def step07_verify_login(self):
        # SMS 자동입력/로그인 완료까지 넉넉히 대기(최대 ~60초)
        logged_in = False
        for _ in range(12):
            if self._is_logged_in(timeout=5):
                logged_in = True
                break
            time.sleep(3)
        return self.record(7, "로그인 확인",
                           "PASS" if logged_in else "FAIL",
                           f"채팅 목록/하단 탭 감지(로그인 완료): {logged_in}")

    # ── STEP 8 ───────────────────────────────────────────────────
    def step08_airplane_on(self):
        ok, method = self.dev.set_airplane(True)
        return self.record(8, "비행기모드 On",
                           "PASS" if ok else "FAIL",
                           f"비행기모드 On (방식: {method}, 상태={self.dev.airplane_is_on()})")

    # ── STEP 9 ───────────────────────────────────────────────────
    def step09_airplane_off(self):
        time.sleep(config.T_AIRPLANE_HOLD)  # 5초 유지
        ok, method = self.dev.set_airplane(False)
        time.sleep(2)
        return self.record(9, "5초 후 비행기모드 Off",
                           "PASS" if ok else "FAIL",
                           f"5초 유지 후 Off (방식: {method}, 상태={self.dev.airplane_is_on()})")

    # ── STEP 10 ──────────────────────────────────────────────────
    def step10_launch_vpn(self):
        self.dev.app_start(config.PKG_VPN, stop=False)
        time.sleep(config.T_APP_LAUNCH + 2)
        pkg = self.dev.current_pkg()
        on_vpn = pkg == config.PKG_VPN or self.dev.exists_any_text(
            ["Thunder VPN", "위치", "연결", "Connect"], timeout=5)
        return self.record(10, "Thunder VPN 실행",
                           "PASS" if on_vpn else "FAIL",
                           f"현재 앱: {pkg}, VPN 화면 감지: {on_vpn}")

    # ── STEP 11 ──────────────────────────────────────────────────
    def step11_change_to_usa(self):
        # 서버 선택 진입: 우상단 글로브 아이콘
        self.d.click(988, 175)
        time.sleep(2.5)
        opened = self.dev.exists_any_text(["서버 선택", "서버 위치", "Select Server", "위치"], timeout=6)
        if not opened:
            # 대체: '위치' 텍스트/변경 버튼
            self.dev.tap_texts(config.VPN_CHANGE_LOCATION_TEXTS, timeout=4)
            time.sleep(2)
        # 미국 도시 우선순위로 선택(현재 선택과 다른 도시를 우선)
        selected = False
        for city in ["Los Angeles", "Oregon", "Las Vegas", "Seattle", "Dallas", "New York"]:
            el = self.d(text=city)
            if el.exists:
                el.click()
                selected = True
                picked = f"미국 {city}"
                break
        if not selected:
            # 그냥 '미국' 항목 선택
            if self.dev.tap_texts(config.VPN_USA_TEXTS, timeout=5):
                selected = True
                picked = "미국"
            else:
                picked = "없음"
        time.sleep(config.T_APP_LAUNCH)
        # 평점/추천 팝업이 뜨면 '나중에'로 닫기
        self.dev.tap_texts(config.VPN_DISMISS_TEXTS, timeout=4)
        time.sleep(1.5)
        # 연결/전환 후 광고가 뜨면 닫기 시도
        self.dev.tap_desc(["닫기", "Close", "광고 닫기"], timeout=2)
        connected = self.dev.exists_any_text(config.VPN_CONNECTED_TEXTS + ["미국", "United States"], timeout=10)
        status = "PASS" if selected else "FAIL"
        return self.record(11, "VPN 서버 미국으로 변경",
                           status,
                           f"선택: {picked}, 연결/미국 표시 감지: {connected}")

    # ── STEP 12 ──────────────────────────────────────────────────
    def step12_final_telegram(self):
        self.dev.app_start(config.PKG_TELEGRAM, stop=False)
        time.sleep(config.T_APP_LAUNCH)
        ok = self._is_logged_in(timeout=10)
        pkg = self.dev.current_pkg()
        # 로그인 안돼있어도 앱이 정상 실행(크래시 없이 화면 표시)되면 참고
        running = pkg == config.PKG_TELEGRAM or self._is_logged_out(timeout=3)
        final = ok or running
        return self.record(12, "텔레그램 재실행 정상 동작",
                           "PASS" if final else "FAIL",
                           f"정상 실행: {running}, 로그인 유지: {ok}")

    # ── STEP 13 ──────────────────────────────────────────────────
    def _message_input(self):
        e = self.d(className="android.widget.EditText")
        return e if e.exists else None

    def step13_send_test_message(self):
        target = config.TG_TARGET_CONTACT
        msg = config.TG_TEST_MESSAGE
        # 서브화면/검색 상태 정리 후 텔레그램 채팅목록으로
        for _ in range(2):
            self.d.press("back")
            time.sleep(0.5)
        self.dev.app_start(config.PKG_TELEGRAM, stop=False)
        time.sleep(2.5)
        self.dev.tap_texts(["대화", "Chats"], timeout=5, partial=False)
        time.sleep(1.5)
        # 최상단 채팅 행(=경애, 최근 대화) 좌표 직접 탭 → 대화방 진입
        # (텔레그램 목록 행은 커스텀 뷰라 접근성 클릭이 동작하지 않아 좌표 탭 사용)
        self.d.click(400, 490)
        time.sleep(2.5)
        # 프로필 페이지면(입력창 없음) '메시지' 버튼으로 대화방 진입
        if self._message_input() is None:
            self.dev.tap_texts(["메시지", "Message"], timeout=3, partial=False)
            time.sleep(2)
        # 대상 대화방인지 확인(툴바 desc/텍스트)
        in_chat = self.d(descriptionContains=target).exists or self.d(text=target).exists
        # 메시지 입력
        typed = False
        edit = self._message_input()
        if edit is not None:
            edit.click()
            time.sleep(0.4)
            try:
                edit.set_text(msg)
                typed = True
            except Exception:
                self.d.send_keys(msg, clear=True)
                typed = True
        time.sleep(1)
        # 전송: '보내기' 버튼의 우측 좌표를 직접 탭(접근성 클릭 미동작 대비)
        sent = False
        btn = self.d(description="보내기")
        if not btn.exists:
            btn = self.d(descriptionContains="보내")
        if btn.exists:
            sent = self.dev.tap_coord_of(btn, side="right")
        time.sleep(2.5)
        # 검증: 입력창이 비워짐(전송 완료 신호) + 대화방 유지
        input_after = ""
        e2 = self._message_input()
        if e2 is not None:
            try:
                input_after = e2.get_text() or ""
            except Exception:
                input_after = ""
        cleared = input_after.strip() in ("", "메시지", "Message")
        confirmed = typed and sent and cleared and in_chat
        status = "PASS" if confirmed else ("WARN" if (typed and sent) else "FAIL")
        return self.record(13, f'"{target}"에게 "{msg}" 전송',
                           status,
                           f'대화방(경애):{in_chat}, 입력:{typed}, 전송:{sent}, 입력창비움:{cleared}')

    # ── 전체 실행 ────────────────────────────────────────────────
    def run_all(self):
        steps = [
            self.step01_launch_telegram,
            self.step02_logout,
            self.step03_verify_logout,
            self.step04_close_via_recents,
            self.step05_relaunch_and_start,
            self.step06_login_arrow,
            self.step07_verify_login,
            self.step08_airplane_on,
            self.step09_airplane_off,
            self.step10_launch_vpn,
            self.step11_change_to_usa,
            self.step12_final_telegram,
            self.step13_send_test_message,
        ]
        for fn in steps:
            try:
                fn()
            except Exception as e:
                idx = len(self.results) + 1
                self.record(idx, fn.__name__, "FAIL", f"예외 발생: {e}")
        return self.results
