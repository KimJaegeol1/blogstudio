"""2단계 — 채널.

어디에 실을 글인지 정한다. **이 단계가 뒤 흐름을 가른다** — 채널이 정해져야
그 채널의 제목·구조 단계가 순서에 붙는다(`steps.order()`).

프롬프트가 없다. 고를 것이 둘뿐이고 설명은 채널마다 고정이라, 모델에게
물으면 매번 같은 답을 다르게 적어 올 뿐이다. 후보를 코드가 만든다.

직접 쓰기를 받지 않는다(custom=False). `site` · `naver` 밖의 값이 들어오면
그 채널의 단계를 찾지 못하고 순서가 조용히 공통 단계로만 끝난다.

`channel_goal` · `reader_stage` · `cta_strength` 는 채널에 딸린 상수다.
별도 단계로 물으면(콘텐츠 목표) 사람이 고를 것이 사실상 채널 하나인데
화면만 하나 더 늘어난다. 값이 채널마다 달라야 할 근거가 생기면 그때 뺀다.

`reader_stage` 를 다른 단계 payload 로 복사하지 않는다. 필요한 곳은
`pay(d, "channel")` 로 읽는다 — 같은 값이 두 군데 있으면 한쪽만 고쳐진다.
"""

from ..step import Step

# key 는 steps/site/ · steps/naver/ 폴더 이름과 같아야 한다.
# 어긋나면 order() 가 그 채널 단계를 못 찾고 공통 단계만 돌려준다.
CHANNELS = [
    {
        "channel": "site",
        "name": "회사 홈페이지",
        "summary": "대응·도입을 검토하는 실무자에게 전문성과 서비스 구조를 보인다",
        "channel_goal": "전문성 증명 · 서비스 전환",
        "reader_stage": "대응 준비",
        "cta_strength": "medium",
        "meta": "구조화된 전문 콘텐츠 · HTML 도식과 표 · 출처와 작성 주체 표시",
    },
    {
        "channel": "naver",
        "name": "네이버 블로그",
        "summary": "개념을 처음 검색한 독자에게 쉽게 설명하고 홈페이지로 잇는다",
        "channel_goal": "검색 유입 · 브랜드 친밀도",
        "reader_stage": "정보 탐색",
        "cta_strength": "soft",
        "meta": "모바일 가독성 · 이미지 도식 · 짧은 문단과 질문형 소제목",
    },
]

NAMES = tuple(c["channel"] for c in CHANNELS)

KEYS = ("channel", "channel_goal", "reader_stage", "cta_strength")


def payload(c) -> dict:
    return {k: c[k] for k in KEYS}


def build_input(d) -> dict:
    """프롬프트가 없어도 필요하다. 후보 캐시가 이 값으로 무효화를 판단한다."""
    return {}


def make(d, inp) -> list[dict]:
    from ..step import opt
    return [opt(c["channel"], c["name"], c["summary"], c["meta"], payload(c))
            for c in CHANNELS]


def written(t):
    """custom=False 라 확정 경로에서는 도달하지 않는다.
    스키마를 맞춰 두는 것은 나중에 열게 될 때를 위해서다."""
    return t, "직접 쓴 채널", {"channel": t, "channel_goal": "",
                            "reader_stage": "", "cta_strength": "soft"}


STEP = Step(
    key="channel", name="채널", eyebrow="CHANNEL", h1="채널 선택",
    custom=False,
    build_input=build_input, make=make, written=written,
)
