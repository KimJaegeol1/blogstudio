"""검색하고 본문을 가져온다.

`external/search.py` 를 부르는 쪽이다. 저쪽은 Tavily 를 알고 여기는
**무엇을 몇 개나 가져올지**를 안다.

## 스니펫으로 판정하지 않는다

검색 결과에 딸려 오는 스니펫은 앞뒤 조건이 잘리고 검색어가 든 문장만
강조된다. 그것으로 "이 명제가 뒷받침된다" 를 판정하면 PDF 앞 6,000자만
잘라 쓰던 것과 같은 실패다 — 가장 그럴듯해 보이는 구간을 골라 보내고
정작 조건은 빠진다.

그래서 스니펫은 **어느 것을 가져올지 고르는 데만** 쓴다. 본문을 못 가져온
출처는 대조에 태우지 않고 미확인으로 남긴다.

## 원한 성격과 걸린 성격은 다르다

검색 계획은 `official_primary` 를 **원했다**고만 말한다. 공식 원문을 노린
질의에서 언론 기사가 나오는 일이 흔하고, 그 기사에 `official_primary` 를
붙이면 우선순위 정렬이 무의미해진다.

    requested_target   계획이 노린 성격
    actual_target      도메인을 보고 코드가 매긴 성격 (data/sources.py)

정렬도 자격 판정도 **actual** 로 한다.

## 앞부분만 잘라 넘기지 않는다

법령 원문은 길다. 앞 12,000자만 넘기면 필요한 조항이 뒤에 있을 때
`insufficient` 가 나오고, 결국 짧은 기사만 근거로 남는다.

여기는 `pick.py` 와 상황이 다르다. PDF 는 한글 소제목 대 영문 원문이라
겹치는 낱말이 없어 LLM 이 필요했지만, **웹 원문은 영문 질의로 찾아온
영문 문서**라 낱말이 겹친다. 그래서 코드가 질의 낱말로 구간을 잡는다 —
호출이 늘지 않고, 하나도 못 잡으면 앞부분으로 떨어진다.

## 상태를 네 단계로 나눈다

    discovered   검색 결과에 나타났다
    fetched      본문을 확보했다
    fetch_failed 못 가져왔다. 대조에 태우지 않는다

`checked` 는 여기 없다. 그건 대조가 끝난 뒤 상태라 check.py 몫이다.

## 캐시가 곧 예산이다

같은 URL 이 여러 질의에 나오고, 같은 원문이 여러 명제를 뒷받침한다. 캐시가
없으면 한 편에 같은 문서를 대여섯 번 가져온다. 드래프트에 붙여 두므로
소재를 바꾸면 같이 비워진다 — 다른 글의 근거가 딸려 오지 않는다.

`?refresh=1` 로 후보를 다시 뽑아도 본문 캐시는 살아 있다. 원문이 그 사이
바뀌지 않았기 때문이고, 그래서 refresh 를 여러 갈래로 쪼갤 필요가 아직 없다.
"""

import re
import time

from ... import sanitize as z
from ...data import sources
from ...external import search as api
from ...record import response as rec
from . import policy

NAME = "search"

# 드래프트에 붙는 캐시 자리.
QUERY_KEY = "_search_q"     # 질의 → 결과 목록
TEXT_KEY = "_search_t"      # URL → 본문

def enabled() -> bool:
    """검색을 쓸 수 있나. **상수로 복사해 두지 않는다.**

    `ENABLED = api.ENABLED` 로 두면 import 시점 값이 굳는다. 그 뒤에 키가
    들어오거나 테스트가 저쪽을 바꿔도 이쪽은 옛 값을 든 채로 남는다 —
    두 곳이 다른 답을 내면서 오류는 안 난다.
    """
    return api.ENABLED


def _norm_url(u: str) -> str:
    """캐시 열쇠로 쓸 주소. 조각(#)과 끝 슬래시만 턴다.

    질의 문자열(?)까지 털면 안 된다 — 문서 id 가 거기 붙는 사이트가 많아서
    다른 문서를 같은 것으로 본다.
    """
    u = (u or "").split("#")[0].strip()
    return u[:-1] if u.endswith("/") and u.count("/") > 3 else u


def _cache(d, key) -> dict:
    return d.setdefault(key, {})


def run(d, plans: dict, sid: str = "") -> dict:
    """claim_id → 출처 목록. 본문까지 채운 것만 fetched 다.

    검색이 꺼져 있으면 빈 결과를 준다. 조용히 넘어가는 것이 아니라, 부르는
    쪽이 그 명제를 미확인으로 남기고 화면에 그대로 뜬다.
    """
    # **꺼져 있어도 여기까지 온다.** 부르는 쪽에서 거르면 "검색을 안 했다"
    # 가 어디에도 안 남고, 사람은 "찾았는데 없었다" 와 구별할 수 없다.
    if not enabled():
        rec.failed(sid, NAME, {"plans": plans},
                   "TAVILY_API_KEY 가 없어 검색하지 않았다", ms=0)
        return {}
    if not plans:
        return {}

    found: dict[str, list[dict]] = {}
    t0 = time.perf_counter()
    calls = {"search": 0, "fetch": 0, "cached": 0}

    for claim_id, queries in plans.items():
        rows = []
        for q in queries:
            rows += _one_query(d, q, calls, sid)
        found[claim_id] = _pick(d, rows, calls, sid)

    rec.generated(
        sid, NAME, {"plans": plans},
        [{"id": cid, "title": f"{len(rows)}건",
          "summary": " / ".join(r["title"] for r in rows[:2]),
          "meta": ",".join(sorted({r["status"] for r in rows})),
          "payload": {"sources": [{k: v for k, v in r.items() if k != "text"}
                                  for r in rows]}}
         for cid, rows in found.items()],
        model="tavily", source="search", refresh=False,
        ms=round((time.perf_counter() - t0) * 1000),
        raw=z.s(str(calls), 200))
    return found


def _one_query(d, q, calls, sid) -> list[dict]:
    """질의 하나. 캐시가 맞으면 부르지 않는다."""
    cache = _cache(d, QUERY_KEY)
    key = f"{q['language']}|{q['source_target']}|{q['query']}"
    if key in cache:
        calls["cached"] += 1
        rows = cache[key]
    else:
        try:
            rows = api.search(q["query"], q["language"])
            calls["search"] += 1
        except api.CallError as e:
            # 질의 하나가 실패해도 나머지는 돈다. 다만 남긴다 —
            # 조용히 넘어가면 왜 근거가 적은지 알 수 없다.
            rec.failed(sid, NAME, {"query": q}, str(e), ms=0)
            rows = []
        cache[key] = rows

    out = []
    for r in rows:
        url = _norm_url(r["url"])
        out.append({**r, "url": url,
                    # 원한 것과 걸린 것을 나눠 든다.
                    "requested_target": q["source_target"],
                    "actual_target": sources.classify(url),
                    "query": q["query"],
                    "status": "discovered", "text": ""})
    return out


# 구간 하나의 길이와 개수. 법령 조항 하나가 대개 이 안에 들어간다.
WINDOW = 2500
MAX_WINDOWS = 4

_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{3,}|[가-힣]{2,}")
# 어디에나 있는 말은 신호가 아니다.
_STOP = {"the", "and", "for", "with", "that", "from", "shall", "this",
         "which", "under", "data", "information"}


def _windows(text: str, query: str) -> str:
    """질의 낱말이 몰린 구간만 남긴다.

    앞부분만 자르면 필요한 조항이 뒤에 있을 때 통째로 놓친다. 질의는
    영문이고 원문도 영문이라 낱말이 겹치므로, 어디를 봐야 하는지 코드가
    안다 — 호출을 하나 더 쓰지 않는다.

    하나도 못 잡으면 앞부분을 준다. 지금보다 나빠지지 않는다.
    """
    text = text or ""
    if len(text) <= WINDOW * MAX_WINDOWS:
        return text

    words = {w.lower() for w in _WORD.findall(query or "")} - _STOP
    if not words:
        return text[:WINDOW * MAX_WINDOWS]

    low = text.lower()
    hits = sorted({m.start() for w in words
                   for m in re.finditer(re.escape(w), low)})
    if not hits:
        return text[:WINDOW * MAX_WINDOWS]

    # 가까운 자리끼리 묶어 구간으로. 겹치면 하나로 본다.
    spans, start, end = [], hits[0], hits[0]
    for h in hits[1:]:
        if h - end <= WINDOW:
            end = h
        else:
            spans.append((start, end))
            start = end = h
    spans.append((start, end))

    # 낱말이 많이 몰린 구간부터
    spans.sort(key=lambda sp: -sum(1 for h in hits if sp[0] <= h <= sp[1]))
    keep = sorted(spans[:MAX_WINDOWS])

    out = []
    for a, b in keep:
        lo = max(0, a - WINDOW // 4)
        hi = min(len(text), b + WINDOW)
        out.append(text[lo:hi])
    return "\n\n[...]\n\n".join(out)


def _pick(d, rows, calls, sid) -> list[dict]:
    """우선순위대로 본문을 가져온다. 상한까지만.

    성격이 앞선 것을 먼저 가져온다. 본문 가져오기가 비싸서 **순서가 곧
    예산**이다 — 뒤엣것은 아예 안 가져온다.
    """
    seen, uniq = set(), []
    for r in sorted(rows, key=policy.rank):
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        uniq.append(r)

    texts = _cache(d, TEXT_KEY)
    got = 0
    for r in uniq:
        if got >= policy.MAX_FETCH:
            break
        url = r["url"]
        if url in texts:
            calls["cached"] += 1
            r["text"], r["status"] = texts[url], "fetched"
            got += 1
            continue
        try:
            r["text"] = _windows(api.fetch(url), r.get("query", ""))
            calls["fetch"] += 1
            r["status"] = "fetched"
            texts[url] = r["text"]
            got += 1
        except api.CallError as e:
            # 스니펫으로 대신하지 않는다. 본문이 없으면 판정하지 않는다.
            r["status"] = "fetch_failed"
            r["error"] = str(e)[:200]
    return uniq
