"""채널별 정책 — **코드가 읽는 값만** 둔다.

`skeletons.py` 와 같은 자리다. 프롬프트에 박으면 두 채널 규칙이 매 호출에
다 실리거나 공통 규칙이 두 벌로 복제된다.

## 모델용 지침은 여기 없다

처음에는 `guidance` · `capabilities` · `avoid` 를 여기 뒀다. 그런데 그것을
읽는 곳이 본문 작성 하나뿐이었고, 구조·제목 단계는 채널을 아예 모른 채
돌고 있었다 — **데이터는 있고 아무도 안 읽는 상태**였다.

    channels.py        코드가 강제하거나 조립에 쓰는 값
    {단계}/{채널}.md    모델이 따라야 하는 채널별 작성 지침

숫자가 양쪽에 나오는 것은 중복이 아니라 역할이 다르다. 프롬프트는 "보통
4~7개, 필요하면 더 적게" 라고 권하고, 코드는 `max_sections=7` 을 자른다.
**하한은 코드에 없다** — 강제하면 모델이 그 수를 채우려고 없는 것을 만든다.

## 값을 dict 셋으로 나눠 두지 않는다

한때 `hard_rules` · `render` · 전역 `MEDIA_LABELS` 로 흩어져 있었다. 그러다
라벨이 두 곳에 생겨 **같은 것을 "캡처" 와 "자료 화면" 으로 다르게 부르는**
일이 실제로 났다. 한 객체로 묶어 두면 그럴 자리가 없다.

**여기는 brand 말고 아무것도 import 하지 않는다.**
"""

from dataclasses import dataclass, field

NAMES = ("site", "naver")


@dataclass(frozen=True)
class ChannelPolicy:
    """채널 하나가 코드에 요구하는 것 전부.

    frozen 인 이유는 이게 설정이기 때문이다. 돌다가 누가 고치면 그 세션만
    다르게 동작하고 재현이 안 된다.
    """

    name: str

    # 코드가 자른다. 상한이지 목표가 아니다.
    max_sections: int
    max_figures: int
    max_callouts: int
    max_tags: int

    # 코드가 비운다. 채널에 안 맞는 필드는 프롬프트가 채워 와도 지운다.
    meta_required: bool          # description · slug
    tags_allowed: bool           # main_keyword · secondary_keywords · tags
    media_allowed: bool          # 사람이 준비할 사진 · 자료 화면

    # 조립이 읽는다.
    figure_render: str           # html | capture
    hero_ratio: str              # wide | 1:1
    trust_block: bool            # 작성자 · 검토자 · 기준일
    cta_strength: str

    # 캡처할 때의 폭·글자 크기·여백. 재서 정한 값이 아니다.
    capture: dict

    # 화면과 결과물이 같은 이름으로 부르게 한다.
    labels: dict = field(default_factory=dict)


SITE = ChannelPolicy(
    name="회사 홈페이지",
    max_sections=7, max_figures=4, max_callouts=3, max_tags=0,
    meta_required=True, tags_allowed=False, media_allowed=False,
    figure_render="html", hero_ratio="wide",
    trust_block=True, cta_strength="medium",
    capture={"width": 820, "font_size": 16, "padding": 0},
    labels={"hero": "대표 이미지", "figure": "본문 도식"},
)

NAVER = ChannelPolicy(
    name="네이버 블로그",
    max_sections=5, max_figures=4, max_callouts=2, max_tags=10,
    meta_required=False, tags_allowed=True, media_allowed=True,
    figure_render="capture", hero_ratio="1:1",
    trust_block=False, cta_strength="soft",
    capture={"width": 680, "font_size": 18, "padding": 24},
    labels={"hero": "대표 이미지", "figure": "본문 도식",
            "photo": "실제 사진", "capture": "자료 화면"},
)

POLICIES = {"site": SITE, "naver": NAVER}


def of(channel: str) -> ChannelPolicy:
    """채널 정책 한 벌. 모르는 채널이면 홈페이지로 떨어진다.

    떨어뜨리는 이유는 결과물 조립 중에 터지면 사람이 할 수 있는 게 없기
    때문이다. 목록 밖 값 자체는 채널 확정 단계가 막는다(고를 것이 둘뿐이고
    직접 쓰기를 안 받는다).
    """
    return POLICIES.get(channel) or SITE


def channel_of(d) -> str:
    """드래프트에서 확정된 채널. 못 찾으면 홈페이지.

    **여기 한 곳만 판단한다.** 예전에는 이 일을 네 곳이 각자 했다 —
    steps 의 순서 계산, 본문의 프롬프트 고르기, 대표 이미지, 결과물 조립.
    넷이 우연히 같은 답을 내고 있었을 뿐이라, 한 곳만 고치면 조용히
    어긋난다.
    """
    if not d:
        return "site"
    raw = (d.get("channel") or {}).get("payload", {}).get("channel")
    if raw in NAMES:
        return raw
    if raw:
        print(f"[channel] 모르는 채널이라 홈페이지로 둔다: {raw!r}")
    return "site"


def policy_of(d) -> ChannelPolicy:
    """드래프트 → 정책. 두 단계를 한 번에 하고 싶을 때."""
    return of(channel_of(d))


def capture(channel: str) -> dict:
    """캡처할 때의 폭·글자 크기·덧씌울 CSS.

    네이버 도식은 세로 한 줄로 세우고 글자를 키운다. **렌더러를 새로 만들지
    않는다** — 마크업은 한 벌이고 찍을 때 스타일만 갈아 끼운다. 둘로 만들면
    도식 내용이 채널마다 어긋날 수 있다.
    """
    from . import brand
    pol = of(channel)
    out = dict(pol.capture)
    if pol.figure_render == "capture":
        out["css"] = brand.NAVER_FIGURE_CSS
        # 도식은 본문보다 넓게 찍는다. 같은 폭으로 찍으면 표가 짓눌린다.
        out["figure_widths"] = dict(brand.FIGURE_WIDTHS)
    return out


def label(channel: str, kind: str) -> str:
    """시각 요소의 이름. 화면과 결과물이 같은 말을 쓰게 한다."""
    return of(channel).labels.get(kind, "자료")


def limits(channel: str) -> dict:
    """모델에게 미리 알리는 상한.

    어차피 코드가 자르지만 미리 알면 자를 일이 줄고, 잘린 결과보다 처음부터
    맞춘 결과가 낫다. 조립 방식(`figure_render`)은 모델이 알 필요가 없다.
    """
    p = of(channel)
    return {"max_sections": p.max_sections, "max_figures": p.max_figures,
            "max_callouts": p.max_callouts}
