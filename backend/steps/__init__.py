"""단계 레지스트리.

**순서는 여기 order() 한 곳에서만 정한다.** 폴더 이름에 번호를 붙이면
(01_reader/) 순서를 바꿀 때 import 경로가 다 깨지므로 코드가 정한다.
번호(no)도 여기서 매긴다 — 폴더가 자기 번호를 들면 하나를 끼울 때
나머지를 다 고쳐야 한다.

**순서는 리스트가 아니라 함수다.** 채널(홈페이지·네이버)이 정해지면 그
채널의 단계가 뒤에 붙기 때문이다. 정적 리스트로 두면 두 채널 단계가 항상
다 보이고, 사람이 자기 채널이 아닌 단계로 들어갈 수 있다. 인자로 드래프트를
받는 이유가 그것이다.

    order(draft)   이 드래프트가 지나갈 단계 목록
    keys(draft)    그 key 만
    meta(draft)    화면에 내보내는 모양 (no 번호 포함)

BY_KEY · TIERS · WRITE_HINT 는 순서와 무관한 속성이라 전역이다.

단계마다 다른 것은 각 폴더가 들고, **모든 단계에 똑같이 벌어지는 일**은
여기 있다.

    options()   후보 캐시 · 자취 남기기 · 실패 기록
    written()   직접 쓰기 디스패치 · 부속 항목 채우기

**단계 폴더는 여기 바로 아래 있다.** 한때 common/ 층을 두고 그 옆에
site/ · naver/ 를 만들 자리로 비워 뒀는데, 채널은 폴더가 아니라 프롬프트로
가르기로 정해서(Step.by_channel) 그 자리를 안 쓰게 됐다. 형제가 없는
common/ 은 "옆에 common 아닌 게 있다" 는 거짓말이라 걷어냈다.

채널이 갈리는 지점은 두 곳에 드러나 있다 — 단계 안에서는 site.md · naver.md
파일 이름으로, 승인 뒤에는 output/site/ · output/naver/ 폴더로.

1단계(소재)와 마지막(승인)은 폴더가 없다. 소재는 화면 흐름 자체가 다르고
(별도 엔드포인트, state, 평가 반영) 승인은 고를 게 없다. 메타만 등록한다.
소재는 시트 연결할 때 폴더로 뺀다.
"""

import json
import time

from .. import llm, prompt as prompts
from ..record import response as rec
from . import (angle, channel, evidence, intent, outline, reader,
               title, type as type_)
from .step import Step

# ── 순서 ──────────────────────────────────────────────────────
#
# 폴더가 있는 단계는 그 폴더의 STEP 을, 없는 단계는 메타만 여기 적는다.

TOPIC = Step(key="topic", name="소재", eyebrow="SOURCE", h1="소재 선택")
APPROVE = Step(key="approve", name="승인", eyebrow="APPROVE", h1="최종 확인")

# 채널을 고르기 전. 여기까지는 어느 채널이든 같다.
HEAD: list[Step] = [TOPIC, channel.STEP]

# 채널을 고른 뒤. **지금 둘이 같아도 목록을 따로 선언한다.**
#
# 같은 리스트를 두 키가 가리키면 한쪽에 단계를 끼울 때 다른 쪽까지 바뀐다.
# 나중에 네이버에만 사진 준비 단계를, 홈페이지에만 서비스 연결 단계를 넣게
# 되면 여기만 고치면 된다.
_AFTER = (reader.STEP, intent.STEP, angle.STEP, type_.STEP,
          evidence.STEP, outline.STEP, title.STEP)

SITE_ORDER: list[Step] = [*_AFTER]
NAVER_ORDER: list[Step] = [*_AFTER]

BY_CHANNEL: dict[str, list[Step]] = {
    "site": SITE_ORDER,
    "naver": NAVER_ORDER,
}

# 채널을 아직 안 골랐을 때 보여 줄 것. 홈페이지 것으로 미리 보인다 —
# 단계 수와 이름을 알아야 사람이 얼마나 남았는지 안다.
PREVIEW: list[Step] = SITE_ORDER

# 늘 마지막.
TAIL: list[Step] = [APPROVE]


def order(draft=None) -> list[Step]:
    """이 드래프트가 지나갈 단계 목록.

    채널을 고르면 그 채널 목록이 붙는다. 아직 안 골랐으면 미리보기를 쓴다 —
    빈 목록을 주면 소재 화면에서 남은 단계가 둘로 보인다.
    """
    ch = channel_of(draft)
    return [*HEAD, *BY_CHANNEL.get(ch, PREVIEW), *TAIL]


def channel_of(draft=None) -> str:
    """확정된 채널. **아직 안 정했으면 빈 문자열.**

    data/channels.channel_of() 와 다르다. 저쪽은 조립할 때 쓰는 것이라 모르면
    홈페이지로 떨어뜨리는데, 여기는 순서를 정하는 자리라 **"아직 안 정함" 과
    "홈페이지" 를 구별해야 한다.** 떨어뜨리면 채널을 고르기도 전에 홈페이지
    단계가 순서에 붙는다.
    """
    if not draft:
        return ""
    raw = (draft.get("channel") or {}).get("payload", {}).get("channel", "")
    return raw if raw in _CHANNELS else ""


def keys(draft=None) -> list[str]:
    return [s.key for s in order(draft)]


# ── 전역 레지스트리 ───────────────────────────────────────────
#
# 순서와 무관한 것들이다. key 로 단계를 찾는 일은 어느 드래프트냐와
# 상관없이 같은 답이어야 한다.

# 등록부. 두 채널 목록이 같은 Step 객체를 가리키므로 겹치는 것은 한 번만.
ALL: list[Step] = [*HEAD, *TAIL]
for _group in BY_CHANNEL.values():
    ALL += [s for s in _group if s not in ALL]

BY_KEY: dict[str, Step] = {}
for _s in ALL:
    if _s.key in BY_KEY:
        raise ValueError(f"단계 key 가 겹친다: {_s.key}")
    BY_KEY[_s.key] = _s


# ── 프롬프트 등록 ─────────────────────────────────────────────
#
# 이름 → 파일 경로를 명시적으로 붙인다. 이름에서 경로를 규칙으로 유추하면
# 오타가 났을 때 엉뚱한 파일을 집거나 조용히 다음 규칙으로 흘러간다.
#
# 폴더 경로도 규칙으로 세지 않는다. key 로 경로를 조립하면(steps/{key}/)
# 층이 하나 생기는 순간 조용히 못 찾는다 — 실제로 common/ 을 만들면서
# 그렇게 깨졌다. import 해 온 모듈이 자기 자리를 알고 있으므로 그걸 쓴다.

import pathlib  # noqa: E402

MODULES = [channel, reader, intent, angle, type_, evidence, outline, title]

DIR_OF: dict[str, pathlib.Path] = {
    m.STEP.key: pathlib.Path(m.__path__[0]) for m in MODULES}

from ..data.channels import NAMES as _CHANNELS  # noqa: E402

for _s in ALL:
    if not _s.prompt:
        continue
    _dir = DIR_OF[_s.key]
    if _s.by_channel:
        # 채널마다 요구가 다른 단계. 공통을 밑에 깔고 채널 파일을 얹는다.
        # 통째로 복제하면 한쪽만 고쳐지고 그 어긋남은 조용히 지나간다.
        for _ch in _CHANNELS:
            prompts.register(f"{_ch}_{_s.key}", _dir / f"{_ch}.md",
                             base=_dir / _s.prompt)
    else:
        prompts.register(_s.key, _dir / _s.prompt)
    if _s.prompt_written:
        prompts.register(f"{_s.key}_written", _dir / _s.prompt_written)


# ── 화면에 내보내는 모양 ──────────────────────────────────────
#
# 번호(no)는 그 드래프트의 순서에서 매긴다. 채널이 갈리면 뒤쪽 번호가
# 채널마다 달라지므로 전역 상수로 둘 수 없다.

def meta(draft=None) -> list[dict]:
    return [{"key": s.key, "no": i, "eyebrow": s.eyebrow, "name": s.name,
             "h1": s.h1,
             **({"multi": True} if s.multi else {}),
             **({} if s.custom else {"custom": False}),
             **({"upload": True} if s.upload else {})}
            for i, s in enumerate(order(draft), 1)]


def meta_of(key: str, draft=None) -> dict:
    """단계 하나의 화면 모양. 그 드래프트의 순서에 없으면 KeyError."""
    return {m["key"]: m for m in meta(draft)}[key]


WRITE_HINT = {s.key: s.hint for s in ALL if s.hint}

# 어느 단계가 상위 등급을 쓰나. /api/health 가 실어 보낸다.
TIERS = {s.key: ("strong" if s.strong else "base")
         for s in ALL if s.uses_llm}


def next_of(key: str, draft=None) -> str:
    ks = keys(draft)
    return ks[ks.index(key) + 1]


def uses_llm(key: str) -> bool:
    s = BY_KEY.get(key)
    return bool(s and s.uses_llm)


# ── 선택지 ────────────────────────────────────────────────────

def options(key, draft, refresh=False) -> list[dict]:
    """단계 하나의 선택지.

    한 번 뽑은 후보는 드래프트에 붙여 둔다. 두 가지 이유다.

    ① 화면을 새로 열 때마다 다시 뽑으면 호출이 그대로 늘어난다.
    ② 확정할 때 고른 id 를 다시 찾는데, 그 사이 새로 뽑으면 같은 id 가
       다른 내용을 가리킨다. 오류 없이 엉뚱한 값이 확정된다.

    앞 단계 값이 바뀌면 입력이 달라지므로 알아서 다시 뽑는다.
    같은 입력으로 다른 후보를 보고 싶으면 refresh 를 준다.
    """
    step = BY_KEY.get(key)
    if not step or not step.make:
        return []

    inp = step.build_input(draft)
    sig = json.dumps(inp, ensure_ascii=False, sort_keys=True, default=str)

    # 채널마다 다른 것을 요구하는 단계는 프롬프트 이름이 다르다. 원문을
    # key 로 찾으면 그 단계 행에 원문이 안 붙는다.
    pname = step.prompt_of(channel_of(draft))

    cache = draft.setdefault("_opts", {})
    hit = cache.get(key)
    if not refresh and hit and hit["sig"] == sig:
        return hit["items"]

    t0 = time.perf_counter()
    try:
        items = step.make(draft, inp)
    except llm.LLMError as e:
        # 실패도 남긴다. 안 남기면 로그에 그 단계가 통째로 비어 보인다.
        rec.failed(draft.get("_sid", ""), key, inp, str(e),
                   round((time.perf_counter() - t0) * 1000),
                   raw=llm.raw(pname))
        raise
    cache[key] = {"sig": sig, "items": items}

    # 무엇을 넣었더니 무엇이 나왔나. 캐시가 맞으면 여기까지 안 오므로
    # 실제로 만든 순간에만 한 줄 남는다.
    rec.generated(
        draft.get("_sid", ""), key, inp, items,
        model=llm.model_for(step.strong) if llm.ENABLED else "",
        source="llm" if llm.ENABLED else "offline",
        refresh=bool(refresh),
        ms=round((time.perf_counter() - t0) * 1000),
        raw=llm.raw(pname))
    return items


# ── 직접 쓴 값 ────────────────────────────────────────────────
#
# 선택지와 같은 payload 빌더를 쓴다. 스키마가 한 곳에만 있으므로
# 나중에 필드를 바꿔도 "직접 쓴 값만 조용히 깨지는" 일이 없다.
#
# 다만 빌더는 모양만 보장하고 의미는 보장하지 않는다. 한 줄만 받으면
# 부속 항목이 "미지정" 이나 빈 배열로 남고, 그걸 읽는 하위 프롬프트 규칙이
# 그만큼 죽는다. 그래서 fill 이 있는 단계는 쓴 한 줄을 프롬프트로 되먹여
# 나머지 항목을 채운다. 사람이 쓴 말 자체는 코드가 그대로 넣는다.

def written(key, text, draft=None) -> dict:
    """직접 쓴 내용을 선택지와 같은 확정값 형태로 만든다."""
    from .. import sanitize as z
    t = z.s(text)
    step = BY_KEY.get(key)
    if not step or not step.written:
        return {"label": t, "detail": "", "payload": {"text": t}}

    if step.written_needs_input and draft is not None:
        label, detail, payload = step.written(t, step.build_input(draft))
    else:
        label, detail, payload = step.written(t)
    v = {"label": label, "detail": detail, "payload": payload}

    if llm.ENABLED and draft is not None and step.fill:
        v = _fill(step, t, draft, v)
    return v


def _fill(step: Step, text, draft, v) -> dict:
    """직접 쓴 한 줄에서 부속 항목을 채운다.

    이것도 프롬프트 호출이므로 자취를 남긴다. 안 남기면 "직접 썼더니 무엇이
    채워졌나" 가 어디에도 없어서, 채움 프롬프트를 고칠 근거가 사라진다.
    """
    sid = draft.get("_sid", "")
    name = f"{step.key}_written"
    inp = dict(step.build_input(draft))
    inp["written"] = text

    t0 = time.perf_counter()
    try:
        got = llm.generate(name, inp, strong=step.strong)
    except llm.LLMError as e:
        rec.failed(sid, name, inp, str(e),
                   ms=round((time.perf_counter() - t0) * 1000),
                   raw=llm.raw(name))
        # 사람이 이미 핵심은 정했다. 부속 항목을 못 채웠다고 막지는 않는다.
        # 대신 조용히 넘어가지 않고 확정값에 남긴다.
        v["detail"] = (v["detail"] + " · 부속 항목 채우기 실패").strip(" ·")
        v["fill_failed"] = str(e)
        return v

    out = step.fill(text, got, v)
    rec.generated(
        sid, name, inp,
        [{"id": "fill", "title": out.get("label", ""),
          "summary": out.get("detail", ""), "meta": "",
          "payload": out.get("payload", {})}],
        model=llm.model_for(step.strong) if llm.ENABLED else "",
        source="llm" if llm.ENABLED else "offline",
        refresh=False, ms=round((time.perf_counter() - t0) * 1000),
        raw=llm.raw(name))
    return out


def many_label(key, picked) -> str:
    """여러 개 골랐을 때의 확정 라벨. 단계가 정하지 않으면 개수로."""
    step = BY_KEY.get(key)
    if step and step.label:
        return step.label(picked)
    return f"{len(picked)}건"
