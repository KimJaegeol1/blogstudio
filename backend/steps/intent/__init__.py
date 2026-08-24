"""4단계 — 검색의도.

이 글이 **어떤 질문에 답하는가**를 정한다. 독자의 속성이 아니라 이 글의
성격이라 독자 단계와 나눈다 — 같은 통관 담당자라도 "무엇이 달라졌나"와
"요청을 받으면 어떻게 대응하나"는 다른 글이다. 독자에 접으면 독자를 고칠
때 질문까지 흔들린다.

`question` 이 뒤로 멀리 간다.

    근거 단계    검증할 명제를 뽑는 기준
    구조 단계    답해야 할 중심 질문
    제목 단계    제목이 질문에서 벗어났는지 보는 기준

그래서 사람이 확인하고 넘어가야 한다. 여기가 엇나가면 뒤가 통째로 엇나간다.

`search_intent` 는 영문 enum 이고 화면 표시만 코드가 한글로 바꾼다. 자유
문자열로 두면 "정보탐색"·"정보 탐색"·"탐색형" 이 섞여 들어와 뒤 단계 규칙이
조용히 죽는다.

**질문을 먼저 만들고 의도를 나중에 분류한다.** 예전에는 후보마다 의도가
달라야 한다고 요구했는데, 그러면 분류 체계가 질문을 지배한다 — 정보 탐색
단계 독자에게 "무엇을 기준으로 고를까"(commercial)를 억지로 묻게 되고,
그건 채널 규칙과 정면으로 부딪힌다.

    prompt.md    후보 3~4개
    written.md   사람이 쓴 질문 한 줄에 부속 항목만 채운다
"""

from ... import llm, sanitize as z
from ..payload import topic_brief, topic_keywords
from ..step import Step, label_of, opt, pay, pick_meta, pick_meta

# 화면 표시는 코드가 한다. 프롬프트는 영문 값만 쓴다.
INTENTS = {
    "informational": "정보 탐색",
    "procedural": "절차 확인",
    "commercial": "비교·검토",
    "transactional": "문의·실행",
}

# 하위 질문 상한. 많으면 근거 단계가 검증할 명제 범위를 그만큼 넓힌다.
MAX_SUB = 3


def payload(question, **extra) -> dict:
    """확정값 한 벌.

    기본값을 두는 이유는 직접 쓴 경우다. 키가 통째로 빠지면 그것을 읽는
    뒤 단계 규칙이 KeyError 없이 조용히 죽는다.
    """
    return {"question": question, "search_intent": "informational",
            "sub_questions": [], "desired_action": "", **extra}


def build_input(d) -> dict:
    """소재 · 채널 · 독자.

    소재를 제목 한 줄로 넘기면 질문이 일반적으로 흐른다. 요약과 키워드가
    있어야 이 소재가 실제로 어디까지 다루는지 안다.

    키워드는 소재가 들고 온 것을 쓴다. 예전에는 `fake.load_keywords()` 를
    따로 불렀는데, 소재 계약에 이미 있는 값을 가짜 데이터로 다시 가져오는
    셈이었다.
    """
    ch = pay(d, "channel")
    return {
        "topic": topic_brief(d),
        # 필요한 것만 추린다. 통째로 넘기면 안 쓰는 값이 매 호출에 실린다.
        "channel": {k: ch.get(k, "") for k in
                    ("channel", "channel_goal", "reader_stage")},
        "reader": pay(d, "reader"),
    }


def _one(p) -> dict:
    """LLM 이 준 후보 하나를 확정값 모양으로. 목록 밖 값은 걸러 낸다."""
    return payload(
        z.s(p.get("question"), 200),
        search_intent=z.enum(p.get("search_intent"), INTENTS) or "informational",
        sub_questions=z.texts(p.get("sub_questions"), MAX_SUB),
        desired_action=z.s(p.get("desired_action"), 120))


def make(d, inp) -> list[dict]:
    cands = (llm.candidates("intent", inp,
                            ("question", "search_intent", "desired_action"))
             if llm.ENABLED else _offline(d, inp))
    out = []
    for i, p in enumerate(cands):
        v = _one(p)
        # rationale 은 왜 이 독자가 이 질문을 하는지다. 화면에만 쓰고
        # 확정값에는 안 넣는다 — 뒤 단계가 읽을 값이 아니다. 예전에는
        # 만들게 해놓고 아무 데도 안 썼다.
        why = z.s(p.get("rationale"), 180)
        # 이유는 한 번만 보인다. 추천 말머리에 넣으면 뒤에 또 붙이지
        # 않는다 — 같은 문장이 한 줄에 두 번 나온다.
        rest = " · ".join(x for x in [
            INTENTS[v["search_intent"]],
            f"읽고 나서 {v['desired_action']}" if v["desired_action"] else ""] if x)
        # 첫 후보가 추천이다. 프롬프트가 "이 독자가 가장 먼저 할 질문을
        # 첫 번째로" 라고 이미 정해 두었다.
        meta = (pick_meta(rest, why) if i == 0
                else " · ".join(x for x in [rest, why] if x))
        out.append(opt(f"q{i}", v["question"],
                       " / ".join(v["sub_questions"]), meta, v))
    return out


def _offline(d, inp):
    """키 없이 돌 때. 앞 단계 값에서 만들어 화면 흐름만 확인한다.

    **의도 종류를 채우지 않는다.** 예전에는 informational·procedural·
    commercial 을 하나씩 만들었는데, 정보 탐색 단계 독자에게 "대응 방식을
    어떤 기준으로 고르는가" 는 아직 하지 않는 질문이다.
    """
    reader = inp.get("reader") or {}
    topic = inp.get("topic") or {}
    role = reader.get("role") or "실무 담당자"
    head = topic.get("headline") or "이 소재"
    stage = (inp.get("channel") or {}).get("reader_stage", "")

    rows = [{"search_intent": "informational",
             "question": f"{head}에서 무엇이 달라지는가?",
             "sub_questions": [],
             "desired_action": "자사 업무에 영향을 주는 변화를 구분한다",
             "rationale": f"{role}가 먼저 변화의 범위를 확인하는 질문이다."}]
    if stage != "정보 탐색":
        rows.append({"search_intent": "procedural",
                     "question": f"{head} 대응에서 무엇부터 확인해야 하는가?",
                     "sub_questions": [],
                     "desired_action": "먼저 확인할 자료와 업무를 정한다",
                     "rationale": f"{role}의 대응 준비에 필요한 질문이다."})
    return rows


def written(t):
    return t, "직접 쓴 질문", payload(t)


def fill(t, got, v):
    """written.md 가 채워 온 것을 검증해서 확정값에 얹는다.

    사람이 쓴 질문은 코드가 그대로 넣는다. 모델이 다듬어 온 question 이
    있어도 쓰지 않는다 — 직접 쓰기의 목적이 그것이다.
    """
    p = payload(
        t,                                              # 쓴 말 그대로
        search_intent=z.enum(got.get("search_intent"), INTENTS) or "informational",
        sub_questions=z.texts(got.get("sub_questions"), MAX_SUB),
        desired_action=z.s(got.get("desired_action"), 120))
    v["payload"] = p
    v["detail"] = " · ".join(x for x in [
        INTENTS[p["search_intent"]], " / ".join(p["sub_questions"])] if x)
    return v


STEP = Step(
    key="intent", name="검색의도", eyebrow="INTENT", h1="검색의도 선택",
    hint="이 글이 답할 질문 한 줄로. 예) 거래처 자료 요청을 받으면 무엇부터 확인해야 하나\n"
         "적은 질문은 그대로 두고 하위 질문과 독자 행동만 자동으로 채웁니다.",
    build_input=build_input, make=make, written=written, fill=fill,
    prompt="prompt.md", prompt_written="written.md",
)
