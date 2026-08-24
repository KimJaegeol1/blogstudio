"""대표 이미지 만들기.

두 번 부른다. purpose 는 한국어로 적힌 의도라 그림 지시문이 아니다.

    ① hero.md      purpose(한국어 의도) → 영어 지시문 + 대체 텍스트
    ② gemini.draw  영어 지시문 → 이미지

한 번에 하지 않는 이유는, 생성 모델에 한국어 의도를 그대로 주면 해석이
약하고 "글자를 넣지 마라" 같은 제약을 걸 자리가 없기 때문이다.

본문 도식은 여기 오지 않는다. figures.py 가 마크업으로 그린다.
"""

import pathlib
import time

from .. import llm, prompt as prompts
from ..external import gemini
from ..data import brand, channels, skeletons
from ..data.channels import channel_of
from ..record import response as rec

# 채널마다 대표 이미지가 다른 물건이다. 홈페이지는 글자 없는 상징 그림,
# 네이버는 제목이 박힌 썸네일이다. 호출 흐름은 같으므로 프롬프트만 가른다.
_DIR = pathlib.Path(__file__).parent
for _ch in channels.NAMES:
    prompts.register(f"{_ch}_hero", _DIR / _ch / "hero.md",
                     base=_DIR / "_hero.md")





def _pay(d, key):
    return d.get(key, {}).get("payload", {}) or {}


def plan(d) -> dict:
    """대표 이미지 계획. 6단계가 정한 것."""
    return (_pay(d, "outline") or {}).get("hero_image") or {}


def build_input(d) -> dict:
    atype = _pay(d, "type").get("article_type", "")
    guide = (skeletons.TYPES.get(atype) or {}).get("image") or {}
    return {
        "title": _pay(d, "title").get("title", ""),
        "topic": d.get("topic", {}).get("label", ""),
        "article_type": atype,
        "purpose": plan(d).get("purpose", ""),
        "hero_guide": guide.get("hero", ""),
        "avoid": guide.get("avoid", ""),
        # 구조가 글마다 달라도 그림의 결은 일정해야 한 브랜드로 읽힌다.
        "style": brand.image_hint(),
        # 홈페이지는 가로, 네이버는 정사각. 채널 프롬프트에도 적혀 있지만
        # 값으로도 넘긴다 — 한 곳만 고쳤을 때 어긋나는 것을 줄인다.
        "ratio": channels.of(channel_of(d)).hero_ratio,
    }


def make(d, sid: str = "") -> dict:
    """지시문을 쓰고 그림을 만들어 저장한다.

    실패는 올린다. 대표 이미지가 없어도 글은 나가므로 부르는 쪽이 잡아서
    화면에 이유를 보이면 된다 — 조용히 자리표시로 되돌리면 왜 안 나왔는지
    알 방법이 없다.
    """
    if not plan(d).get("purpose"):
        raise gemini.ImagenError("6단계에서 대표 이미지를 계획하지 않았다")

    inp = build_input(d)

    t0 = time.perf_counter()
    name_ = f"{channel_of(d)}_hero"
    got = llm.generate(name_, inp)
    text = (got.get("prompt") or "").strip()
    if not text:
        raise llm.LLMError(f"{name_}: 지시문이 비었다")
    alt = (got.get("alt") or "").strip()[:200]

    data = gemini.draw(text)
    name = gemini.save(data, f"{sid or 'hero'}.png")

    out = {"file": name, "prompt": text, "alt": alt,
           "bytes": len(data), "model": gemini.MODEL}
    rec.written(sid, inp, out, model=gemini.MODEL,
                  ms=round((time.perf_counter() - t0) * 1000), step="hero",
                  raw=llm.raw(name_))
    return out
