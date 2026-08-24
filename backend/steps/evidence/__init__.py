"""7단계 — 근거.

**두 종류를 섞지 않는 것이 이 단계의 전부다.**

    소재에 딸려 온 기사   URL 이 있다. 확인된 출처다
    프롬프트가 만든 것    URL 이 없다. "무엇을 어디서 확인할지" 까지만 정해진 대상이다

프롬프트는 검색을 하지 않고 URL 을 금지한다. 그래서 뒤엣것은 출처가 아니라
확인해야 할 목록이고, 결과물이 아니라 발행 전 확인 목록으로 나간다.
미확인 근거에 출처가 붙는 것은 이 파이프라인에서 반복해 나온 실패라
프롬프트와 코드 양쪽에서 막는다.

**폴더 안 조각들을 여기서 import 한다.** 각 조각이 자기 프롬프트를
등록하는데, 이 폴더가 부르지 않으면 등록이 api.py 의 import 목록에 매달린다.
실제로 `evidence_pick` 이 그 상태였다 — api 를 안 거치는 진입점이 생기면
호출 시점에 MissingPrompt 로 터진다.

    claims.py   검증할 명제 나누기
    plan.py     명제별 검색 계획
    search.py   검색 · 본문 가져오기
    check.py    원문 대조
    policy.py   상태 계산 · 상한
    upload.py   PDF 받기
    pick.py     긴 PDF 에서 쓸 쪽 고르기

여러 개 고를 수 있다(multi). 그래서 확정 라벨을 직접 만든다 — "근거 5건" 으로
뭉뚱그리면 근거가 확보된 줄로 읽힌다.
"""

import json
import time

from ... import llm, sanitize as z
from ...data import sources
from ...record import response as rec
from ...external import search as tavily
from ..payload import is_confirmed
from ..step import Step, label_of, opt, pay
from . import check, claims, pick, plan, policy, search, upload  # noqa: F401


def payload(kind, title, **extra) -> dict:
    return {"kind": kind, "title": title, **extra}


def build_input(d) -> dict:
    # 제목과 소제목을 보지 않는다. 근거가 구조 앞으로 옮겨 온 이유가
    # 그것이다 — 제목이 먼저 서면 근거 찾기가 "정해진 결론을 뒷받침할
    # 자료 찾기" 가 된다. 대신 이 글이 답할 질문을 본다.
    it = pay(d, "intent")
    return {"topic": label_of(d, "topic"),
            "question": it.get("question", ""),
            "sub_questions": it.get("sub_questions", []),
            "angle": pay(d, "angle"),
            "article_type": pay(d, "type").get("article_type", ""),
            "reader": pay(d, "reader"),
            # 이미 첨부된 문서. 같은 것을 "확인해야 할 대상" 으로 또 만들지
            # 않게 알려 준다. 목록이 바뀌면 이 값이 달라져 후보를 다시 뽑는다.
            "documents": upload.brief(d)}


def verified(d, inp, sid="") -> list[dict]:
    """검증된 명제 목록.

    네 조각이 차례로 돈다. 앞이 비면 뒤는 안 돈다 — 명제가 없으면 검색할
    것이 없고, 검색이 꺼져 있으면 대조할 원문이 없다.

        claims  이 글이 성립하려면 참이어야 하는 것을 낱개로
        plan    명제마다 어떤 질의로, 그리고 올린 문서 중 무엇을 볼지
        search  검색하고 본문을 가져온다
        check   원문과 대조한다 → 상태

    소재 기사와 올린 문서도 **여기 섞여 들어온다.** 예전에는 카드로 따로
    나가면서 URL 이나 파일이 있다는 것만으로 확인된 것 취급을 받았다.

    **중간이 실패해도 막지 않는다.** 검색이 꺼져 있거나 실패하면 명제는
    미확인으로 남고, 그건 지금까지의 "무엇을 어디서 확인할지" 와 같은 상태다.
    """
    t0 = time.perf_counter()
    rows = claims.split(d, sid=sid)
    if not rows:
        return []

    live, held = claims.to_check(rows)
    if live:
        made = plan.make(d, live, docs=upload.docs(d), sid=sid)
        # 조건을 붙이지 않는다. 검색이 꺼져 있어도 search.run 이 그 사실을
        # 자취에 남긴다 — 걸러 버리면 "안 했다" 가 어디에도 안 남는다.
        found = search.run(d, made["queries"], sid)
        # 손에 있는 문서를 검색 결과와 같은 자리에 섞는다. 기사도 마찬가지다.
        _mix(found, live, made["documents"], _articles(d))
        check.run(live, found, sid, searched=search.enabled())

    _summary(rows, found if live else {}, sid,
             round((time.perf_counter() - t0) * 1000))
    return live + held


def _summary(rows, found, sid, ms) -> None:
    """근거 단계가 통째로 무엇을 했는지 한 줄.

    지금은 claims · plan · search · check 로그를 명제마다 뒤져야 안다.
    "검색이 돌았나 · 몇 건 걸렸나 · 왜 미확인인가" 는 자주 묻는 것이라
    한 자리에 모아 둔다.
    """
    by_reason = {}
    for c in rows:
        k = c.get("reason_code") or c.get("status", "")
        by_reason[k] = by_reason.get(k, 0) + 1

    fetched = sum(1 for v in found.values() for x in v if x.get("status") == "fetched")
    failed = sum(1 for v in found.values() for x in v
                 if x.get("status") == "fetch_failed")

    rec.generated(
        sid, "evidence",
        {"claims": len(rows), "search_enabled": search.enabled()},
        [{"id": c["claim_id"], "title": c["claim"],
          "meta": f'{c["status"]} · {c.get("authority", "")}',
          "summary": policy.REASONS.get(c.get("reason_code", ""), ""),
          "payload": {"status": c["status"], "authority": c.get("authority"),
                      "reason_code": c.get("reason_code"),
                      "sources": len(c.get("sources") or [])}}
         for c in rows],
        model="-", source="pipeline", refresh=False, ms=ms,
        raw=json.dumps({"본문_가져옴": fetched, "가져오기_실패": failed,
                        "상태별": by_reason}, ensure_ascii=False))


def _articles(d) -> list[dict]:
    """소재에 딸려온 기사. **본문을 바로 가져온다.**

    예전에는 주소만 넣고 `status: discovered` 로 뒀다. 그러면 검색이 같은
    URL 을 우연히 다시 찾아야만 본문이 채워진다 — 실제로는 거의 안 채워지고
    `fetch_failed` 로 남았다.

    이미 주소를 알고 있으므로 검색할 이유가 없다. 검색 키가 없어도 가져올
    수 있게 키 없는 경로(`plain_fetch`)를 쓴다.

    **가져온 것이 그 기사가 맞는지 확인한다.** 주소가 낡으면 같은 사이트의
    엉뚱한 기사가 온다 — 실제로 "CBAM 신고 의무, 무엇이 달라지나" 를
    가져왔더니 치약 제품 기사가 왔다. 기사는 내려가고 번호는 재사용된다.
    """
    out = []
    for a in pay(d, "topic").get("sources", []):
        url = z.s(a.get("url"), 500)
        if not url.startswith(("http://", "https://")):
            continue
        row = {"title": z.s(a.get("headline"), 200), "url": url,
               "requested_target": "secondary",
               "actual_target": sources.classify(url),
               "source_name": z.s(a.get("press"), 60),
               "score": 0.0, "status": "fetch_failed", "text": ""}
        try:
            text = tavily.plain_fetch(url)
            if _is_same(row["title"], text):
                row["text"] = text
                row["status"] = "fetched"
            else:
                row["status"] = "wrong_page"
                row["error"] = "가져온 글이 이 기사가 아니다 (주소가 낡았을 수 있다)"
        except tavily.CallError as e:
            row["error"] = str(e)[:200]
        out.append(row)
    return out


# 제목 낱말이 이만큼은 본문에 있어야 같은 기사로 본다.
SAME_RATIO = 0.5


def _is_same(title: str, text: str) -> bool:
    """가져온 본문이 그 제목의 기사인가.

    뉴스 주소는 기사가 내려가면 목록이나 다른 기사로 넘어간다. 그때
    **제목과 전혀 다른 글이 근거로 들어간다** — 대조가 걸러 주긴 하지만
    우연히 관련 있는 글이면 그대로 붙는다.

    제목의 낱말이 본문에 얼마나 있는지로 가른다. 완전 일치는 못 본다 —
    사이트가 제목을 줄이거나 말머리를 붙인다.
    """
    words = [w for w in (title or "").split() if len(w) >= 2]
    if not words or not text:
        return False
    hit = sum(1 for w in words if w in text)
    return hit / len(words) >= SAME_RATIO


def _mix(found: dict, live, doc_links: dict, articles) -> None:
    """검색 결과에 문서와 기사를 얹는다.

    문서는 plan 이 고른 명제에만 붙는다. 모든 명제 × 모든 문서를 돌리면
    상한을 금방 넘고, 문서 하나가 검색 근거를 다 밀어낸다.

    기사는 어느 명제에 붙을지 정할 근거가 없어서 **첫 명제에만** 붙인다.
    질문에 제일 가까운 것이 앞에 오게 정렬돼 있다.
    """
    budget = policy.MAX_PDF_CHECKS
    for c in sorted(live, key=policy.rank_claim):
        rows = found.setdefault(c["claim_id"], [])
        for doc in doc_links.get(c["claim_id"], [])[:policy.MAX_PDF_PER_CLAIM]:
            if budget <= 0:
                c["reason_code"] = c["reason_code"] or "document_check_limit_exceeded"
                break
            budget -= 1
            rows.append(doc)

    if articles and live:
        found.setdefault(live[0]["claim_id"], []).extend(articles)


def _claim_opt(c) -> dict:
    """명제 하나를 카드로.

    **카드 단위가 명제다.** 본문 작성이 받아야 하는 것은 "어떤 출처를 쓸
    것인가" 가 아니라 "어떤 명제를 글에 쓸 것인가" 이고, 출처는 그 명제를
    뒷받침하는 하위 정보다. 출처를 카드로 두면 같은 문서가 여러 번 뜨고
    사람이 무엇을 고른 건지 모호해진다.
    """
    n = len(c["sources"])
    bits = [LABELS.get(c["status"], c["status"])]
    if c.get("authority") and c["status"] in ("supported", "partial"):
        bits.append(policy.AUTHORITY_LABELS.get(c["authority"], c["authority"]))
    if n:
        bits.append(f"출처 {n}건")
    if c["reason_code"]:
        bits.append(policy.REASONS.get(c["reason_code"], c["reason_code"]))
    if not policy.selectable(c):
        bits.append("고를 수 없음")

    # **고를 수 있는지를 값으로 내려보낸다.** 예전에는 메타에 "고를 수 없음"
    # 이라는 글자만 있었다. 화면이 그 글자를 읽을 수는 없으니 상태를 보고
    # 다시 판단했고, 그러면 정책이 두 곳에 생긴다 — 추론은 미확인이어도
    # 고를 수 있는데 화면이 전부 막아 버렸다.
    return opt("claim:" + c["claim_id"], c["claim"],
               c.get("why", ""), " · ".join(bits),
               {"kind": "확인 대상", "title": c["claim"],
                "citable": policy.citable(c), **c},
               selectable=policy.selectable(c))


LABELS = {
    "supported": "확인됨",
    "partial": "일부 확인",
    "contradicted": "원문과 어긋남",
    "unverified": "확인 필요",
    "invalid_check": "검증 오류",
}


def make(d, inp) -> list[dict]:
    """근거 카드. **카드 하나가 명제 하나다.**

    예전에는 소재 기사와 올린 문서를 카드로 따로 냈다. 그리고 URL 이나
    파일이 있다는 것만으로 "출처 확인됨" 을 달았다. 확인된 것은 **주소가
    존재한다는 사실**뿐이었는데, 그게 그대로 참고자료로 나갔다.

        확인된 것    URL 이 있다
        확인 안 된 것 그 기사가 이 주장을 뒷받침하는가
                     지금 법령과 맞는가
                     전환기간 기준인가 본격 시행 기준인가

    이제 기사도 문서도 **명제 안의 출처로 들어가 대조를 거친다.** 검색이
    찾아온 것과 같은 취급이다. 사람이 고르는 단위는 명제 하나다.
    """
    if not llm.ENABLED:
        return _offline(d)

    # 검증한 명제. 검색이 켜져 있으면 상태가 붙고, 꺼져 있으면 전부 미확인이다.
    sid = d.get("_sid", "")
    rows = verified(d, inp, sid)
    if rows:
        return [_claim_opt(c) for c in rows]

    # 명제를 못 나눴다. 지금까지처럼 "무엇을 어디서 확인할지" 만 만든다 —
    # 여기서 통째로 막으면 사람이 할 수 있는 게 없다.
    out = []
    for i, c in enumerate(llm.candidates("evidence", inp, ("title",))):
        where = c.get("where_to_look") or "미정"
        out.append(opt(
            f"e{i}", z.s(c["title"]),
            c.get("detail") or c.get("claim_to_verify") or "",
            f"{c.get('kind', '근거')} · 찾을 곳 {where} · 출처 미확인",
            payload(c.get("kind", "근거"), z.s(c["title"]),
                    claim_to_verify=c.get("claim_to_verify", ""),
                    where_to_look=c.get("where_to_look", ""))))
    return out


def _offline(d):
    from ...data import fake
    return [opt(e["ev_id"], e["title"], e["detail"],
                f"{e['kind']} · 신뢰도 {e['authority']}", payload(**e))
            for e in fake.load_evidence(d.get("topic_id"))]


def _rows(text):
    return [x.strip() for x in text.splitlines() if x.strip()]


def written(t):
    # 직접 쓴 근거는 URL 이 없다. 확인된 출처가 아니라 확인 대상이다.
    rows = _rows(t)
    return (f"확인 필요 {len(rows)}건", " / ".join(rows),
            {"items": [payload("직접", x) for x in rows]})


def label(picked) -> str:
    """여러 개 골랐을 때의 확정 라벨.

    "N건" 으로 뭉뚱그리면 안 된다. URL 이 붙은 기사와 아직 확인 안 된 대상은
    다른 것이고, 그 차이가 본문에 인용이 붙느냐 마느냐를 가른다.
    """
    linked = sum(1 for o in picked if is_confirmed(o.get("payload")))
    pending = len(picked) - linked
    parts = []
    if linked:
        parts.append(f"확인된 출처 {linked}건")
    if pending:
        parts.append(f"확인 필요 {pending}건")
    return " · ".join(parts) or f"{len(picked)}건"


STEP = Step(
    key="evidence", name="근거", eyebrow="EVIDENCE", h1="근거 선택",
    multi=True, upload=True,
    hint="댈 수 있는 근거를 한 줄에 하나씩.",
    build_input=build_input, make=make, written=written, label=label,
    prompt="prompt.md",
)
