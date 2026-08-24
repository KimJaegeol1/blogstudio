"""5단계 — 각도.

이 소재를 **어떤 판단 축에서 해석할지** 정한다.

독자를 다시 정하는 자리가 아니다. 그건 앞 단계에서 끝났다. 여기서 정하는
것은 이미 정해진 독자의 질문에 **무엇을 중심에 놓고 답할지**다.

    prompt.md    후보 3~4개
    written.md   사람이 쓴 한 줄에 판단 축과 톤만 채운다

직접 쓴 한 줄은 그대로 `core_message` 가 된다.

`intent.question` 을 본다. 안 보면 같은 소재·독자에서 질문이 달라도 비슷한
각도가 나온다 — 검색의도 단계를 만든 이유가 없어지는 자리다.

**근거 검증보다 앞이다.** `core_message` 는 이후 검증할 중심 논지이지
확인된 결론이 아니다.
"""

from ... import llm, sanitize as z
from ..payload import topic_brief, topic_keywords
from ..step import Step, label_of, opt, pay, pick_meta, pick_meta


# 톤 상한. 정확히 3개를 요구했더니 거의 모든 후보가 "실무적·차분한·근거중심"
# 으로 채워졌다. 톤은 채널 프롬프트와 브랜드 규칙이 다시 조절하므로 여기서는
# 핵심만 있으면 된다.
MAX_TONE = 3


def payload(viewpoint, message, differentiation="", tone=()) -> dict:
    """확정값 한 벌.

    `differentiation` 은 이 후보가 다른 후보와 무엇이 다른지다. 예전에는
    프롬프트가 `rationale` 을 만들게 해놓고 코드가 버렸다 — 모델에게 이유를
    쓰게 하고 아무도 안 읽는 상태였다.
    """
    return {"viewpoint": z.s(viewpoint), "core_message": z.s(message),
            "differentiation": z.s(differentiation, 200),
            "tone": z.texts(tone, MAX_TONE)}


def build_input(d) -> dict:
    return {
        # 제목 한 줄만 넘기면 각도가 소재의 범위를 모른다. 요약과 키워드가
        # 다르면 같은 제목이라도 다룰 것이 다르다.
        "topic": topic_brief(d),
        "reader": pay(d, "reader"),
        # 이 글이 답할 질문. 각도는 그 질문에 어떤 축으로 답할지 정하는 것이다.
        "intent": pay(d, "intent"),
        # 같은 질문이라도 홈페이지는 도입을 검토하는 사람, 네이버는 처음
        # 검색한 사람이라 판단 축이 달라진다.
        "channel": pay(d, "channel"),
    }


def make(d, inp) -> list[dict]:
    # tone 은 필수에서 뺀다. 없어도 글이 나오는 값인데 필수로 두면 그것
    # 하나 빠뜨린 후보가 통째로 버려진다.
    cands = (llm.candidates("angle", inp,
                            ("viewpoint", "core_message", "differentiation"))
             if llm.ENABLED else _offline(d, inp))
    out = []
    for i, c in enumerate(cands):
        p = payload(c["viewpoint"], c["core_message"],
                    c.get("differentiation"), c.get("tone") or [])
        tone = "톤 " + " / ".join(p["tone"]) if p["tone"] else ""
        meta = " · ".join(x for x in [p["differentiation"], tone] if x)
        # 첫 후보가 추천이다. 왜 추천인지는 differentiation 이 이미 들고 있다.
        out.append(opt(f"a{i}", p["viewpoint"], p["core_message"],
                       pick_meta(p["differentiation"], tone) if i == 0 else meta, p))
    return out


def _offline(d, inp=None):
    """키 없이 돌 때. 앞 단계 값에서 만들어 화면 흐름만 확인한다.

    질문을 기준으로 만든다. 예전에는 화자의 상황(당장 할 일 / 결재 설득 /
    겪어 본 사람)만 바꿔서, 질문이 달라도 같은 넷이 나왔다.
    """
    it = (inp or {}).get("intent") or pay(d, "intent")
    q = it.get("question") or "이 질문"
    subs = it.get("sub_questions") or []
    subject = label_of(d, "topic") or "이 주제"
    return [
        {"viewpoint": "공식적으로 달라진 것을 기준으로 본다",
         "core_message": f"{subject}, 무엇이 실제로 달라졌는지부터 구분해야 한다.",
         "differentiation": "내부 대응 방법보다 제도가 정한 변화를 먼저 짚는다.",
         "tone": ["정확한", "실무적"]},
        {"viewpoint": "지금 가진 것을 다시 쓸 수 있는지를 기준으로 본다",
         "core_message": f"{subject}, 가진 자료가 지금 기준에 맞는지가 먼저다.",
         "differentiation": "새로 준비할 것보다 기존 자료의 재사용 가능성을 중심에 둔다.",
         "tone": ["실무적", "차분한"]},
        {"viewpoint": (f"{subs[0]}에서 본다" if subs
                       else "요청을 받는 쪽의 업무 흐름에서 본다"),
         "core_message": f"{q} — 답은 업무 순서에서 나온다.",
         "differentiation": "제도 설명보다 실제로 막히는 지점을 중심에 둔다.",
         "tone": ["구체적", "실무적"]},
    ]


def written(t):
    return t, "직접 쓴 각도", payload(t, t, "사람이 직접 정한 중심 논지")


def fill(t, got, v):
    p = payload(
        z.s(got.get("viewpoint")) or t,          # 못 채우면 쓴 말로 둔다
        t,                                       # 쓴 말 그대로
        z.s(got.get("differentiation"), 200) or "사람이 직접 정한 중심 논지",
        z.texts(got.get("tone"), MAX_TONE))
    v["payload"] = p
    v["detail"] = p["viewpoint"] + (
        " · 톤 " + " / ".join(p["tone"]) if p["tone"] else "")
    return v


STEP = Step(
    key="angle", name="각도", eyebrow="ANGLE", h1="각도 선택",
    hint="무슨 말을 할지 한 줄로. 예) 가진 자료가 지금 기준에 맞는지가 먼저다\n"
         "적은 말은 그대로 두고 판단 축·톤만 자동으로 채웁니다.",
    build_input=build_input, make=make, written=written, fill=fill,
    prompt="prompt.md", prompt_written="written.md",
)
