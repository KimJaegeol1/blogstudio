"""세 갈래를 합쳐 보는 자리.

파일은 갈라 두고 읽을 때만 합친다. 갈라 둔 이유는 물어보는 질문이 다르기
때문이다 — "사람이 뭘 별로라고 했나"와 "모델이 뭘 냈나"는 따로 세고 따로 읽는다.
그런데 "이 글이 어떻게 만들어졌나"를 볼 때는 셋이 시간순으로 섞여야 한다.

합치는 일을 각 스트림 모듈에 두면 셋이 서로를 import 하게 된다. 여기 한 곳에
두면 위쪽 모듈은 아무것도 모른 채로 남는다.
"""

from . import choice, feedback, response

STREAMS = ("feedback", "choice", "response")

_READ = {"feedback": feedback.read, "choice": choice.read, "response": response.read}


def read(day: str | None = None, stream: str | None = None) -> list[dict]:
    """행 전부. 시간순. 어느 파일에서 왔는지 stream 으로 표시한다."""
    names = (stream,) if stream in STREAMS else STREAMS
    out = []
    for name in names:
        for row in _READ[name](day):
            out.append({**row, "stream": name})
    return sorted(out, key=lambda r: r.get("at", ""))


def journey(sid: str, day: str | None = None) -> list[dict]:
    """한 세션이 지나온 자취만. 시간순."""
    return [r for r in read(day) if r.get("sid") == sid]


def counts(day: str | None = None) -> dict[str, int]:
    """갈래별 행 수. /api/health 가 쓴다."""
    return {name: len(_READ[name](day)) for name in STREAMS}


# ── 확인용 ────────────────────────────────────────────────────
#
# 로그를 눈으로 볼 때 쓴다. raw 와 input 이 한 행에 수십 KB씩이라
# 통째로 내보내면 브라우저에서 열리지 않는다. 그래서 요약을 따로 만든다.
#
# 요약에 무엇을 남길지는 "그 행이 무엇이었는지 한 줄로 알아볼 수 있는가"로
# 정했다. 자세히 봐야 할 행을 찾은 다음 full 로 다시 부르면 된다.

CUT = 160


def _cut(v, n=CUT):
    s = "" if v is None else str(v)
    return s if len(s) <= n else s[:n] + "…"


def _digest(r: dict) -> dict:
    """행 하나를 한 줄로. 갈래·종류마다 볼 것이 다르다."""
    kind = r.get("kind")

    if r.get("stream") == "feedback":
        return {"verdict": r.get("verdict"), "tags": r.get("tags") or [],
                "note": _cut(r.get("note")),
                "target": _cut((r.get("option") or {}).get("title")
                               or (r.get("option") or {}).get("topic_title")
                               or r.get("option_id"))}

    if kind == "generated":
        items = r.get("options") or []
        return {"n": len(items), "source": r.get("source"),
                "titles": [_cut(o.get("title"), 60) for o in items],
                "raw_len": len(r.get("raw") or "")}

    if kind == "confirmed":
        return {"offered": len(r.get("offered") or []),
                "chosen": r.get("chosen") or [],
                "written": _cut(r.get("written")),
                "label": _cut((r.get("value") or {}).get("label"))}

    if kind == "written":
        out = r.get("output") or {}
        return {"lead": _cut(out.get("lead") or out.get("alt")),
                "sections": len(out.get("sections") or []) or None,
                "file": out.get("file"),
                "raw_len": len(r.get("raw") or "")}

    if kind == "failed":
        return {"reason": _cut(r.get("reason"), 300),
                "raw_len": len(r.get("raw") or "")}

    if kind == "uploaded":
        segs = r.get("segments") or []
        return {"name": _cut(r.get("name")), "sha": r.get("sha"),
                "pages": r.get("pages"), "chars": r.get("chars"),
                "picked": r.get("picked"), "segs": [x.get("page") for x in segs],
                "pick_error": _cut(r.get("pick_error"))}

    if kind == "rejected":
        return {"name": _cut(r.get("name")), "bytes": r.get("bytes"),
                "reason": _cut(r.get("reason"), 300)}

    return {}


def brief(r: dict) -> dict:
    """공통 칸 + 갈래별 요약."""
    out = {"at": r.get("at"), "stream": r.get("stream"), "kind": r.get("kind"),
           "sid": r.get("sid"), "step": r.get("step"),
           "model": r.get("model"), "ms": r.get("ms")}
    # 어느 문서에 대한 행인가. 있는 행에만 붙인다 — 없는 행에 빈 칸이
    # 생기면 요약이 넓어지기만 하고 알려 주는 게 없다.
    if r.get("doc"):
        out["doc"] = r["doc"]
    return {**out, **_digest(r)}


def _facets(rows) -> dict:
    """이 행들 안에 어떤 값이 있나. 무엇으로 걸러 볼 수 있는지 알려 준다."""
    return {
        "sids": sorted({r["sid"] for r in rows if r.get("sid")}),
        "steps": sorted({r["step"] for r in rows if r.get("step")}),
        "kinds": sorted({r["kind"] for r in rows if r.get("kind")}),
        "docs": sorted({r["doc"] for r in rows if r.get("doc")}),
    }


def find(stream: str | None = None, sid: str | None = None,
         step: str | None = None, kind: str | None = None,
         doc: str | None = None,
         day: str | None = None, limit: int = 100,
         newest_first: bool = True, full: bool = False) -> dict:
    """확인용 조회 한 번.

    걸러낸 뒤 자른다. 자르고 거르면 "최근 100건 안에 그 sid 가 없어서
    빈 결과" 라는 헷갈리는 일이 생긴다.

    **빈 결과일 때 무엇을 물어야 하는지 알려 준다.** 예전에는 `steps: []`
    만 돌려줘서, 이름을 틀리면 실제 이름을 찾을 방법이 없었다 — 프롬프트
    이름(`naver_outline`)과 단계 key(`outline`)가 달라서 실제로 막혔다.
    """
    all_rows = read(day, stream)
    rows = all_rows
    if sid:
        rows = [r for r in rows if r.get("sid") == sid]
    if step:
        rows = [r for r in rows if r.get("step") == step]
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    if doc:
        # 문서 하나가 지나온 자취. 올린 행과 그 문서로 돈 응답이 같이 나온다.
        rows = [r for r in rows if r.get("doc") == doc]

    total = len(rows)
    if newest_first:
        rows = rows[::-1]
    shown = rows[:max(0, limit)] if limit else rows

    out = {
        "total": total,
        "shown": len(shown),
        # **필터를 탄 수다.** 예전에는 스트림 전체를 다시 세서, 같은 응답
        # 안에서 total 과 기준이 달랐다.
        "counts": {name: sum(1 for r in rows if r.get("stream") == name)
                   for name in STREAMS},
        **_facets(rows),
        "rows": shown if full else [brief(r) for r in shown],
    }
    if not total:
        # 걸러낸 조건이 무엇이었고, 실제로는 무엇이 있는지.
        out["asked"] = {k: v for k, v in
                        (("stream", stream), ("sid", sid), ("step", step),
                         ("kind", kind), ("doc", doc), ("day", day)) if v}
        out["available"] = _facets(all_rows)
        out["hint"] = ("걸러낸 조건에 맞는 행이 없다. available 에 실제로 있는 "
                       "값이 들어 있다. step 은 단계 key 다 — 프롬프트 이름"
                       "(naver_outline)이 아니라 outline 처럼 쓴다.")
    return out
