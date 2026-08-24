"""명제를 원문과 대조한다.

근거 단계의 마지막 조각이다. **여기서 상태가 정해진다.**

## 역할을 가른다

    LLM     의미가 대응하는가(verdict) · 원문의 어느 대목인가(evidence_spans)
    코드    그 대목이 원문에 실제로 있는가 → 상태

모델이 자기 출력에 "이건 사실이다" 라고 적으면 그건 검증이 아니라 주장이다.
그래서 `supported` 라는 낱말은 프롬프트가 못 쓰게 하고, 인용한 대목을 원문에서
찾아본 뒤 `policy.status_of()` 가 정한다. 못 찾으면 `invalid_check` 다 —
지어낸 인용에 출처가 붙는 것을 막는 자리다.

## 한 번 다시 묻는다

`invalid_check` 는 모델이 인용을 다듬었을 때 자주 난다. 원문 그대로 옮기라고
한 번 더 이르면 대개 고쳐진다. 다만 **상한을 둔다** — 없으면 같은 인용으로
무한히 돈다.

## 상한에 걸린 것을 버리지 않는다

명제 × 출처가 곧 호출 수다. 상한을 넘으면 그 쌍은 안 돌지만, 그 명제를
조용히 없애지 않고 `check_limit_exceeded` 를 달아 미확인으로 남긴다.
사라지면 왜 근거가 없는지 알 수 없다.
"""

import pathlib
import time

from ... import llm, prompt as prompts, sanitize as z
from ...record import response as rec
from . import policy

prompts.register("check", pathlib.Path(__file__).parent / "check.md")

NAME = "check"

# 원문 한 벌을 프롬프트에 실을 때의 길이. 너무 길면 대조가 흐려지고
# 호출당 비용이 그대로 붙는다.
MAX_TEXT = 12000


def _ask(claim, source, sid, note="") -> tuple[dict, int]:
    inp = {
        "claim": claim["claim"],
        "claim_type": claim["claim_type"],
        "source": {"title": source.get("title", ""), "url": source.get("url", ""),
                   "text": (source.get("text") or "")[:MAX_TEXT]},
    }
    if note:
        inp["note"] = note

    t0 = time.perf_counter()
    try:
        got = llm.generate(NAME, inp)
    except llm.LLMError as e:
        rec.failed(sid, NAME, inp, str(e),
                   ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
        return {}, round((time.perf_counter() - t0) * 1000)
    return got, round((time.perf_counter() - t0) * 1000)


def _spans(got, text) -> list[dict]:
    """원문에 실제로 있는 대목만 남긴다."""
    out = []
    for s in (got.get("evidence_spans") or []):
        if not isinstance(s, dict):
            continue
        q = z.s(s.get("quote"), 600)
        if q and policy.span_ok(q, text):
            out.append({"quote": q, "location": z.s(s.get("location"), 80)})
    return out


def one(claim, source, sid: str = "") -> dict:
    """명제 하나 × 출처 하나. 판정을 붙인 출처를 돌려준다."""
    text = source.get("text") or ""
    got, ms = _ask(claim, source, sid)
    status, reason = policy.status_of(got, text)

    tries = 0
    while status == "invalid_check" and tries < policy.MAX_RETRY:
        tries += 1
        got, ms = _ask(claim, source, sid,
                       note="앞서 인용한 대목을 원문에서 찾지 못했습니다. "
                            "원문에 있는 글자를 그대로 옮겨 주십시오.")
        status, reason = policy.status_of(got, text)

    row = {
        "source_id": source.get("url") or source.get("file", ""),
        "title": source.get("title", ""),
        "url": source.get("url", ""),
        "file": source.get("file", ""),
        "source_name": source.get("source_name", ""),
        # 계획이 원한 성격과 실제로 걸린 성격은 다르다. 정렬도 자격 판정도
        # actual 로 한다 — requested 로 하면 공식 원문을 노린 질의에 걸린
        # 기사가 공식 원문 행세를 한다.
        "requested_target": source.get("requested_target", ""),
        "actual_target": source.get("actual_target", ""),
        "verdict": policy.verdict_of(got),
        "status": status,
        "evidence_spans": _spans(got, text),
        "supported_parts": z.texts(got.get("supported_parts"), 4),
        "unsupported_parts": z.texts(got.get("unsupported_parts"), 4),
        "reason": z.s(got.get("reason"), 300),
        "limitations": z.texts(got.get("limitations"), 3),
        "retried": tries,
        "ms": ms,
    }

    # **성공도 남긴다.** 실패만 남기면 "이 명제를 이 원문과 대조했더니
    # 이렇게 나왔다" 가 어디에도 없어서, 대조 프롬프트를 고칠 근거가 사라진다.
    # 특히 invalid_check 가 얼마나 자주 나는지는 이 기록으로만 안다.
    rec.generated(
        sid, NAME,
        {"claim": claim["claim"], "claim_type": claim["claim_type"],
         "source": {"title": source.get("title", ""), "url": source.get("url", ""),
                    "chars": len(text)}},
        [{"id": claim["claim_id"], "title": claim["claim"],
          "summary": row["reason"], "meta": f'{row["verdict"]} → {row["status"]}',
          "payload": row}],
        model=llm.model_for(False), source="llm", refresh=bool(tries),
        ms=ms, raw=llm.raw(NAME))
    return row


# 판정기가 바뀌면 옛 결과를 쓰면 안 된다. 프롬프트나 판정 규칙을 고칠 때
# 이 값을 올린다.
VERSION = 1

# 다시 대조해도 같은 답이 나오는 상태만 담는다. 상한에 걸렸거나 실패한 것은
# 다음번엔 될 수도 있으므로 담지 않는다.
# 낱말 앞 몇 글자로 볼지. 조사·어미를 떼려는 것이다.
STEM = 3

# 낱말이 이만큼 겹치면 같은 명제로 본다.
#
# **짧은 명제는 낱말 하나 차이가 크다.** "적용되었다" 와 "적용된다" 만
# 달라도 네 낱말짜리면 0.75 로 떨어진다. 서로 다른 명제끼리는 재 보니
# 0.25 를 안 넘으므로 여유가 있다.
SAME = 0.7

REUSABLE = ("supported", "partial", "contradicted", "unverified")

# (본문 지문, 명제 지문, 판정기 판) → 판정. 세션 안에서만 산다.
_SEEN: dict = {}

# 명제 열쇠 → 그 명제. 표현이 바뀌어도 같은 열쇠를 찾으려고 든다.
_KEYS: dict = {}


def _mark(text: str) -> str:
    """본문 지문. **주소가 아니라 내용으로 잡는다** — 같은 주소라도 글이
    바뀌면 옛 판정을 쓰면 안 된다."""
    import hashlib
    return hashlib.sha256(policy.norm(text or "").encode()).hexdigest()[:16]


def _use(sid: str) -> None:
    """이 드래프트의 캐시로 바꾼다. 바뀌면 앞의 것을 버린다."""
    if _SEEN.get("_sid") != sid:
        _SEEN.clear(); _KEYS.clear()
        _SEEN["_sid"] = sid


def _claim_key(c: dict) -> str:
    """캐시에서 이 명제를 가리키는 열쇠.

    **문구가 흔들려도 같아야 한다.** 이미 담아 둔 것 중 같은 명제가 있으면
    그 열쇠를 쓴다 — 표현이 조금 바뀐 것을 새 명제로 보면 캐시가 안 맞는다.
    """
    for key, kind in list(_KEYS.items()):
        if same_claim(c, kind):
            return key
    import hashlib
    key = hashlib.sha256(
        f'{c.get("claim_type","")}|{policy.norm(c.get("claim") or "")}'.encode()
    ).hexdigest()[:16]
    _KEYS[key] = {"claim": c.get("claim"), "claim_type": c.get("claim_type")}
    return key


def _stems(text: str) -> set:
    return z.stems(policy.norm(text or ""))


def same_claim(a: dict, b: dict) -> bool:
    """두 명제가 같은 것인가.

    **문구가 조금 바뀌어도 같아야 한다.** PDF 를 올리면 명제를 다시 만드는데,
    "전환기간에는 CBAM 대상..." 이 "CBAM 전환기간에는 대상..." 으로 바뀌는
    정도로 표현이 흔들린다. 그때마다 다시 대조하면 검증이 통째로 두 번
    돈다 — 실제로 4분이 걸렸다.

    지문(해시)으로는 못 잡는다. `적용되었다` 와 `적용된다` 는 앞 세 글자도
    다르다. **낱말이 얼마나 겹치는지**로 본다. 종류가 다르면 다른 명제다 —
    같은 문장이라도 규정과 해석은 대조 기준이 다르다.
    """
    if a.get("claim_type") != b.get("claim_type"):
        return False
    x, y = _stems(a.get("claim")), _stems(b.get("claim"))
    if not x or not y:
        return False
    return len(x & y) / max(len(x), len(y)) >= SAME


def run(claims, found: dict, sid: str = "", searched=True) -> list[dict]:
    """명제 목록에 판정을 채운다. 같은 목록을 고쳐서 돌려준다.

    **하나가 실패해도 나머지는 돈다.** 대조가 통째로 막히면 사람이 할 수
    있는 게 없다.
    """
    budget = policy.MAX_CHECKS
    # 캐시는 **한 드래프트 안에서만** 산다. 다른 글의 판정을 물고 오면
    # 본문이 바뀌었는데 옛 답을 쓰는 일이 생긴다.
    _use(sid)

    for c in claims:
        rows = [s for s in (found.get(c["claim_id"]) or [])
                if s.get("status") == "fetched" and s.get("text")]
        if not rows:
            # 본문을 하나도 못 가져왔다. 스니펫으로 대신하지 않는다.
            # **왜 없는지를 갈라 적는다.** 검색을 안 한 것과 찾았는데
            # 없는 것은 사람이 할 일이 다르다.
            c["status"] = "unverified"
            if not c["reason_code"]:
                if not searched:
                    c["reason_code"] = "search_disabled"
                elif found.get(c["claim_id"]):
                    c["reason_code"] = "fetch_failed"
                else:
                    c["reason_code"] = "no_search_result"
            continue

        checked = []
        for s in rows:
            # 같은 명제를 같은 본문에 대조한 적이 있으면 그 답을 쓴다.
            # **예산도 안 쓴다** — 다시 물어도 같은 답이 나온다.
            key = (_mark(s.get("text")), _claim_key(c), VERSION)
            got = _SEEN.get(key)
            if got:
                checked.append({**got, "cached": True})
                continue
            if budget <= 0:
                c["reason_code"] = "check_limit_exceeded"
                break
            budget -= 1
            row = one(c, s, sid)
            checked.append(row)
            # 다시 대조해도 같은 답이 나오는 것만 담는다. 상한에 걸렸거나
            # 실패한 것은 다음번엔 될 수도 있다.
            if row.get("status") in REUSABLE:
                _SEEN[key] = row

        c["sources"] = checked
        c["status"] = policy.best([x["status"] for x in checked])
        # 자격은 **뒷받침한 출처만** 본다. 반박하거나 못 미친 출처의 성격이
        # 자격을 올려 주면 안 된다.
        c["authority"] = policy.authority_of(
            c["claim_type"],
            [x["actual_target"] for x in checked
             if x["status"] in ("supported", "partial")])
        if c["status"] == "unverified" and not c["reason_code"]:
            c["reason_code"] = "no_source"

    return claims
