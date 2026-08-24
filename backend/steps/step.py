"""단계 하나가 무엇을 갖춰야 하는가.

각 단계 폴더가 이 모양의 `STEP` 하나를 내보낸다. dataclass 로 둔 이유는
규약이 코드로 강제되기 때문이다 — 모듈 속성 규약(getattr)으로 두면 이름에
오타가 나도 조용히 None 이 되고, 그 단계만 화면에서 비어 보인다.

    key       드래프트와 URL 에 쓰이는 이름
    name      화면에 뜨는 짧은 이름
    eyebrow   화면 윗줄
    h1        화면 제목
    multi     여러 개 고를 수 있나
    custom    직접 쓰기를 받나
    upload    파일을 받나 — 화면이 이 플래그를 보고 업로드 상자를 그린다
    strong    상위 모델을 쓰나
    hint      직접 쓰기 칸 안내

    build_input(draft)          드래프트 → 프롬프트 입력. 이 값이 바뀌면 후보를 다시 뽑는다
    make(draft, inp)            → 선택지 목록 [{id, title, summary, meta, payload}]
    written(text)               직접 쓴 텍스트 → (label, detail, payload)
    fill(text, got, v)          직접 쓴 한 줄에서 부속 항목 채우기 (reader·angle 만)
    label(picked)              여러 개 골랐을 때의 확정 라벨 (evidence 만)

순서 번호(no)는 여기 없다. steps/__init__.py 의 리스트 순서가 정한다.
폴더 이름에 번호를 붙이면(01_reader/) 순서를 바꿀 때 import 경로가 다 깨진다.

**단계 폴더는 다른 단계 폴더를 import 하지 않는다.** 앞 단계 값은 항상
드래프트 dict 에서 키로 읽는다. 이걸 어기면 순서를 바꿀 때 import 가 꼬이고,
"이 폴더만 보면 된다" 가 성립하지 않는다.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Step:
    key: str
    name: str
    eyebrow: str
    h1: str

    multi: bool = False
    custom: bool = True
    upload: bool = False    # 파일을 받나
    strong: bool = False
    hint: str = ""

    build_input: Callable | None = None
    make: Callable | None = None
    written: Callable | None = None
    fill: Callable | None = None
    label: Callable | None = None

    # 프롬프트 파일. 폴더 안 파일 이름이고, 등록은 레지스트리가 한다.
    prompt: str = ""            # 후보 생성용 (없으면 LLM 을 안 쓰는 단계)
    prompt_written: str = ""    # 직접 쓴 값 채우기용

    # 직접 쓴 값을 만들 때 앞 단계 값이 필요한 단계. 참이면 written() 이
    # build_input(draft) 결과를 두 번째 인자로 받는다.
    #
    # fill 과 다르다. fill 은 프롬프트를 한 번 더 부르는 것이고, 이건
    # **코드가 계산할 수 있는 것**을 계산하는 자리다 — 제목에 어떤 키워드가
    # 들어갔는지 세는 데 모델이 필요 없다.
    written_needs_input: bool = False

    # 채널마다 다른 것을 요구하는 단계. 참이면 prompt 를 밑바탕으로 깔고
    # {채널}.md 를 얹어 `{채널}_{key}` 이름으로 등록한다.
    #
    # **폴더를 가르지 않는다.** 화면도 후보 고르는 법도 payload 도 같고
    # 다른 것은 "LLM 에게 무엇을 요구하는가" 뿐이다. 그건 프롬프트 차이지
    # 단계 차이가 아니다. 폴더를 가르는 것은 화면이나 순서가 달라질 때다.
    by_channel: bool = False

    @property
    def uses_llm(self) -> bool:
        return bool(self.prompt)

    def prompt_of(self, channel: str) -> str:
        """이 단계가 부를 프롬프트 이름."""
        if not self.by_channel:
            return self.key
        from ..data import channels
        ch = channel if channel in channels.NAMES else "site"
        return f"{ch}_{self.key}"


# ── 드래프트에서 값 꺼내기 ────────────────────────────────────
#
# 단계마다 앞 단계 확정값을 읽는다. 여섯 곳에 같은 두 줄을 복사하지 않도록
# 여기 둔다. dict 접근이라 단계끼리 import 하는 것과는 다르다.

def label_of(d, key) -> str:
    return d.get(key, {}).get("label", "")


def pay(d, key) -> dict:
    return d.get(key, {}).get("payload", {}) or {}


def pick_meta(reason: str, meta: str = "") -> str:
    """추천 카드의 메타 문구.

    **왜 추천인지가 없으면 추천이 아니다.** 그냥 첫 번째라는 뜻이 되고,
    사람은 그걸 보고 판단할 수 없다. 이유는 각 단계가 이미 들고 있다 —
    각도는 differentiation, 검색의도·구조는 rationale, 유형은 type_reason.
    """
    head = "추천 · " + (reason or "이 글에 가장 맞는 선택")
    return f"{head} · {meta}" if meta else head


# 추천 표시. 메타 앞에 붙는다.
PICK = "추천"


def pick_meta(meta: str, why: str = "") -> str:
    """첫 후보에 붙는 추천 표시.

    **왜 추천인지를 함께 적는다.** "추천" 만 붙이면 사람이 그것만 고르고
    나머지를 안 본다. 이유가 보여야 다른 후보와 견줄 수 있다.

    이유는 후보가 이미 들고 있는 값을 쓴다 — 각도는 differentiation,
    검색의도·구조는 rationale, 유형은 type_reason. 새로 지어내지 않는다.
    """
    head = f"{PICK} · {why}" if why else PICK
    return f"{head} · {meta}" if meta else head


def opt(oid, title, summary, meta, payload, selectable=True) -> dict:
    """선택지 하나. 화면이 그대로 그린다.

    `selectable` 이 거짓이면 고를 수 없다. **값으로 내려보낸다** — 화면이
    상태를 보고 다시 판단하면 정책이 두 곳에 생기고, 실제로 어긋났다.
    미확인 추론은 고를 수 있는데 화면이 전부 막아 버렸다.

    확정 경로도 같은 값을 본다. 화면을 우회해도 못 고른다.
    """
    out = {"id": oid, "title": title, "summary": summary,
           "meta": meta, "payload": payload}
    if not selectable:
        out["selectable"] = False
    return out
