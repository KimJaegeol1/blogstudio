"""6단계 — 글 유형.

목록 여섯 개는 코드가 들고 있고, 프롬프트는 어느 게 맞는지 고르기만 한다.
후보를 만드는 단계가 아니라 **추천과 부적합 표시를 얹는** 단계다.

**제목 분류기가 아니다.** 확정된 질문(`intent.question`)을 어떤 글 형식으로
답할지 고르는 단계다. 예전에는 프롬프트가 제목 단어로 유형을 정했다 —
"적용" 이 들어가면 케이스형, "확인" 이 들어가면 체크리스트형. 그런데
"CBAM 적용 대상은 무엇인가" 는 정보형이고 "적용 여부 확인 방법" 은
가이드형일 수 있다.

직접 쓰기를 받지 않는다(custom=False). 정해진 여섯 개 밖의 값이 들어오면
구조 단계에서 골격을 못 찾고 조용히 일반 구조로 흐른다. 같은 이유로 모델이
낸 추천 이름도 목록에 있는지 확인한다 — "동향" · "trend" 가 오면 추천이
조용히 사라진다.
"""

from ... import llm, sanitize as z
from ...data import skeletons
from ..payload import topic_brief, topic_keywords
from ..step import Step, label_of, opt, pay

# (이름, 독자가 얻는 것, 어떤 질문에 맞나)
#
# 세 번째 값은 **화면 메타 문구**다. 검색의도 enum 목록을 여기 적지 않는다 —
# 프롬프트가 그것을 매핑표로 읽고 기계적으로 대응시킨다. 같은
# `informational` 이라도 "무엇인가" 는 정보형이고 "무엇이 달라졌나" 는
# 동향형이다.
ARTICLE_TYPES = [
    ("정보형",      "개념·제도·구성을 설명한다",      "무엇인지 묻는 질문에"),
    ("가이드형",    "실제로 할 방법과 순서를 준다",   "어떻게 하는지 묻는 질문에"),
    ("비교형",      "같은 기준으로 나란히 놓는다",    "무엇이 다른지 묻는 질문에"),
    ("케이스형",    "실제 수행 사례를 뜯어본다",      "실제로 어땠는지 묻는 질문에"),
    ("동향형",      "최근 변화와 영향을 전달한다",    "무엇이 달라졌는지 묻는 질문에"),
    ("체크리스트형", "기준별로 현재 상태를 점검한다",  "우리는 어떤지 묻는 질문에"),
]

NAMES = tuple(n for n, _, _ in ARTICLE_TYPES)

# 이름이 어긋나면 구조 단계가 골격을 못 찾고 조용히 일반 구조로 흐른다.
# 예전에는 "사람이 맞춰 둔 것" 이라고 주석만 있었다 — 조용히 흐르는 것보다
# 뜨자마자 터지는 편이 낫다.
_missing = set(NAMES) - set(skeletons.TYPES)
_extra = set(skeletons.TYPES) - set(NAMES)
if _missing or _extra:
    raise RuntimeError(
        f"글 유형 이름이 skeletons.TYPES 와 어긋난다: "
        f"없는 것={sorted(_missing)} 남는 것={sorted(_extra)}")


def payload(name, reason="") -> dict:
    """확정값 한 벌.

    `type_reason` 은 왜 이 유형인지다. 예전에는 프롬프트가 이유를 만들게
    해놓고 화면에만 쓰고 버렸다 — 로그에도 뒤 단계에도 안 남았다.
    """
    return {"article_type": name, "type_reason": z.s(reason, 200)}


def build_input(d) -> dict:
    """소재 · 독자 · 질문 · 각도 · 독자 단계.

    소재를 제목 한 줄로 넘기면 **케이스형이 쓸 만한지 판단할 수 없다.**
    실제 사례가 있는지는 요약과 딸려온 기사를 봐야 안다.

    채널은 통째로 넘기지 않는다. 홈페이지냐 네이버냐가 유형을 정하면 안
    되고, 독자 단계(`reader_stage`)만 보조 신호로 쓴다.
    """
    tp = pay(d, "topic")
    return {
        # 케이스형이 쓸 만한지 보려면 실제 사례가 있는지 알아야 한다.
        "topic": {**topic_brief(d, keywords=False),
                  "sources": [{"headline": x.get("headline", ""),
                               "press": x.get("press", "")}
                              for x in (tp.get("sources") or [])[:5]
                              if isinstance(x, dict)]},
        "reader": pay(d, "reader"),
        "intent": pay(d, "intent"),
        "angle": pay(d, "angle"),
        "reader_stage": pay(d, "channel").get("reader_stage", ""),
    }


def make(d, inp) -> list[dict]:
    """목록 여섯 개는 그대로 두고, 추천과 부적합 표시만 얹는다."""
    rec, why, unfit = "", "", {}
    if llm.ENABLED:
        out = llm.generate("type", inp)
        # 목록에 없는 이름은 버린다. 안 그러면 추천이 조용히 사라진다.
        rec = z.enum(out.get("recommended"), NAMES) or ""
        why = z.s(out.get("rationale"), 200)
        unfit = _unfit(out.get("unfit"), rec)

    items = []
    for name, when, hint in ARTICLE_TYPES:
        if name == rec:
            reason = why or "이 글의 질문과 목적에 가장 맞는 유형"
            meta = "추천 · " + reason
        elif name in unfit:
            reason = f"이 글에는 안 맞음 — {unfit[name]}" if unfit[name] else ""
            meta = "이 글엔 안 맞음 · " + (unfit[name] or "근거 없음")
        else:
            # 고르지 않은 유형의 이유를 지어내지 않는다.
            reason = ""
            meta = hint
        items.append(opt(name, name, when, meta, payload(name, reason)))
    return items


def _unfit(rows, rec) -> dict:
    """부적합 표시. 목록 밖 이름과 추천과 겹치는 것은 버린다.

    전부 부적합이면 통째로 지운다 — 고를 수 있는 유형이 하나도 없으면
    사람이 화면에서 할 수 있는 게 없다.
    """
    out = {}
    for u in (rows if isinstance(rows, list) else []):
        if not isinstance(u, dict):
            continue
        name = z.enum(u.get("article_type"), NAMES)
        if name and name != rec:
            out[name] = z.s(u.get("reason"), 200)
    return {} if len(out) >= len(NAMES) else out


def written(t):
    """custom=False 라 확정 경로에서는 도달하지 않는다.
    스키마를 맞춰 두는 것은 나중에 열게 될 때를 위해서다."""
    return t, "직접 쓴 유형", payload(t)


STEP = Step(
    key="type", name="유형", eyebrow="TYPE", h1="유형 선택",
    custom=False,
    build_input=build_input, make=make, written=written,
    prompt="prompt.md",
)
