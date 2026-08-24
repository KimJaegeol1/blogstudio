"""본문 그림. 섹션 하나에 들어갈 상황 그림을 만든다.

    ① llm.generate  섹션 계획 → 영어 지시문
    ② gemini.draw   지시문 → 이미지
    ③ gemini.save   파일로

`hero.py` 와 흐름은 같지만 **한 장이 아니라 여러 장**이다. 그래서 다른
것이 셋 있다.

## 일부만 실패해도 나머지는 쓴다

두 장 중 하나만 만들어졌으면 그 하나는 쓰고 나머지는 자리표시로 남는다.
대표 이미지는 없으면 글이 허전할 뿐이지만, 본문 그림은 **원래 없어도 되는
것**이라 하나 실패했다고 통째로 막을 이유가 없다.

## 섹션 번호로 잇는다

본문에 `[본문 그림 삽입]` 이 어느 섹션에 있는지는 구조가 정했다. 만든
파일도 그 번호를 들고 있어야 사람이 어느 자리에 넣을지 안다.

## 이미 만든 것은 다시 안 만든다

한 번에 다 만들지 못하고 나눠 부를 수 있고, 그때마다 새로 그리면 앞에
만든 그림이 바뀐다. 사람이 저장해 둔 것과 화면의 것이 달라진다.
"""

import pathlib
import time

from .. import llm, prompt as prompts
from ..data import brand, channels
from ..data.channels import channel_of
from ..external import gemini
from ..record import response as rec
from . import common as C

_DIR = pathlib.Path(__file__).parent
for _ch in channels.NAMES:
    _f = _DIR / _ch / "illust.md"
    if _f.exists():
        prompts.register(f"{_ch}_illust", _f, base=_DIR / "_illust.md")

# 한 편에 몇 장까지. 구조가 더 계획해도 여기서 자른다 — 그림이 많아지면
# 글이 아니라 화보가 되고, 호출 수도 그만큼 는다.
MAX = 2


def plans(d) -> dict:
    """섹션 번호 → 그림 계획. 구조가 정한 것."""
    return C.illustrations_of(d)


def made(d) -> dict:
    """이미 만든 것. 섹션 번호 → {file, alt, prompt}"""
    return d.get("illust") or {}


def pending(d) -> dict:
    """계획은 있는데 아직 안 만든 것."""
    done = made(d)
    return {n: v for n, v in plans(d).items() if str(n) not in done}


def build_input(d, order: int, plan: dict) -> dict:
    sec = _section(d, order)
    return {
        "title": (d.get("title", {}).get("payload") or {}).get("title", ""),
        "topic": d.get("topic", {}).get("label", ""),
        "heading": sec.get("title", ""),
        "objective": sec.get("objective", ""),
        "role": sec.get("role", ""),
        "purpose": plan.get("purpose", ""),
        # 글마다 달라도 그림의 결은 일정해야 한 브랜드로 읽힌다.
        "style": brand.image_hint(),
    }


def _section(d, order: int) -> dict:
    secs = (d.get("outline", {}).get("payload") or {}).get("sections") or []
    return secs[order - 1] if 0 < order <= len(secs) else {}


def one(d, order: int, plan: dict, sid: str = "") -> dict:
    """한 장. 실패는 올린다 — 부르는 쪽이 어느 섹션이 실패했는지 안다."""
    inp = build_input(d, order, plan)
    name_ = f"{channel_of(d)}_illust"

    t0 = time.perf_counter()
    got = llm.generate(name_, inp)
    text = (got.get("prompt") or "").strip()
    if not text:
        raise llm.LLMError(f"{name_}: 지시문이 비었다")
    alt = (got.get("alt") or "").strip()[:200]

    data = gemini.draw(text)
    file = gemini.save(data, f"{sid or 'illust'}-s{order}.png")

    out = {"file": file, "prompt": text, "alt": alt,
           "bytes": len(data), "model": gemini.MODEL}
    rec.written(sid, inp, out, model=gemini.MODEL,
                ms=round((time.perf_counter() - t0) * 1000), step="illust",
                raw=llm.raw(name_))
    return out


def make(d, sid: str = "") -> dict:
    """계획된 것을 만든다. {"made": {...}, "failed": {...}}

    **하나가 실패해도 멈추지 않는다.** 본문 그림은 원래 없어도 되는
    것이라, 하나 때문에 나머지를 못 만들 이유가 없다.
    """
    todo = list(pending(d).items())[:MAX]
    if not todo:
        return {"made": made(d), "failed": {}}

    out = dict(made(d))
    bad = {}
    for order, plan in todo:
        try:
            out[str(order)] = one(d, order, plan, sid)
        except (llm.LLMError, gemini.ImagenError) as e:
            bad[str(order)] = str(e)[:200]
            rec.failed(sid, "illust", {"order": order, "purpose": plan.get("purpose")},
                       str(e), ms=0)
    d["illust"] = out
    return {"made": out, "failed": bad}
