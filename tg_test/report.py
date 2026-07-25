# -*- coding: utf-8 -*-
"""누적 대시보드 생성 + 실패 아티팩트(마스킹 스크린샷·로그) 게시.

- results/history.json : 마스터 이력(로컬, 비공개). 매 실행마다 1건 append.
- docs/index.html      : 총 시도/성공/실패를 보여주는 대시보드(공개).
- docs/data/history.json: 대시보드용 이력 사본(공개, 개인정보 없음).
- docs/runs/<run_id>/  : 실패한 실행일 때만 마스킹 스크린샷 + 로그 업로드.
"""
import os
import json
import time

from . import config

HISTORY = os.path.join(config.RESULTS_DIR, "history.json")

# 대시보드에 표시할 전체 시나리오(고정)
SCENARIO = [
    "텔레그램 실행",
    "설정 > 내 계정 > 로그아웃",
    "로그아웃 확인",
    "Recent 진입 후 텔레그램 종료",
    "텔레그램 재실행 > 시작하기",
    "이전 로그인 정보로 로그인(국가코드 +82, 번호 확인 '네')",
    "로그인 확인 (SMS 코드 자동입력)",
    "비행기모드 On",
    "5초 후 비행기모드 Off",
    "ExpressVPN 실행",
    "ExpressVPN 서버 미국으로 변경",
    "텔레그램 재실행 정상 동작",
    '"뚱재민"에게 "test" 전송',
    "ExpressVPN 서버 한국으로 변경 → 최종 Success",
]


# ── 이력 로드/저장 ────────────────────────────────────────────────
def load_history():
    if os.path.exists(HISTORY):
        try:
            with open(HISTORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"totals": {"attempts": 0, "pass": 0, "fail": 0}, "runs": []}


def append_run(meta, results):
    """이력에 이번 실행을 추가하고 totals 갱신. run 요약 dict 반환."""
    hist = load_history()
    overall = meta["overall"]
    run = {
        "run_id": meta["run_id"],
        "run_at": meta["run_at"],
        "model": meta["model"],
        "android": meta["android"],
        "duration": meta["duration"],
        "overall": overall,
        "n_pass": sum(1 for r in results if r["status"] == "PASS"),
        "n_fail": sum(1 for r in results if r["status"] == "FAIL"),
        "n_warn": sum(1 for r in results if r["status"] == "WARN"),
        "steps": [
            {"idx": r["idx"], "title": r["title"], "status": r["status"], "detail": r["detail"]}
            for r in results
        ],
        # 실패/경고 단계만 아티팩트 대상
        "failed_steps": [r["idx"] for r in results if r["status"] in ("FAIL", "WARN")],
    }
    hist["runs"].insert(0, run)          # 최신이 앞
    hist["runs"] = hist["runs"][:200]    # 최근 200건 유지
    hist["totals"]["attempts"] += 1
    if overall == "PASS":
        hist["totals"]["pass"] += 1
    else:
        hist["totals"]["fail"] += 1
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    return hist, run


# ── 실패 시 아티팩트(마스킹 스크린샷 + 로그) 게시 ──────────────────
def _mask_image(src, dst):
    """개인정보 보호: 스크린샷을 블러 처리해 텍스트를 읽을 수 없게 만든다."""
    try:
        from PIL import Image, ImageFilter
        img = Image.open(src).convert("RGB")
        img = img.filter(ImageFilter.GaussianBlur(radius=14))
        img.save(dst, "PNG")
        return True
    except Exception:
        # PIL 실패 시 원본 대신 게시하지 않음(개인정보 보호 우선)
        return False


def export_failure_artifacts(meta, results):
    """실패한 실행일 때만 실패 단계의 마스킹 스크린샷 + 로그를 docs/runs/<id>/에 저장.
    반환: 게시된 아티팩트 목록(run 요약에 병합용)."""
    if meta["overall"] == "PASS":
        return []
    run_id = meta["run_id"]
    out_dir = os.path.join(config.DOCS_DIR, "runs", run_id)
    os.makedirs(out_dir, exist_ok=True)
    arts = []
    log_lines = [
        f"# Telegram 자동화 테스트 실패 로그",
        f"run_id: {run_id}",
        f"run_at: {meta['run_at']}",
        f"device: {meta['model']} / Android {meta['android']}",
        f"overall: {meta['overall']}",
        "",
    ]
    for r in results:
        log_lines.append(f"[{r['status']}] {r['idx']:02d}. {r['title']} - {r['detail']}")
        if r.get("dump"):
            log_lines.append(f"    로컬 덤프(비공개): {r['dump']}")
        if r["status"] in ("FAIL", "WARN"):
            src = os.path.join(config.RESULTS_DIR, r["screenshot"])
            shot_name = f"step{r['idx']:02d}.png"
            dst = os.path.join(out_dir, shot_name)
            masked = _mask_image(src, dst) if os.path.exists(src) else False
            arts.append({
                "idx": r["idx"], "title": r["title"], "status": r["status"],
                "detail": r["detail"],
                "screenshot": f"runs/{run_id}/{shot_name}" if masked else None,
            })
    with open(os.path.join(out_dir, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    return arts


# ── 대시보드 HTML ─────────────────────────────────────────────────
def build_dashboard(hist, last_run, failure_arts):
    os.makedirs(config.DOCS_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.DOCS_DIR, "data"), exist_ok=True)

    t = hist["totals"]
    attempts, npass, nfail = t["attempts"], t["pass"], t["fail"]
    rate = round(npass / attempts * 100, 1) if attempts else 0.0

    # 공개용 이력 사본(개인정보 없음: 숫자/단계명/상태/텍스트로그)
    with open(os.path.join(config.DOCS_DIR, "data", "history.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    # 최근 실행 행
    run_rows = []
    for run in hist["runs"][:30]:
        color = "#16a34a" if run["overall"] == "PASS" else "#dc2626"
        run_rows.append(
            f"<tr><td>{_esc(run['run_at'])}</td>"
            f"<td><span class='pill' style='background:{color}'>{run['overall']}</span></td>"
            f"<td>{run['n_pass']}/{len(run['steps'])}</td>"
            f"<td>{run['duration']}s</td>"
            f"<td class='rid'>{_esc(run['run_id'])}</td></tr>"
        )
    run_rows_html = "\n".join(run_rows)

    # 전체 시나리오(고정) — 마지막 실행의 각 단계 결과를 배지로 표시
    last_status = {s["idx"]: s["status"] for s in last_run["steps"]}
    scen_rows = []
    for i, title in enumerate(SCENARIO, start=1):
        st = last_status.get(i, "-")
        c = {"PASS": "#16a34a", "FAIL": "#dc2626", "WARN": "#d97706"}.get(st, "#9aa1ad")
        badge = (f"<span class='pill' style='background:{c}'>{st}</span>"
                 if st != "-" else "<span class='pill' style='background:#9aa1ad'>-</span>")
        scen_rows.append(
            f"<li><span class='snum'>{i:02d}</span>"
            f"<span class='stitle'>{_esc(title)}</span>{badge}</li>"
        )
    scenario_html = "<ol class='scenario'>" + "".join(scen_rows) + "</ol>"

    # 마지막 실행 단계 상세
    step_rows = []
    for s in last_run["steps"]:
        c = {"PASS": "#16a34a", "FAIL": "#dc2626", "WARN": "#d97706"}.get(s["status"], "#2563eb")
        step_rows.append(
            f"<tr><td>{s['idx']:02d}</td><td>{_esc(s['title'])}</td>"
            f"<td><span class='dot' style='background:{c}'></span>{s['status']}</td>"
            f"<td class='dt'>{_esc(s['detail'])}</td></tr>"
        )
    step_rows_html = "\n".join(step_rows)

    # 실패 아티팩트(마스킹 스크린샷 + 로그)
    fail_html = ""
    if failure_arts:
        cards = []
        for a in failure_arts:
            img = (f"<a href='{a['screenshot']}' target='_blank'>"
                   f"<img loading='lazy' src='{a['screenshot']}' alt='step {a['idx']}'></a>"
                   ) if a.get("screenshot") else "<div class='noimg'>스크린샷 없음</div>"
            cards.append(
                f"<div class='fcard'><div class='fhead'>"
                f"<span class='fnum'>{a['idx']:02d}</span> {_esc(a['title'])} "
                f"<span class='pill' style='background:#dc2626'>{a['status']}</span></div>"
                f"<div class='fbody'>{img}<p>{_esc(a['detail'])}</p></div></div>"
            )
        log_link = f"runs/{last_run['run_id']}/log.txt"
        fail_html = (
            f"<section class='fails'><h2>⚠️ 최근 실패 아티팩트 "
            f"<a class='loglink' href='{log_link}' target='_blank'>전체 로그</a></h2>"
            f"<p class='masknote'>개인정보 보호를 위해 스크린샷은 블러 처리됩니다.</p>"
            f"<div class='fgrid'>{''.join(cards)}</div></section>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Telegram 자동화 테스트 대시보드</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --text:#161a20; --sub:#6b7280; --border:#e5e7eb; --shadow:0 1px 3px rgba(0,0,0,.08); }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1115; --card:#1a1d24; --text:#e7e9ee; --sub:#9aa1ad; --border:#2a2f3a; --shadow:0 1px 3px rgba(0,0,0,.4);}} }}
  :root[data-theme="dark"] {{ --bg:#0f1115; --card:#1a1d24; --text:#e7e9ee; --sub:#9aa1ad; --border:#2a2f3a; }}
  :root[data-theme="light"] {{ --bg:#f6f7f9; --card:#fff; --text:#161a20; --sub:#6b7280; --border:#e5e7eb; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,'Segoe UI',Roboto,'Malgun Gothic',sans-serif; background:var(--bg); color:var(--text); }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:28px 16px 64px; }}
  h1 {{ font-size:1.5rem; margin:0 0 4px; }}
  .sub {{ color:var(--sub); font-size:.88rem; margin:0 0 24px; }}
  .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:12px; }}
  @media(max-width:640px) {{ .cards {{ grid-template-columns:repeat(2,1fr); }} }}
  .stat {{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:20px; box-shadow:var(--shadow); text-align:center; }}
  .stat .v {{ font-size:2.4rem; font-weight:800; line-height:1; font-variant-numeric:tabular-nums; }}
  .stat .l {{ font-size:.82rem; color:var(--sub); margin-top:8px; }}
  .bar {{ height:10px; border-radius:999px; background:var(--border); overflow:hidden; margin:10px 0 28px; }}
  .bar > span {{ display:block; height:100%; background:linear-gradient(90deg,#16a34a,#22c55e); }}
  .live {{ display:inline-flex; align-items:center; gap:6px; font-size:.75rem; color:var(--sub); }}
  .live .d {{ width:8px; height:8px; border-radius:50%; background:#16a34a; animation:blink 1.4s infinite; }}
  @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.25}} }}
  section {{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:16px 18px; box-shadow:var(--shadow); margin-bottom:20px; }}
  section h2 {{ font-size:1.05rem; margin:0 0 12px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:top; }}
  th {{ color:var(--sub); font-weight:600; white-space:nowrap; }}
  .dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }}
  .pill {{ color:#fff; font-size:.72rem; font-weight:700; padding:2px 9px; border-radius:999px; }}
  .rid {{ color:var(--sub); font-family:ui-monospace,monospace; font-size:.78rem; }}
  .dt {{ color:var(--sub); }}
  .tablescroll {{ overflow-x:auto; }}
  .fails h2 {{ color:#dc2626; }}
  .loglink {{ font-size:.8rem; font-weight:600; margin-left:8px; }}
  .masknote {{ font-size:.78rem; color:var(--sub); margin:0 0 12px; }}
  .fgrid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; }}
  .fcard {{ border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
  .fhead {{ padding:8px 10px; font-size:.82rem; font-weight:600; border-bottom:1px solid var(--border); }}
  .fnum {{ color:var(--sub); }}
  .fbody img {{ width:100%; display:block; }}
  .fbody p {{ margin:8px 10px; font-size:.78rem; color:var(--sub); }}
  .noimg {{ padding:30px; text-align:center; color:var(--sub); font-size:.8rem; }}
  ol.scenario {{ list-style:none; margin:0; padding:0; counter-reset:none; }}
  ol.scenario li {{ display:flex; align-items:center; gap:10px; padding:9px 4px; border-bottom:1px solid var(--border); font-size:.9rem; }}
  ol.scenario li:last-child {{ border-bottom:none; }}
  .snum {{ color:var(--sub); font-variant-numeric:tabular-nums; font-weight:700; min-width:24px; }}
  .stitle {{ flex:1; }}
  footer {{ text-align:center; color:var(--sub); font-size:.76rem; margin-top:24px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>📱 Telegram 자동화 테스트 대시보드</h1>
  <p class="sub">USB 실기기(ADB) 자동화 · 로그아웃/재로그인 + 비행기모드 + Thunder VPN 미국 전환 + 메시지 발송
    &nbsp;·&nbsp; <span class="live"><span class="d"></span>30초마다 자동 새로고침</span></p>

  <div class="cards">
    <div class="stat"><div class="v">{attempts}</div><div class="l">총 시도</div></div>
    <div class="stat"><div class="v" style="color:#16a34a">{npass}</div><div class="l">성공</div></div>
    <div class="stat"><div class="v" style="color:#dc2626">{nfail}</div><div class="l">실패</div></div>
    <div class="stat"><div class="v">{rate}%</div><div class="l">성공률</div></div>
  </div>
  <div class="bar"><span style="width:{rate}%"></span></div>

  {fail_html}

  <section>
    <h2>🧭 전체 테스트 시나리오 (14단계)</h2>
    {scenario_html}
  </section>

  <section>
    <h2>📋 최근 실행 단계별 결과 (마지막: {_esc(last_run['run_at'])} · {last_run['overall']})</h2>
    <div class="tablescroll">
    <table>
      <thead><tr><th>#</th><th>단계</th><th>결과</th><th>상세</th></tr></thead>
      <tbody>{step_rows_html}</tbody>
    </table>
    </div>
  </section>

  <section>
    <h2>📜 실행 이력 (최근 30건)</h2>
    <div class="tablescroll">
    <table>
      <thead><tr><th>실행 시각</th><th>결과</th><th>통과</th><th>소요</th><th>run id</th></tr></thead>
      <tbody>{run_rows_html}</tbody>
    </table>
    </div>
  </section>

  <footer>기기 {_esc(last_run['model'])} · Android {_esc(str(last_run['android']))} · 자동 생성 대시보드</footer>
</div>
</body>
</html>"""
    out = os.path.join(config.DOCS_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
