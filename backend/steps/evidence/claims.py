"""검증할 명제를 낱개로 나눈다.

근거 단계의 첫 조각이다. 이 글이 답할 질문을 받아 **이 글이 성립하려면
참이어야 하는 명제**를 뽑는다.

## 왜 낱개인가

한 문장에 두 주장이 섞이면 검증이 성립하지 않는다.

    본격 시행 이후 거래처 요청이 늘고, 통관 일정에도 영향을 줄 수 있다

앞은 공식 자료로 확인되고 뒤는 실무 추론이다. 붙여 두면 절반만 맞는 것을
통째로 맞다고 하거나 통째로 틀렸다고 하게 된다.

## 본문 문장이 아니다

이 단계는 본문보다 앞이라 검증할 문장이 아직 없다. 그래서 claim 은
"본문의 이 문장" 이 아니라 "이 글이 말이 되려면 참이어야 하는 것" 이다.

권고나 표현(`recommendation` · `rhetoric`)이 여기 없는 이유도 그것이다.
그건 본문이 생긴 뒤에야 존재하고, 본문 작성의 검증이 볼 몫이다.

## id 는 코드가 만든다

프롬프트가 `claim_01` 을 지어내게 두면 겹치거나 건너뛴다. 뒤 단계가 이
id 로 원문·대조 결과·섹션 배치를 잇기 때문에, 하나만 어긋나도 조용히
다른 근거가 붙는다.
"""

import pathlib
import time

from ... import llm, prompt as prompts, sanitize as z
from ...record import response as rec
from ..payload import topic_brief
from ..step import label_of, pay
from . import policy, upload

prompts.register("claims", pathlib.Path(__file__).parent / "claims.md")

NAME = "claims"


def build_input(d) -> dict:
    it = pay(d, "intent")
    return {
            # 제목 한 줄로는 이 소재가 실제로 무엇을 다루는지 모른다. 명제를
            # 뽑는 단계라 요약이 제일 필요한 자리다.
            "topic": topic_brief(d, keywords=False),
            "question": it.get("question", ""),
            "sub_questions": it.get("sub_questions", []),
            "angle": pay(d, "angle"),
            "article_type": pay(d, "type").get("article_type", ""),
            "reader": pay(d, "reader"),
            "documents": upload.brief(d)}


def _one(i: int, c: dict) -> dict:
    """후보 하나를 확정 모양으로. id 는 여기서 붙인다."""
    return {
        "claim_id": f"c{i + 1:02d}",
        "claim": z.s(c.get("claim"), 300),
        "claim_type": z.enum(c.get("claim_type"), policy.CLAIM_TYPES) or "interpretation",
        "required_source": z.s(c.get("required_source"), 120),
        "searchable": bool(c.get("searchable", True)),
        "why": z.s(c.get("why"), 200),
        # 아래는 뒤 조각이 채운다. 미리 자리를 두는 이유는 채워지지 않은
        # 명제도 화면과 본문이 같은 모양으로 읽을 수 있어야 하기 때문이다.
        "status": "unverified",
        "authority": "insufficient",
        "reason_code": "",
        "sources": [],
    }


def split(d, inp=None, sid: str = "") -> list[dict]:
    """검증할 명제 목록. 실패하면 빈 목록.

    막지 않는 이유는, 명제를 못 나눴다고 근거 단계가 통째로 멈추면 사람이
    할 수 있는 게 없기 때문이다. 그때는 검색 없이 지금까지처럼 "무엇을
    어디서 확인할지" 만 만든다. 대신 자취에 실패를 남긴다.
    """
    inp = inp or build_input(d)
    t0 = time.perf_counter()
    try:
        got = llm.generate(NAME, inp)
    except llm.LLMError as e:
        rec.failed(sid, NAME, inp, str(e),
                   ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
        return []

    # llm.candidates() 를 안 쓴다. 그쪽은 "candidates" 키를 찾는데 이
    # 프롬프트는 "claims" 를 낸다 — 후보를 고르는 단계가 아니라 검증 대상을
    # 나누는 단계라 이름이 다르다. 검증은 여기서 한다.
    rows = [_one(i, c) for i, c in enumerate(got.get("claims") or [])
            if isinstance(c, dict) and z.s(c.get("claim"))]
    if not rows:
        rec.failed(sid, NAME, inp, "쓸 수 있는 명제가 없다",
                   ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
        return []

    # 검색으로 확인할 수 있는 것을 앞에 둔다. 상한에 걸리면 뒤엣것부터
    # 확인되지 않으므로, 확인 가능한 것이 뒤로 밀리면 안 된다.
    rows.sort(key=lambda c: (not c["searchable"],))

    rec.generated(
        sid, NAME, inp,
        [{"id": c["claim_id"], "title": c["claim"], "summary": c["why"],
          "meta": c["claim_type"], "payload": c} for c in rows],
        model=llm.model_for(False), source="llm", refresh=False,
        ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
    return rows


def to_check(claims) -> tuple[list[dict], list[dict]]:
    """검증에 태울 것과 상한에 걸려 못 태울 것.

    넘친 것을 버리지 않는다. 조용히 사라지면 왜 그 근거가 없는지 알 수 없어서,
    사유를 붙여 미확인으로 남긴다.
    """
    live = [c for c in claims if c["searchable"]]
    rest = [c for c in claims if not c["searchable"]]

    for c in rest:
        c["reason_code"] = "not_searchable"

    over = live[policy.MAX_CLAIMS:]
    for c in over:
        c["reason_code"] = "check_limit_exceeded"

    return live[:policy.MAX_CLAIMS], over + rest
