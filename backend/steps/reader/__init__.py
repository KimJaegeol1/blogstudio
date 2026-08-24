"""3단계 — 독자.

이 글을 누구에게 쓸지 정한다. 입력은 소재 제목 한 줄이 전부다.

    prompt.md    후보 3~4개를 만든다
    written.md   사람이 한 줄로 쓴 독자에 부속 항목만 채운다

직접 쓴 한 줄은 그대로 `role` 이 된다. 프롬프트는 role 을 아예 출력하지
않도록 막아 뒀고, 코드가 사람이 쓴 말을 그대로 넣는다.
"""

from ... import llm, sanitize as z
from ..step import Step, label_of, opt, pay, pick_meta

LEVELS = ("입문", "실무", "전문가")
AUTHORITY = ("결정권자", "추천자", "영향자")


def payload(role, **extra) -> dict:
    """확정값 한 벌.

    avoid_terms 는 3·5·6단계 프롬프트가 "이 표현은 쓰지 마라" 로 읽는다.
    기본값이 없으면 직접 쓴 독자에서 키가 통째로 빠져 규칙이 죽는다.
    """
    return {"role": role, "expertise_level": "미지정",
            "decision_authority": "미지정",
            "preferred_terms": [], "pain_points": [], "avoid_terms": [], **extra}


def build_input(d) -> dict:
    # 채널이 독자를 좁힌다. 같은 소재라도 네이버는 처음 검색한 사람,
    # 홈페이지는 도입을 검토하는 사람이다.
    return {"topic": label_of(d, "topic"), "channel": pay(d, "channel")}


def make(d, inp) -> list[dict]:
    cands = (llm.candidates("reader", inp, ("role",))
             if llm.ENABLED else _offline(d))
    out = []
    for i, p in enumerate(cands):
        # 첫 후보가 추천이다. 프롬프트가 "이 소재에 가장 맞는 독자를 앞에"
        # 라고 이미 정해 두었다 — is_main 은 모델이 붙이는 표시고, 없으면
        # 순서를 따른다.
        main = p.get("is_main", i == 0)
        meta = (f"{p.get('expertise_level', '미지정')} · "
                f"{p.get('decision_authority', '미지정')} · "
                f"쓰는 말 {', '.join(p.get('preferred_terms') or [])}")
        out.append(opt(
            f"p{i}", p["role"],
            " / ".join(p.get("pain_points") or []),
            pick_meta(meta, p.get("why_main")
                      or "이 소재를 실제로 찾아보는 사람") if main else meta,
            payload(**p)))
    return out


def _offline(d):
    from ...data import fake
    return fake.load_personas(d.get("topic_id"))


def written(t):
    return t, "직접 쓴 독자", payload(t)


def fill(t, got, v):
    """written.md 가 채워 온 것을 검증해서 확정값에 얹는다.

    사람이 쓴 말은 코드가 그대로 넣는다. 모델이 다듬어 온 role 이 있어도
    쓰지 않는다 — 직접 쓰기의 목적이 그것이다.
    """
    p = payload(
        t,                                                  # 쓴 말 그대로
        expertise_level=z.enum(got.get("expertise_level"), LEVELS) or "실무",
        decision_authority=z.enum(got.get("decision_authority"), AUTHORITY) or "추천자",
        pain_points=z.texts(got.get("pain_points"), 3),
        preferred_terms=z.texts(got.get("preferred_terms"), 4),
        avoid_terms=z.texts(got.get("avoid_terms")))
    v["payload"] = p
    v["detail"] = " · ".join(x for x in [
        p["expertise_level"], p["decision_authority"],
        " / ".join(p["pain_points"])] if x)
    return v


STEP = Step(
    key="reader", name="독자", eyebrow="READER", h1="독자 선택",
    hint="누가 읽을지 한 줄로. 예) 협력사 자료 요청을 받는 구매 담당자\n"
         "적은 말은 그대로 두고 이해 수준·자주 막히는 지점만 자동으로 채웁니다.",
    build_input=build_input, make=make, written=written, fill=fill,
    prompt="prompt.md", prompt_written="written.md",
)
