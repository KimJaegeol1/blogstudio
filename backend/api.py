"""JSON API.

프론트와 백엔드가 만나는 유일한 지점이다. 여기서 HTML 을 만들지 않는다.
화면이 어떻게 생겼는지 백엔드는 모르고, 프론트는 이 응답만 보고 그린다.

응답은 늘 {ok: true, ...} 아니면 {ok: false, reason: ...} 이다.
"""

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import FileResponse

from . import build, llm, paths, prompt as prompts, session, steps
from .external import gemini, search as tavily
from .output import illust, render
from .record import choice as rec_choice, history, log
from .steps.evidence import pick, upload
from .data import fake
from .deps import Ctx, Drafting, Refuse, ctx, drafting, editable, known

router = APIRouter(prefix="/api")


def _safe_url(u) -> str:
    """시트에서 온 값이라 스킴을 확인한다. javascript: 등 차단."""
    return u if isinstance(u, str) and u.startswith(("http://", "https://")) else "#"


@router.get("/health")
def health():
    """.env 가 먹었는지, 그리고 지금 어느 코드가 돌고 있는지 여기서 확인한다.

    build 는 소스 내용의 지문이다. 파일을 바꿨는데 이 값이 그대로면 코드가
    안 바뀐 게 아니라 서버가 옛 코드를 들고 있는 것이다. 키는 안 내보낸다.
    """
    return {"ok": True, "llm": llm.ENABLED,
            "model": llm.MODEL, "model_strong": llm.MODEL_STRONG,
            "code": build.CODE, "content": build.CONTENT,
            "tiers": steps.TIERS, "prompts": prompts.names(),
            "imagen": gemini.ENABLED, "imagen_model": gemini.MODEL,
            # 검색이 꺼져 있으면 명제가 전부 미확인으로 남는다. 오류가 안
            # 나므로 키를 안 넣었다는 것을 눈치채기 어렵다 — 여기서 보인다.
            "search": tavily.ENABLED,
            # 후보가 진짜인지 개발용 견본인지. llm 이 꺼져 있으면 각 단계가
            # fake.py 로 떨어지는데, 화면만 봐서는 구별이 안 된다.
            "mode": "real" if llm.ENABLED else "mock",
            "hooks": build.hooks(),
            # 로그가 실제로 어느 폴더에 쌓이는지. 폴더를 여러 벌 두고
            # 엉뚱한 것을 열어 보는 일이 잦아서 절대 경로로 내보낸다.
            "log_dirs": {s: str(log.where(s)) for s in history.STREAMS},
            "log_rows": history.counts()}


@router.get("/steps")
def api_steps(c: Ctx = Depends(ctx)):
    """단계 목록. 채널이 정해지면 뒤에 그 채널 단계가 붙으므로
    드래프트를 봐야 한다. 소재 전에도 부를 수 있어야 하므로 거절하지 않는다."""
    return {"steps": steps.meta(c.st.get("draft"))}


# ── 로그 보기 ──────────────────────────────────────────────────
#
# 브라우저에 주소만 쳐도 읽히게 둔다. 로그가 세 폴더로 갈려 있어서 파일을
# 하나씩 열면 순서가 안 맞고, jsonl 은 한 줄이 수십 KB라 편집기로 보기 어렵다.
#
# 기본은 요약이다. raw 와 input 이 한 행에 20KB씩이라 통째로 내보내면 화면이
# 열리지 않는다. 자세히 볼 행을 찾은 다음 full=1 로 다시 부른다.

@router.get("/logs")
def api_logs(stream: str = "", sid: str = "", step: str = "", kind: str = "",
             doc: str = "", day: str = "", limit: int = 100,
             order: str = "desc", full: int = 0):
    """세 갈래를 합쳐 시간순으로 본다.

        /api/logs                          최근 100건 요약
        /api/logs?stream=response          AI 가 낸 것만
        /api/logs?kind=failed              실패한 것만
        /api/logs?sid=abc123               그 세션이 지나온 자취
        /api/logs?kind=uploaded            사람이 올린 문서만
        /api/logs?doc=a1b2c3               그 문서가 지나온 자취
        /api/logs?step=outline&full=1      구조 단계 행을 통째로
        /api/logs?limit=0                  무엇이 있는지만 (steps · kinds · sids)

    **step 은 단계 key 다.** 프롬프트 이름이 아니다 — 채널이 갈려도
    (`naver_outline`) 행에는 `outline` 로 남는다. 틀리면 응답의
    `available` 이 실제 이름을 알려 준다.
        /api/logs?day=2026-08-04&limit=0   그날 전부

    stream 은 feedback | choice | response.
    kind 는 generated | confirmed | written | failed | uploaded | rejected.
    limit 0 이면 자르지 않는다. order=asc 면 오래된 것부터.
    """
    if stream and stream not in history.STREAMS:
        raise Refuse("unknown_stream", detail=f"stream 은 {', '.join(history.STREAMS)}")
    return {"ok": True,
            **history.find(stream=stream or None, sid=sid or None,
                           step=step or None, kind=kind or None,
                           doc=doc or None, day=day or None, limit=limit,
                           newest_first=(order != "asc"), full=bool(full))}


# ── 1단계 ──────────────────────────────────────────────────────

@router.get("/topics")
def api_topics(state: str = "normal", c: Ctx = Depends(ctx)):
    items = session.topics(c.st, state)
    for t in items:
        for s in t.get("sources", []):
            s["url"] = _safe_url(s.get("url"))
    return {
        "topics": items,
        "error": fake.load_error(state),
        "loaded_at": fake.LOADED_AT,
        "recommended": session.recommended(items),
        "down_tags": fake.DOWN_TAGS,
        "selected": c.st["topic"],
        "custom": c.st["custom"],
        "is_last": state == "last",
    }


@router.post("/topics/pick")
def api_pick(body: dict = Body(...), c: Ctx = Depends(ctx)):
    if not session.pick_topic(c.st, body.get("topic_id"), body.get("custom")):
        raise Refuse("empty")
    session.draft(c.st)
    return {"ok": True, "next": "reader"}


# ── 평가 ───────────────────────────────────────────────────────
#
# 소재든 단계 후보든 결과물이든 "사람이 이걸 어떻게 봤나"는 한 가지 일이다.
# 엔드포인트도 하나로 둔다. step 이 어디서 온 평가인지 말해 준다.

@router.post("/feedback")
def api_feedback(body: dict = Body(...), c: Ctx = Depends(ctx)):
    step = body.get("step", "")
    if step not in steps.BY_KEY and step != "result":
        raise Refuse("unknown_step")
    session.feedback(c.st, c.sid, step,
                     body.get("option_id", ""),
                     body.get("verdict", "none"),
                     body.get("tags") or [],
                     body.get("note", ""))
    return {"ok": True}


# ── 2~8단계 ────────────────────────────────────────────────────

@router.get("/draft")
def api_draft(dr: Drafting = Depends(drafting)):
    return {
        "ok": True,
        "need": session.need(dr.d),
        "done": session.done(dr.d),
        "values": {k: {"label": v["label"], "detail": v.get("detail", "")}
                   for k, v in dr.d.items() if isinstance(v, dict) and "label" in v},
    }


@router.get("/draft/result")
def api_result(dr: Drafting = Depends(drafting)):
    left = session.need(dr.d)
    if left:
        raise Refuse("incomplete", need=left)
    if not dr.d.get("write"):
        # 자리표시를 보여주지 않는다. 무엇이 덜 됐는지 화면에 뜨는 편이 낫다.
        raise Refuse("no_body", detail="본문을 먼저 만들어야 합니다")
    # 이미지 자체는 안 싣는다. 화면을 열 때마다 1MB 를 다시 보내게 된다.
    # 계획과 만들어진 사실만 주고, 그림은 /draft/hero.png 로 따로 받는다.
    made = dr.d.get("hero") or None
    return {"ok": True, "out": render.build(dr.d), "done": session.done(dr.d),
            "hero_plan": ((dr.d.get("outline", {}).get("payload") or {})
                          .get("hero_image") or {}).get("purpose", ""),
            "hero": {"alt": made.get("alt", ""), "file": made.get("file", "")}
                    if made else None,
            "hero_error": dr.d.get("hero_error", "")}


@router.get("/draft/hero.png")
def api_hero_png(dr: Drafting = Depends(drafting)):
    """만들어진 대표 이미지. 결과물 JSON 에 base64 로 싣지 않는 이유는,
    화면을 열 때마다 1MB 를 다시 보내게 되기 때문이다."""
    name = (dr.d.get("hero") or {}).get("file")
    f = paths.IMAGES / name if name else None
    if not f or not f.exists():
        raise Refuse("no_hero")
    return FileResponse(f, media_type="image/png")


# ── 근거 문서 ──────────────────────────────────────────────────
#
# 7단계는 검색을 하지 않는다. 사람이 원문 PDF 를 올리면 그 자리가 메워지고,
# 그 문서는 확인된 출처로 다뤄진다.
#
# {key} 보다 먼저 선언한다. 뒤에 두면 upload 가 단계 이름으로 잡혀 거절된다.

@router.get("/draft/upload")
def api_uploads(dr: Drafting = Depends(drafting)):
    """올려 둔 문서 목록. 발췌 전문은 빼고 준다."""
    return {"ok": True, "docs": upload.listed(dr.d)}


@router.post("/draft/upload")
async def api_upload(file: UploadFile = File(...), dr: Drafting = Depends(drafting)):
    """PDF 하나를 받아 근거 후보로 만든다.

    받자마자 글자를 뽑는다. 파일명만 들고 있으면 본문 작성이 인용할 것이
    없어서 "첨부 자료 참고" 같은 문장만 나온다.
    """
    sid = dr.d.get("_sid", "")
    data = await file.read()
    try:
        doc = upload.save(sid, file.filename or "", data)
    except upload.UploadError as e:
        # 거절도 남긴다. 무엇이 왜 안 들어갔는지가 상한을 조정할 근거다.
        rec_choice.rejected(sid, "evidence", file.filename or "", len(data), str(e))
        raise Refuse("upload_failed", detail=str(e))

    # 어느 쪽을 쓸지는 이 글이 답할 질문을 봐야 알 수 있다. 앞에서부터
    # 자르면 긴 규정에서는 표지와 목차만 담긴다.
    doc = pick.narrow(doc, dr.d)
    upload.add(dr.d, doc)
    # 파일은 id 로만 저장된다. 원래 이름이 남는 곳은 이 행뿐이다.
    rec_choice.uploaded(sid, "evidence", doc)
    # 후보 목록이 달라졌으므로 다음 GET 에서 다시 뽑히게 캐시를 지운다.
    dr.d.get("_opts", {}).pop("evidence", None)
    return {"ok": True, "doc": {k: v for k, v in doc.items() if k != "excerpt"}}


@router.delete("/draft/upload/{doc_id}")
def api_upload_delete(doc_id: str, dr: Drafting = Depends(drafting)):
    if not upload.remove(dr.d, doc_id, dr.d.get("_sid", "")):
        raise Refuse("no_doc")
    dr.d.get("_opts", {}).pop("evidence", None)
    return {"ok": True}


@router.get("/draft/{key}")
def api_step(key: str = Depends(known), refresh: int = 0,
             dr: Drafting = Depends(drafting)):
    # 앞 단계를 건너뛰고 들어오면 안 정한 곳을 알려 준다.
    left = session.need(dr.d)
    ks = steps.keys(dr.d)
    # 이 드래프트가 지나가지 않는 단계다. 채널이 홈페이지인데 네이버
    # 단계를 직접 부르면 여기서 막힌다.
    if key not in ks:
        raise Refuse("unknown_step")
    if left and ks.index(key) > ks.index(left):
        raise Refuse("skipped", need=left)

    saved = dr.d.get(key) or {}
    return {
        "ok": True,
        "step": steps.meta_of(key, dr.d),
        "done": session.done(dr.d, key),
        "options": steps.options(key, dr.d, refresh=bool(refresh)),
        "selected": saved.get("choice_ids", []),
        "written": saved.get("written", ""),
        "hint": steps.WRITE_HINT.get(key, ""),
        # 이 단계에서 알아야 할 것. **구조를 고르기 전에 보여야 한다** —
        # 근거가 하나도 없다는 것을 결과물 만든 뒤에 알면 이미 늦다.
        "warn": session.warn_of(dr.d, key),
        # 후보가 진짜인지 개발용 견본인지. 화면만 봐서는 구별이 안 된다 —
        # 키가 안 읽히는데 t1a·c1 이 뜨면 잘 돌고 있는 줄 안다.
        "mock": not llm.ENABLED,
    }


# {key} 보다 먼저 선언한다. 뒤에 두면 write 가 단계 이름으로 잡혀 거절된다.
@router.post("/draft/write")
def api_write(dr: Drafting = Depends(drafting)):
    """본문 작성. 8단계까지 다 정해져야 부를 수 있다."""
    left = session.need(dr.d)
    if left:
        raise Refuse("incomplete", need=left)
    return {"ok": True, "write": session.write(dr.d)}


@router.post("/draft/hero")
def api_hero(dr: Drafting = Depends(drafting)):
    """대표 이미지 만들기. 구조가 정해져 있어야 계획이 있다."""
    try:
        return {"ok": True, "hero": session.hero(dr.d)}
    except Exception as e:
        raise Refuse("hero_failed", detail=str(e))


@router.post("/draft/illust")
def api_illust(dr: Drafting = Depends(drafting)):
    """본문 그림 만들기. 구조가 계획한 섹션에만 생긴다.

    **일부만 실패해도 200 이다.** 만들어진 것은 쓰고 못 만든 것은
    `failed` 에 이유가 담긴다 — 본문 그림은 원래 없어도 되는 것이라
    하나 때문에 나머지를 막을 이유가 없다.
    """
    got = session.illust(dr.d)
    return {"ok": True, **got,
            "plans": {str(n): v for n, v in illust.plans(dr.d).items()}}


@router.get("/draft/illust/{order}.png")
def api_illust_png(order: int, dr: Drafting = Depends(drafting)):
    """만들어진 본문 그림 한 장."""
    row = (dr.d.get("illust") or {}).get(str(order)) or {}
    name = row.get("file")
    if not name:
        raise Refuse("no_illust")
    path = paths.IMAGES / name
    if not path.exists():
        raise Refuse("no_illust")
    return FileResponse(path, media_type="image/png")


@router.post("/draft/{key}")
def api_confirm(body: dict = Body(...), key: str = Depends(editable),
                dr: Drafting = Depends(drafting)):
    got = session.confirm(dr.d, key, body.get("choice") or [], body.get("custom", ""))
    if got is not True:
        # 왜 안 됐는지 갈라서 준다. "빈 입력" 하나로 뭉개면 PDF 를 올려 둔
        # 사람에게 틀린 안내가 나간다.
        raise Refuse(got if isinstance(got, str) else "empty")
    return {"ok": True, "next": steps.next_of(key, dr.d)}
