"""명제마다 어떤 질의로 무엇을 찾을지 정한다.

## claim_ref 를 인덱스로 맞추지 않는다

프롬프트에 명제 여섯을 주면 다섯만 돌려주는 일이 있다. 인덱스로 짝을 지으면
그 순간부터 조용히 밀린 명제에 엉뚱한 질의가 붙는다 — 오류가 안 나고 결과만
틀린다. 그래서 `claim_id` 로 되돌린다. 모르는 id 는 버린다.

n8n 에서 겪은 것과 같은 문제다. 개수가 1:1 로 보존될 때만 인덱스가 안전하다.

## 기관 이름을 프롬프트에 박지 않는다

찾을 곳은 `source_target`(출처의 성격)으로만 받는다. 성격 → 어느 도메인을
믿을지는 `policy.PRIORITY` 가 정한다. 프롬프트에 기관명을 박으면 다른
주제에서 재사용이 깨지고, 모델은 그 기관이 실제로 그 자료를 내는지 확인할
수 없다.

## 질의가 없어도 된다

확인해 줄 자료가 있을 것 같지 않은 명제는 질의를 비운다. 없는 것을 찾게
하면 시간만 쓰고 엉뚱한 문서가 근거로 붙는다. 그 명제는 미확인으로 남는다.
"""

import pathlib
import time

from ... import llm, prompt as prompts, sanitize as z
from ...record import response as rec
from ..payload import topic_brief
from ..step import label_of, pay
from . import policy

prompts.register("plan", pathlib.Path(__file__).parent / "plan.md")

NAME = "plan"

LANGS = ("ko", "en")


def build_input(d, claims, docs=()) -> dict:
    return {
        # 검색 질의가 소재의 범위를 벗어나지 않게 요약까지 본다.
        "topic": topic_brief(d, keywords=False),
        "question": pay(d, "intent").get("question", ""),
        "claims": [{k: c[k] for k in
                    ("claim_id", "claim", "claim_type", "required_source")}
                   for c in claims],
        # 사람이 올린 문서. 제목과 앞부분만 보고 어느 명제에 걸지 고른다.
        "documents": [{"document_id": x["id"], "title": x["title"],
                       "preview": x.get("preview", "")} for x in docs],
    }


def _queries(rows) -> list[dict]:
    """질의 목록을 다듬는다. 목록 밖 값이 오면 그 질의를 버린다.

    기본값으로 떨어뜨리지 않는 이유는, `source_target` 이 어느 것을 먼저
    가져올지 정하기 때문이다. 모르는 값을 아무 성격으로 채우면 우선순위가
    조용히 엉킨다.
    """
    out = []
    for q in rows if isinstance(rows, list) else []:
        if not isinstance(q, dict):
            continue
        text = z.s(q.get("query"), 200)
        lang = z.enum(q.get("language"), LANGS)
        target = z.enum(q.get("source_target"), policy.SOURCE_TARGETS)
        if not (text and lang and target):
            continue
        out.append({"query": text, "language": lang, "source_target": target})
    # 성격이 앞선 것부터. 상한에 걸리면 뒤엣것이 잘린다.
    out.sort(key=lambda q: policy.PRIORITY[q["source_target"]])
    return out[:policy.MAX_QUERIES]


def make(d, claims, docs=(), sid: str = "") -> dict:
    """{"queries": {claim_id: [질의]}, "documents": {claim_id: [출처]}}

    실패하면 빈 계획. 막지 않는다 — 계획을 못 세웠다고 근거 단계가 멈추면
    사람이 할 수 있는 게 없다. 그때는 검색 없이 확인 대상만 만든다.

    **문서 연결도 여기서 한다.** 모든 명제 × 모든 문서를 대조하면 상한을
    금방 넘고 문서 하나가 검색 근거를 다 밀어낸다. 제목과 앞부분을 보고
    관련 있는 쌍만 고른다.
    """
    empty = {"queries": {}, "documents": {}}
    if not claims:
        return empty

    docs = list(docs)
    inp = build_input(d, claims, docs)
    known = {c["claim_id"] for c in claims}
    by_doc = {x["id"]: x for x in docs}

    t0 = time.perf_counter()
    try:
        got = llm.generate(NAME, inp)
    except llm.LLMError as e:
        rec.failed(sid, NAME, inp, str(e),
                   ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
        return empty

    plans: dict[str, list[dict]] = {}
    for p in (got.get("plans") or []):
        if not isinstance(p, dict):
            continue
        ref = z.s(p.get("claim_ref"), 20)
        # 인덱스로 맞추지 않는다. 모르는 id 는 조용히 붙이지 않고 버린다.
        if ref not in known or ref in plans:
            continue
        qs = _queries(p.get("queries"))
        if qs:
            plans[ref] = qs

    links = _links(got.get("document_links"), known, by_doc)

    rec.generated(
        sid, NAME, inp,
        [{"id": ref, "title": qs[0]["query"], "meta": qs[0]["source_target"],
          "summary": " / ".join(q["query"] for q in qs[1:]), "payload": {"queries": qs}}
         for ref, qs in plans.items()]
        + [{"id": f"doc:{ref}", "title": r[0]["title"], "meta": "올린 문서",
            "summary": "", "payload": {"documents": r}}
           for ref, r in links.items()],
        model=llm.model_for(False), source="llm", refresh=False,
        ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
    return {"queries": plans, "documents": links}


def _links(rows, known, by_doc) -> dict:
    """올린 문서 → 어느 명제에 붙일지.

    문서 하나가 여러 명제에 걸리는 것은 막지 않되 상한을 둔다. 하나가 전부에
    걸리면 그 문서만으로 글이 만들어진 것처럼 보인다.
    """
    out: dict[str, list[dict]] = {}
    used: dict[str, int] = {}
    for r in (rows if isinstance(rows, list) else []):
        if not isinstance(r, dict):
            continue
        doc = by_doc.get(z.s(r.get("document_ref"), 40))
        if not doc:
            continue
        for ref in (r.get("claim_refs") or [])[:policy.MAX_DOCUMENT_CLAIMS]:
            ref = z.s(ref, 20)
            if ref not in known:
                continue
            if used.get(doc["id"], 0) >= policy.MAX_DOCUMENT_CLAIMS:
                break
            used[doc["id"]] = used.get(doc["id"], 0) + 1
            out.setdefault(ref, []).append({
                "title": doc["title"], "url": "", "file": doc["id"],
                "source_name": doc.get("name", ""),
                "requested_target": "official_primary",
                # 사람이 골라 올린 원문이다. 다만 그 문서가 이 명제를
                # 뒷받침하는지는 대조해 봐야 안다.
                "actual_target": "official_primary",
                "score": 1.0, "status": "fetched",
                "text": doc.get("excerpt", "")})
    return out
