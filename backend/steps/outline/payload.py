"""6단계 확정값 스키마.

`__init__.py` 와 `parse.py` 가 둘 다 쓴다. 카드로 고르든 직접 쓰든 같은
빌더를 지나야 필드를 바꿔도 한쪽만 조용히 깨지는 일이 없다.
"""

from ... import sanitize as z

# 카드에 붙는 짧은 표시. 결과물 쪽 이름은 채널 정책이 정한다
# (data/channels.py 의 labels) — 여기는 한 칸짜리 꼬리표라 따로 둔다.
_MEDIA = {"photo": "사진", "capture": "자료 화면"}


def _image(v):
    """본문 도식 계획. form 은 컴포넌트 이름이다(figures.NAMES).
    무엇을 어디에까지만 정한다 — 도식 안에 들어갈 내용은 본문 작성이 채운다."""
    if not isinstance(v, dict):
        return None
    purpose, form = z.s(str(v.get("purpose", ""))), z.s(str(v.get("form", "")))
    return {"purpose": purpose, "form": form} if purpose or form else None


MEDIA_TYPES = ("photo", "capture")

# 섹션이 이 글에서 하는 일. **`image.form` 과 다른 축이다** — form 은
# "무엇으로 그리나" 고 role 은 "이 섹션이 무슨 일을 하나" 다. 둘을 한
# 목록으로 두면 같은 것을 두 이름으로 부르게 된다.
#
# 이걸 두는 이유는 섹션 셋이 전부 `설명 → 목록 → 정리` 로 나왔기 때문이다.
# 논리는 이어지는데 읽는 리듬이 같아서 글이 평평해진다.
ROLES = ("context", "diagnosis", "structure", "comparison",
         "procedure", "criteria", "closing")

ROLE_LABELS = {
    "context": "상황",
    "diagnosis": "원인",
    "structure": "구조",
    "comparison": "비교",
    "procedure": "절차",
    "criteria": "기준",
    "closing": "정리",
}


# 이렇게 끝나면 그림이 무엇을 이해시키는지 안 적은 것이다. 사람이 읽고
# 무슨 파일을 찾아야 할지 모른다.
_META_TAIL = ("시각화한다", "시각화합니다", "보조한다", "보조합니다",
              "강조한다", "강조합니다", "구체화한다", "구체화합니다",
              "표현한다", "표현합니다", "설명한다", "설명합니다")


def _purpose_ok(t: str) -> bool:
    """그림이 무엇을 이해시키는지 적혔나.

    존재 이유("~를 시각화한다")로 끝나면 준비하는 사람에게 아무것도 안
    알려 준다. 프롬프트로 막았지만 코드도 본다 — 실제로 그렇게 나왔다.
    """
    return not t.rstrip(" .").endswith(_META_TAIL)


def _media(v, allow=True):
    """사람이 준비해야 할 사진·캡처 자리.

    **생성하지 않는다.** 회의 사진이나 공식 문서 화면을 모델이 그리면 그건
    사진이 아니라 가짜 현장이고, 신뢰 요소가 정반대로 작동한다 — 작성자
    이름을 안 지어내기로 한 것과 같은 이유다. 여기는 "어떤 자료가 필요한지"
    까지만 정하고, 실제로 채우는 일은 발행 전 확인 목록으로 넘어간다.

    `image`(도식)와 다른 것이다. 도식은 코드가 마크업으로 그려 결과물에
    바로 실리고, media 는 사람이 파일을 넣어야 한다.

    allow 가 거짓이면(홈페이지) 비운다. 필드는 늘 두되 채널에 안 맞으면
    코드가 비운다 — 제목의 meta_description·tags 와 같은 원칙이다. 모양이
    채널마다 다르면 그것을 읽는 쪽이 양쪽을 다 알아야 한다.
    """
    if not allow or not isinstance(v, dict):
        return None
    kind = z.s(str(v.get("type", "")))
    purpose = z.s(str(v.get("purpose", "")), 300)
    if kind not in MEDIA_TYPES or not purpose:
        return None
    # 메타 문장이면 버린다. 남겨 두면 사람이 그걸 보고 파일을 못 찾는다.
    if not _purpose_ok(purpose):
        return None
    return {"type": kind, "purpose": purpose}


def _illustration(v, allow=True):
    """줄글만 이어지는 구간을 쉬어 가게 하는 그림.

    **도식과 다른 물건이다.**

        image          정보를 구조로 보인다. 코드가 마크업으로 그린다
        illustration   상황을 그림으로 보인다. 생성 모델이 그린다
        media          실제 사진·자료 화면. 사람이 파일을 넣는다

    도식이 정보 구조화용이라, 목록으로 만들기 애매하고 줄글만 두면 무거운
    구간을 메울 수단이 없었다. 섹션 셋이 전부 목록으로 끝난 글이 그래서
    나왔다.

    **글자를 넣지 않는다.** 생성 모델이 한글을 못 쓰는 것이 도식을 마크업으로
    그리는 이유고, 여기도 같다. 상황만 보이고 설명은 본문이 한다.

    같은 섹션에 도식이 이미 있으면 안 받는다 — 부르는 쪽이 거른다.
    """
    if not allow or not isinstance(v, dict):
        return None
    purpose = z.s(str(v.get("purpose", "")), 300)
    if not purpose or not _purpose_ok(purpose):
        return None
    return {"purpose": purpose}


def _hero(v):
    """대표 이미지 계획. purpose 만 받는다.

    hero 는 글자 없는 상징 이미지라 생성으로 만들고, form(도식 형식)은 여기
    있을 값이 아니다. 프롬프트가 hero 에도 form 을 요구했더니 실제 실행에서
    세 후보가 전부 hero 를 "타임라인" 으로 채웠다 — 도식을 대표 이미지 자리에
    앉힌 것이다. 필드를 없애서 그 자리를 막는다.
    """
    if not isinstance(v, dict):
        return None
    purpose = z.s(str(v.get("purpose", "")))
    return {"purpose": purpose} if purpose else None


def _refs(v, known=None) -> list[str]:
    """이 섹션이 다루는 명제 id.

    **모르는 id 는 버린다.** 모델이 지어낸 id 를 그대로 두면 본문 작성이
    없는 명제를 찾다가 그 섹션의 근거가 통째로 비고, 오류 없이 결과만
    틀린다. `known` 을 안 주면 모양만 다듬는다(직접 쓴 값이 그렇다).
    """
    if not isinstance(v, list):
        return []
    out = []
    for r in v:
        r = z.s(str(r), 20)
        if r and r not in out and (known is None or r in known):
            out.append(r)
    return out[:6]


def payload(sections, hero_image=None, known=None, media=True) -> dict:
    """sections 는 {title, objective, covers, exclude, image} 객체 배열.

    이미지 계획을 섹션에 붙여 둔다. 별도 배열로 두고 번호로 가리키면
    섹션이 하나 늘거나 순서가 바뀔 때 조용히 엉뚱한 자리를 가리킨다.
    문자열이 들어오면 소제목만 있는 섹션으로 감싼다 — 직접 쓴 값이 그렇다.

    objective·covers·exclude 는 이 단계가 소제목을 지을 때 쓴 설계 의도다.
    이것이 없으면 본문 작성이 소제목만 보고 내용을 다시 추론하고, 그러면
    섹션마다 같은 이야기가 반복된다. 특히 exclude 가 중요하다 — covers 만
    넘기면 "무엇을 쓸지" 는 분명해져도 "다른 섹션에서 또 쓰는 것" 을 막지
    못한다.

    claim_refs 는 이 섹션이 다룰 명제다. **구조가 한 판단을 본문이 다시
    하지 않게 하는 자리**다 — 없으면 본문 작성이 소제목만 보고 어느 근거를
    어디에 놓을지 다시 정하고, 그러면 구조 단계가 한 일이 사라진다.

    직접 쓴 구조에는 셋 다 없다. 그때는 비워 두고 뒤 단계가 소제목만 본다.
    """
    out = []
    for x in sections:
        if isinstance(x, dict):
            out.append({"title": z.s(str(x.get("title", ""))),
                        "objective": z.s(str(x.get("objective", "")), 200),
                        "covers": z.lines(x.get("covers"), 120, 5),
                        "exclude": z.lines(x.get("exclude"), 120, 5),
                        "role": z.enum(x.get("role"), ROLES) or "",
                        "claim_refs": _refs(x.get("claim_refs"), known),
                        "image": _image(x.get("image")),
                        # 도식이 있는 섹션에는 안 넣는다. 둘 다 있으면 그
                        # 섹션만 무거워지고, 그림이 도식을 설명하는 꼴이 된다.
                        # 도식이나 자료 화면이 있는 섹션에는 그림을 안 넣는다.
                        # 셋이 다 있으면 그 섹션만 무거워지고, 같은 것을 두
                        # 번 보여주게 된다 — media 와 illustration 이 실제로
                        # "요청 문서에서 범위를 확인한다" 를 나눠 가졌다.
                        "illustration": None
                        if (_image(x.get("image")) or _media(x.get("media"), media))
                        else _illustration(x.get("illustration"), media),
                        "media": _media(x.get("media"), media)})
        else:
            out.append({"title": z.s(str(x)), "objective": "", "role": "",
                        "covers": [], "exclude": [], "claim_refs": [],
                        "image": None, "illustration": None, "media": None})
    return {"sections": [x for x in out if x["title"]],
            "hero_image": _hero(hero_image)}


def label(secs, figs, hero, media=0, illus=0) -> str:
    """구조 후보 한 줄 요약.

    셋을 따로 센다. 만드는 주체가 다르기 때문이다.

        도식        코드가 마크업으로 그린다. 결과물에 바로 실린다
        대표 이미지  생성 모델이 그린다
        미디어      **사람이 준비한다.** 사진·캡처는 회사가 가진 파일이다

    합쳐서 "이미지 3장" 으로 세면 파일 세 장을 약속하는 것처럼 보인다.
    """
    parts = [f"{secs}개 부분"]
    if figs:
        parts.append(f"도식 {figs}개")
    if hero:
        parts.append("대표 이미지 1장")
    if illus:
        parts.append(f"본문 그림 {illus}장")
    if media:
        parts.append(f"준비할 자료 {media}건")
    return " · ".join(parts)


def overlap(pay) -> list[str]:
    """두 섹션 이상이 든 명제. 있으면 카드에 표시한다.

    같은 명제를 여러 섹션이 맡으면 소제목만 다르고 내용은 같은 설명이
    반복된다. **지우지는 않는다** — 앞 섹션이 사실을, 뒤 섹션이 그 적용을
    다루는 것은 정당하다. 사람이 보고 판단할 일이라 표시만 한다.
    """
    seen, dup = {}, []
    for x in pay["sections"]:
        for r in x["claim_refs"]:
            seen[r] = seen.get(r, 0) + 1
            if seen[r] == 2:
                dup.append(r)
    return dup


def role_repeat(pay) -> list[str]:
    """같은 역할이 **연속으로 셋 이상** 이어지는가.

    떨어져 있는 반복은 막지 않는다 — 상황·비교·상황 은 정당하다. 문제는
    같은 리듬이 붙어서 이어질 때다. 실제로 나온 글이 설명·목록·정리를
    세 번 되풀이했다.

    지우지 않고 표시만 한다. 정당한 경우가 있고, 후보가 하나만 남으면
    화면이 막힌다.
    """
    rows = [x.get("role") or "" for x in pay["sections"]]
    out, run, prev = [], 0, None
    for r in rows:
        run = run + 1 if r and r == prev else 1
        prev = r
        if run >= 3 and r not in out:
            out.append(r)
    return out


# 이만큼 겹치면 같은 내용으로 본다.
SAME_COVER = 0.6


def distinct_covers(pay) -> int:
    """서로 다른 내용이 몇 가지인가.

    **같은 것을 표현만 바꿔 두 번 쓰면 하나로 센다.** 안 그러면 같은 말을
    늘려 써서 하한을 넘길 수 있다. 낱말 겹침으로 접는다 — 명제를 가르는
    것과 같은 방식이다.
    """
    groups = []
    for x in pay["sections"]:
        for c in x.get("covers") or []:
            w = z.stems(c)
            if not w:
                continue
            if any(len(w & g) / max(len(w), len(g)) >= SAME_COVER for g in groups):
                continue
            groups.append(w)
    return len(groups)


def volume(pay, atype: str, channel: str) -> dict:
    """구조가 담기로 한 양. 하한과 함께 준다.

    **글자 수만 세면 반복이 는다.** 같은 말을 늘려 써도 넘기 때문이다.
    섹션 수 · 서로 다른 내용 · 쓴 명제를 함께 본다.

    글자 수는 여기서 못 잰다 — 본문을 아직 안 썼다. 구조가 정하는 것은
    **몇 가지를 담을 것인가**고, 분량은 그것을 따라온다.
    """
    from ...data import skeletons
    want = skeletons.need(atype, channel)
    used = {r for x in pay["sections"] for r in (x.get("claim_refs") or [])}
    got = {"sections": len(pay["sections"]),
           "covers": distinct_covers(pay),
           "claims": len(used)}
    short = {k: (got[k], want[k]) for k in got if got[k] < want[k]}
    return {"got": got, "want": want, "short": short}


def missing_must(pay, must) -> list[str]:
    """`must_have` 중 어느 섹션도 안 맡은 것.

    **비교형인데 같은 기준이 없으면 비교가 아니다.** 유형을 골라 놓고
    그 유형의 뼈대가 빠지면 글이 그 유형이 아니게 된다.

    문구를 그대로 베끼라고 하지 않았으므로 낱말 겹침으로 본다. 확실히
    못 가르므로 지우지 않고 표시만 한다.
    """
    said = " ".join(
        x.get("objective", "") + " " + " ".join(x.get("covers") or [])
        for x in pay["sections"])
    out = []
    for m in must or []:
        words = [w for w in m.split() if len(w) >= 2]
        if not words:
            continue
        hit = sum(1 for w in words if w[:2] in said)
        if hit / len(words) < 0.5:
            out.append(m)
    return out


def signature(pay) -> tuple:
    """구조의 지문. 후보끼리 실제로 다른지 보는 데 쓴다.

    소제목 표현만 다른 후보는 고를 이유가 없다. 다만 **지우지 않는다** —
    지웠다가 후보가 하나만 남으면 화면이 막힌다. 표시만 한다.

    **`role` 순서도 본다.** 근거 배치가 달라도 `상황 → 기준 → 정리` 가
    되풀이되면 독자가 이해하는 경로는 같다. 실제로 소재와 질문이 달라도
    "개념 설명 → 목록 → 먼저 확인할 것" 으로 접히는 일이 있었다.
    """
    return (tuple(tuple(x["claim_refs"]) for x in pay["sections"]),
            tuple(x.get("role") or "" for x in pay["sections"]))


def flow(pay) -> tuple:
    """설명 흐름만. 근거를 빼고 역할 순서만 본다."""
    return tuple(x.get("role") or "" for x in pay["sections"])


def detail(pay) -> str:
    """카드 요약 줄. 소제목을 화살표로 잇고 무엇이 붙는지 표시한다.

    **표시를 한 모양으로 통일한다.** `+도식` · `+그림` · `자료 1장` 처럼
    섞으면 내부 표기처럼 보인다. 대괄호 하나로 맞춘다.
    """
    return "  →  ".join(
        x["title"] + "".join(f" [{m}]" for m in _marks(x))
        for x in pay["sections"])


def _marks(x) -> list[str]:
    out = []
    if x.get("image"):
        out.append("도식")
    if x.get("illustration"):
        out.append("본문 그림")
    if x.get("media"):
        out.append(_MEDIA.get((x["media"] or {}).get("type", ""), "자료"))
    return out
