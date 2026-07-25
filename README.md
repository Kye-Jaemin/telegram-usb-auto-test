# Telegram USB 자동화 테스트

갤럭시(안드로이드) 실기기를 USB로 연결해 아래 시나리오를 자동 수행하고, 결과를 **누적 대시보드**로 공개한다.

## 시나리오 (13단계)
1. 텔레그램 실행
2. 설정 > 내 계정 > 로그아웃
3. 로그아웃 확인
4. Recent 진입 후 텔레그램 종료
5. 텔레그램 재실행 > 시작하기
6. 이전 로그인 정보로 로그인(국가코드 +82, 번호 확인 "네")
7. 로그인 확인 (SMS 코드 자동입력)
8. 비행기모드 On
9. 5초 후 비행기모드 Off
10. Thunder VPN 실행
11. 서버 위치 미국으로 변경
12. 텔레그램 재실행 정상 동작
13. "경애"에게 "test" 전송 → 최종 Pass

## 대시보드
- **총 시도 / 성공 / 실패 / 성공률**을 실시간(30초 자동 새로고침)으로 표시
- 실행할 때마다 누적 집계
- **실패했을 때만** 해당 단계의 스크린샷(개인정보 보호 블러 처리) + 로그를 게시
- 성공 실행은 숫자만 집계 (개인정보 노출 없음)

GitHub Pages: 저장소 설정에서 Pages 소스를 `main` 브랜치 `/docs` 로 지정.

## 실행 방법
```bash
pip install -r requirements.txt      # uiautomator2
adb devices                          # 기기 연결 확인 (USB 디버깅 필요)
python run_test.py --serial <SERIAL> --push
```
- `--push` : 실행 후 `docs/` 변경을 git commit & push 하여 대시보드 자동 갱신

## 구조
```
run_test.py         실행 엔트리포인트(집계·대시보드·푸시)
tg_test/config.py   패키지명·셀렉터·타이밍
tg_test/device.py   기기 제어(ADB·uiautomator2·스크린샷·비행기모드)
tg_test/steps.py    13단계 시나리오
tg_test/report.py   누적 이력·대시보드·실패 아티팩트
docs/               공개 대시보드(GitHub Pages)
results/            로컬 원본(스크린샷·이력) — .gitignore, 비공개
```

## 환경
- 기기: 삼성 갤럭시 (One UI / Android), 텔레그램 `org.telegram.messenger`, Thunder VPN `com.fast.free.unblock.thunder.vpn`
- 호스트: Windows + Python 3.12 + ADB
