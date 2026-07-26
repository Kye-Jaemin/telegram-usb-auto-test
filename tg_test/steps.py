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
    def __init__(self, dev, run_id=None):
        self.dev = dev
        self.d = dev.d
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self.results = []

    def _save_dump(self, idx):
        """문제 발생 단계의 adb logcat 스냅샷 + 원본 스크린샷을 로컬에 저장(비공개).
        반환: logcat 파일 경로(없으면 None)."""
        import os
        import shutil
        out_dir = os.path.join(config.DUMPS_DIR, self.run_id)
        os.makedirs(out_dir, exist_ok=True)
        # 1) logcat 스냅샷
        try:
            log = self.dev.logcat_snapshot()
        except Exception as e:
            log = f"logcat-error: {e}"
        log_path = os.path.join(out_dir, f"step{idx:02d}_logcat.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(log)
        except Exception:
            log_path = None
        # 2) 원본 스크린샷 복사(record에서 방금 찍은 것)
        try:
            src_shot = os.path.join(config.SHOTS_DIR, f"step{idx:02d}.png")
            if os.path.exists(src_shot):
                shutil.copy2(src_shot, os.path.join(out_dir, f"step{idx:02d}.png"))
        except Exception:
            pass
        # 3) 텔레그램 디버그 로그: 아직 비활성이면 1회 켜기 시도(문제 발생 시), 그 후 pull
        try:
            if not getattr(self, "_dbg_enabled", False):
                if self.dev.telegram_debug_logs_enabled():
                    self._dbg_enabled = True
                elif not getattr(self, "_dbg_tried", False):
                    self._dbg_tried = True
                    self._dbg_enabled = self.dev.enable_telegram_debug_logs()
            self.dev.pull_telegram_logs(out_dir)
        except Exception:
            pass
        return log_path

    # 결과 기록(+스크린샷, 실패 시 덤프)
    def record(self, idx, title, status, detail):
        shot = f"step{idx:02d}"
        self.dev.screenshot(shot)
        dump_path = None
        if status in ("FAIL", "WARN"):
            dump_path = self._save_dump(idx)
        self.results.append({
            "idx": idx,
            "title": title,
            "status": status,          # PASS / FAIL / WARN / INFO
            "detail": detail,
            "screenshot": f"screenshots/{shot}.png",
            "dump": dump_path,
            "ts": time.strftime("%H:%M:%S"),
        })
        extra = f" [덤프: {dump_path}]" if dump_path else ""
        print(f"[{status}] {idx:02d}. {title} - {detail}{extra}")
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
        w, h = self.dev.w, self.dev.h
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

    # ── Google SSO 로그인 처리(이메일 인증 요구 시) ──────────────
    def _handle_google_sso(self):
        """flood로 SMS 대신 이메일 인증 화면이 뜨면 Google 계정으로 로그인.
        성공적으로 SSO 시도했으면 True."""
        if not self.dev.exists_any_text(config.TG_EMAIL_VERIFY_TEXTS, timeout=2):
            return False
        # 'Google 계정으로 로그인' 탭
        if not self.dev.tap_texts(config.TG_GOOGLE_LOGIN_TEXTS, timeout=4):
            return False
        time.sleep(4)
        # 계정 선택(이름 또는 이메일)
        picked = self.d(text=config.TG_GOOGLE_ACCOUNT_NAME).click_exists(timeout=5)
        if not picked:
            picked = self.d(textContains=config.TG_GOOGLE_ACCOUNT_EMAIL).click_exists(timeout=3)
        time.sleep(5)
        # 동의/계속 버튼(있으면)
        self.dev.tap_texts(config.TG_SSO_CONSENT_TEXTS, timeout=4, partial=False)
        time.sleep(5)
        return True

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
                # 번호: 반드시 기존값 완전 삭제(clear_text) 후 재설정.
                # (이 기기/IME에서 set_text가 기존 값에 덧붙어 번호가 깨지는 버그 대비)
                num = self.d(className="android.widget.EditText")[1]
                num.click(); time.sleep(0.3)
                num.clear_text(); time.sleep(0.4)
                num.set_text(config.TG_PHONE_NATIONAL); time.sleep(0.4)
                cur = (self.d(className="android.widget.EditText")[1].get_text() or "").replace(" ", "")
                # 혹시 아직 안 맞으면 한 번 더 시도
                if cur != config.TG_PHONE_NATIONAL:
                    num.clear_text(); time.sleep(0.4)
                    num.set_text(config.TG_PHONE_NATIONAL); time.sleep(0.4)
                    cur = (self.d(className="android.widget.EditText")[1].get_text() or "").replace(" ", "")
                num_set = (cur == config.TG_PHONE_NATIONAL)
            except Exception:
                pass
            time.sleep(0.8)
        # 다음(파란 화살표) — desc 후보 우선, 없으면 우하단 FAB 좌표
        tapped = self.dev.tap_desc(["다음", "Next", "완료", "Done", "Continue"], timeout=4)
        if not tapped:
            try:
                # 우하단 파란 화살표 FAB (해상도 비율)
                self.dev.tap_ratio(0.87, 0.62)
                tapped = True
            except Exception:
                pass
        time.sleep(3)
        # 번호 확인 다이얼로그: '네' 등 긍정 버튼
        confirmed = self.dev.tap_texts(config.TG_NUMBER_CONFIRM_TEXTS, timeout=6, partial=False)
        time.sleep(4)
        # 쿨다운('너무 많이 시도') 다이얼로그가 뜨면 그 화면을 그대로 기록(닫지 않음 → record가 캡처)
        cooldown = self.dev.exists_any_text(["너무 많이", "나중에 다시", "죄송합니다"], timeout=1)
        # flood로 이메일 인증이 요구되면 Google SSO로 로그인
        sso = False if cooldown else self._handle_google_sso()
        status = "WARN" if cooldown else ("PASS" if tapped else "WARN")
        return self.record(6, "로그인 화살표(다음) 선택",
                           status,
                           f"국가코드82:{cc_set}, 번호:{num_set}, 다음:{tapped}, 확인(네):{confirmed}, "
                           f"쿨다운:{cooldown}, Google SSO:{sso} — SMS/SSO 로그인 대기")

    # ── STEP 7 ───────────────────────────────────────────────────
    def step07_verify_login(self):
        # SMS 자동입력/SSO 로그인 완료까지 대기(최대 ~60초)
        logged_in = False
        sso_used = False
        cooldown = False
        for i in range(12):
            if self._is_logged_in(timeout=5):
                logged_in = True
                break
            # 쿨다운/에러 다이얼로그 감지(닫지 않음 → record가 에러 화면 그대로 캡처)
            if self.dev.exists_any_text(["너무 많이", "나중에 다시", "죄송합니다"], timeout=1):
                cooldown = True
                break
            # 이메일 인증 화면이 (늦게) 뜨면 Google SSO 시도(1회)
            if not sso_used and self.dev.exists_any_text(config.TG_EMAIL_VERIFY_TEXTS, timeout=1):
                sso_used = self._handle_google_sso()
            time.sleep(3)
        detail = f"로그인 완료: {logged_in} (쿨다운: {cooldown}, SSO 폴백: {sso_used})"
        result = self.record(7, "로그인 확인",
                             "PASS" if logged_in else "FAIL", detail)
        # 에러 화면 기록 후 쿨다운 다이얼로그 정리(다음 단계 진행 위해)
        if cooldown:
            self.dev.tap_texts(["확인", "OK"], timeout=2)
        return result

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
            ["선택된 위치", "보호", "변경", "VPN 위치", "ExpressVPN"], timeout=5)
        return self.record(10, "ExpressVPN 실행",
                           "PASS" if on_vpn else "FAIL",
                           f"현재 앱: {pkg}, VPN 화면 감지: {on_vpn}")

    # ── ExpressVPN 위치 변경 공용 헬퍼 ───────────────────────────
    def _vpn_pick(self, texts):
        """텍스트 포함 항목 중 첫 요소를 좌표 없이 클릭. 성공 시 선택 라벨 반환."""
        for t in texts:
            el = self.d(textContains=t)
            if el.count > 0:
                try:
                    label = el[0].info.get("text") or t
                except Exception:
                    label = t
                el[0].click()
                return True, label
        return False, None

    def _vpn_change_country(self, country_texts):
        """ExpressVPN에서 국가를 변경한다. (opened, selected, label, connected) 반환.

        흐름: 홈 '변경' → 위치목록 → 구체 서버('<국가> - 도시') 탭
             → '위치를 변경하시나요?' 계속 → 연결.
        """
        # 홈의 평점 팝업 닫기(있으면)
        self.dev.tap_texts(config.VPN_DISMISS_TEXTS, timeout=2)
        # 위치 변경 진입
        opened = self.dev.tap_texts(config.VPN_CHANGE_LOCATION_TEXTS, timeout=6)
        time.sleep(2.5)
        # 구체 서버(하이픈 포함) 우선 선택, 없으면 국가명
        hyphen = [c + " -" for c in country_texts]
        selected, label = self._vpn_pick(hyphen)
        if not selected:
            selected, label = self._vpn_pick(country_texts)
        time.sleep(2)
        # '위치를 변경하시나요?' 확인 다이얼로그 → 계속
        self.dev.tap_texts(["계속", "Continue", "확인", "OK"], timeout=5, partial=False)
        time.sleep(config.T_APP_LAUNCH)
        # 연결 후 팝업 닫기
        self.dev.tap_texts(config.VPN_DISMISS_TEXTS, timeout=2)
        connected = self.dev.exists_any_text(
            config.VPN_CONNECTED_TEXTS + country_texts, timeout=12)
        return opened, selected, label, connected

    # ── STEP 11 ──────────────────────────────────────────────────
    def step11_change_to_usa(self):
        opened, selected, label, connected = self._vpn_change_country(config.VPN_USA_TEXTS)
        return self.record(11, "ExpressVPN 서버 미국으로 변경",
                           "PASS" if (selected and connected) else ("WARN" if selected else "FAIL"),
                           f"위치변경진입:{opened}, 선택:{label}, 연결/미국표시:{connected}")

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

    def _in_chat_input(self):
        """대화방 하단 메시지 입력창(EditText가 화면 하단부에 위치)이면 반환, 아니면 None."""
        e = self.d(className="android.widget.EditText")
        if e.exists:
            try:
                if e.info["bounds"]["top"] > self.dev.h * 0.6:
                    return e
            except Exception:
                return e if e.exists else None
        return None

    def step13_send_test_message(self):
        target = config.TG_TARGET_CONTACT
        msg = config.TG_TEST_MESSAGE
        # 서브화면/검색 상태 정리 후 텔레그램 대화 탭
        for _ in range(2):
            self.d.press("back")
            time.sleep(0.5)
        self.dev.app_start(config.PKG_TELEGRAM, stop=False)
        time.sleep(2.5)
        self.dev.tap_texts(["대화", "Chats"], timeout=5, partial=False)
        time.sleep(1.2)
        # 검색으로 대상 찾기(채팅목록/검색결과 행은 a11y 미노출 → 검색 후 첫 결과 좌표 탭)
        searched = self.dev.tap_texts(["대화 검색", "Search", "검색"], timeout=5)
        time.sleep(1)
        try:
            self.d.send_keys(target, clear=True)
        except Exception:
            self.d.send_keys(target)
        time.sleep(2.5)
        # 첫 검색결과 행 좌표 탭 → 대화방 진입
        self.dev.tap_ratio(0.33, 0.24)
        time.sleep(3)
        # 프로필 페이지면(하단 입력창 없음) '메시지' 버튼으로 대화방 진입
        if self._in_chat_input() is None:
            self.dev.tap_texts(["메시지", "Message"], timeout=3, partial=False)
            time.sleep(2)
        edit = self._in_chat_input()
        in_chat = edit is not None
        # 메시지 입력
        typed = False
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
        e2 = self._in_chat_input()
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
                           f'검색:{searched}, 대화방:{in_chat}, 입력:{typed}, 전송:{sent}, 입력창비움:{cleared}')

    # ── STEP 14 ──────────────────────────────────────────────────
    def step14_change_to_korea(self):
        # ExpressVPN 실행 후 국가를 한국으로 변경
        self.dev.app_start(config.PKG_VPN, stop=False)
        time.sleep(config.T_APP_LAUNCH)
        opened, selected, label, connected = self._vpn_change_country(config.VPN_KOREA_TEXTS)
        return self.record(14, "ExpressVPN 서버 한국으로 변경(최종)",
                           "PASS" if (selected and connected) else ("WARN" if selected else "FAIL"),
                           f"위치변경진입:{opened}, 선택:{label}, 연결/한국표시:{connected}")

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
            self.step14_change_to_korea,
        ]
        for fn in steps:
            try:
                fn()
            except Exception as e:
                idx = len(self.results) + 1
                self.record(idx, fn.__name__, "FAIL", f"예외 발생: {e}")
        return self.results
