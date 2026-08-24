"""9단계 — 제목.

후보 4~5개를 만들고, 유형과 어긋나는 표현이 든 것은 코드에서 걸러낸다.

BAN 이 코드에 있는 이유는, prompt.md 에 "정보형에 대응 방법을 쓰지 않는다"
를 적어 뒀는데 모델이 어겼고 후속 코드가 그대로 승인했기 때문이다.
프롬프트를 더 길게 써도 안 풀리는 종류라 코드에서 한 겹 더 막는다.
"""

from ... import llm, sanitize as z
from ...data import channels
from ..payload import is_citable, topic_brief, topic_keywords
from ..step import Step, label_of, opt, pay, pick_meta

# 좁게 시작한다. 두 유형만 본다 — 비교형에서 "절차", 체크리스트형에서
# "개념 정리" 를 막는 건 오탐이 날 것 같다. 로그가 쌓이면 그때 늘린다.
BAN = {
    "정보형": ("대응 방법", "대응 전략", "준비 단계", "하는 법", "대응법"),
    "가이드형": ("란 무엇인가", "란?", "이란?", "의 뜻", "개념 정리"),
}


SLUG_MAX = 60
SLUG_WORDS = 6

# 이보다 짧은 키워드는 세지 않는다. 한 글자는 아무 제목에나 걸린다.
KEYWORD_MIN = 2


def _norm(v) -> str:
    """공백을 접고 소문자로. 조사 때문에 못 잡는 것을 막는다.

    한국어는 낱말 뒤에 조사가 붙어서 정확히 일치하는 일이 드물다.
    "CBAM" 은 "CBAM이" 로, "내재배출량" 은 "내재배출량을" 로 나온다.
    공백까지 접으면 "탄소 배출량" 이 "탄소배출량의" 안에서도 잡힌다.
    """
    return "".join(str(v or "").lower().split())


def used_keywords(title, keywords) -> list[str]:
    """제목에 **실제로 들어간** 키워드.

    모델에게 물어보지 않는다. 물어보면 제목에 없는 것을 썼다고 하거나,
    입력에 없는 낱말을 지어내거나, 조사가 붙었다고 빠뜨린다. 세는 일은
    코드가 정확히 할 수 있다.
    """
    t = _norm(title)
    out = []
    for row in keywords if isinstance(keywords, list) else []:
        k = str((row or {}).get("keyword", "") if isinstance(row, dict) else row).strip()
        n = _norm(k)
        if len(n) >= KEYWORD_MIN and n in t and k not in out:
            out.append(k)
    return out


def payload(text, style, keywords=(), channel="site", got=None) -> dict:
    """확정값 한 벌. **모양은 채널과 상관없이 같다.**

    채널마다 다른 필드를 내면 그것을 읽는 쪽(저장·API·화면·결과물)이 양쪽을
    다 알아야 한다. 그래서 필드는 늘 다 두고 **채널에 안 맞는 것만 비운다.**

    글자 수는 코드가 센다. LLM 은 글자를 정확히 세지 못한다.

    비우는 일도 코드가 한다. 프롬프트에 "빈 값으로 두라"고 적어 두었지만
    지키지 않는 날이 있고, 그때 네이버 결과물에 엉뚱한 슬러그가 붙는다.
    """
    got = got or {}
    pol = channels.of(channel)
    meta, tags_ok, cap = pol.meta_required, pol.tags_allowed, pol.max_tags

    return {
        "title": text, "char_count": len(text),
        "title_style": style,
        # 모델이 아니라 코드가 센다.
        "used_keywords": used_keywords(text, keywords),
        # 홈페이지만
        "meta_description": z.s(got.get("meta_description"), 160) if meta else "",
        "slug": _slug(got.get("slug"), text) if meta else "",
        # 네이버만. 모델이 고른 것을 그대로 믿지 않는다 — 입력에 없는
        # 낱말이거나 제목에 안 들어간 것이면 검색에 안 걸린다.
        "main_keyword": _main(got.get("main_keyword"), text, keywords) if tags_ok else "",
        "secondary_keywords": z.texts(got.get("secondary_keywords"), 4) if tags_ok else [],
        "tags": _tags(got.get("tags"), cap) if tags_ok else [],
    }


def _tags(rows, cap) -> list[str]:
    """태그를 다듬는다. `#` 과 공백을 털고 겹치는 것을 걷는다.

    모델이 `#CBAM` 처럼 적어 오면 붙일 때 `##CBAM` 이 된다. 붙이는 일은
    결과물 조립이 하므로 여기서는 낱말만 남긴다.
    """
    seen, out = set(), []
    for t in (rows if isinstance(rows, list) else []):
        t = z.s(t, 30).lstrip("#").strip().replace(" ", "")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:cap]


def _main(proposed, title, keywords) -> str:
    """대표 검색어. 제목에 실제로 들어간 것 중에서 고른다.

    모델이 고른 것이 제목에 없으면 버리고, 쓰인 키워드 중 검색량이 가장
    높은 것으로 대신한다. 하나도 없으면 빈 문자열이다.
    """
    used = used_keywords(title, keywords)
    p = str(proposed or "").strip()
    if p and p in used:
        return p
    if not used:
        return ""
    volume = {str((r or {}).get("keyword", "")): (r or {}).get("volume", 0)
              for r in keywords if isinstance(r, dict)}
    return max(used, key=lambda k: volume.get(k, 0))


def _slug(raw, title=None) -> str:
    """URL 에 쓸 영문 조각. 코드가 다듬는다.

    모델이 낸 값을 그대로 쓰면 공백·대문자·한글이 섞여 들어와 주소가
    깨진다. 영문이 하나도 없으면 빈 문자열을 준다 — 한글을 로마자로
    옮기는 규칙은 표기가 여럿이라 여기서 정할 일이 아니고, 사람이 CMS 에서
    채우는 편이 낫다.
    """
    import re
    out = re.sub(r"[^a-z0-9]+", "-", (raw or "").strip().lower()).strip("-")
    # 낱말 수도 제한한다. 길이만 자르면 마지막 낱말이 잘려 나간다.
    return "-".join([x for x in out.split("-") if x][:SLUG_WORDS])[:SLUG_MAX]


def build_input(d) -> dict:
    """제목은 구조 다음이다.

    구조가 먼저 서면 제목이 **실제로 다룰 내용** 위에서 만들어진다. 반대
    순서였을 때는 제목이 약속한 것을 구조가 못 채우는 일이 있었다.

    **소제목 문자열만 넘기면 그 효과가 절반 사라진다.** "달라지는 기준은
    검증 가능성이다" 라는 소제목만 보면 무엇이 검증되는지 — 법적 의무인지
    내부 추적성인지, 공식 원문으로 확인된 것인지 — 알 수 없다. 그래서
    설계 의도(`objective` · `covers` · `exclude`)와 근거 연결(`claim_refs`)을
    함께 넘기고, 거기 걸린 명제도 상태째 넘긴다.
    """
    secs = _sections(d)
    return {
        "topic": topic_brief(d, keywords=False),
        "reader": pay(d, "reader"),
        "intent": pay(d, "intent"),
        "angle": pay(d, "angle"),
        "article_type": pay(d, "type").get("article_type", ""),
        "type_reason": pay(d, "type").get("type_reason", ""),
        "sections": secs,
        # 구조가 실제로 쓰기로 한 명제만. 제목이 사실을 담을 때 그것이
        # 확인된 것인지 알아야 한다.
        "claims": _claims(d, secs),
        # 인용 가능한 근거가 몇 건인지. 0 이면 제목이 "이유" 나 "원인" 을
        # 약속하면 안 된다 — 본문이 그 답을 못 준다.
        "evidence_state": _evidence_state(d, secs),
        "keywords": topic_keywords(d),
        # 프롬프트 이름이 이미 채널을 정한다. 자취에서 무엇으로 돌았는지
        # 보려고 싣는다.
        "channel": pay(d, "channel").get("channel", "site"),
    }


def _sections(d) -> list[dict]:
    """구조를 제목이 읽을 만큼만. 이미지·미디어 계획은 뺀다."""
    return [{"title": x.get("title", ""),
             "objective": x.get("objective", ""),
             "covers": x.get("covers") or [],
             "exclude": x.get("exclude") or [],
             "claim_refs": x.get("claim_refs") or []}
            for x in (pay(d, "outline").get("sections") or [])
            if isinstance(x, dict) and x.get("title")]


def _evidence_state(d, secs) -> dict:
    """구조가 쓰기로 한 명제 중 실제로 인용할 수 있는 것이 몇인가.

    제목이 무엇을 약속할 수 있는지가 여기서 갈린다. 근거가 하나도 없는데
    "왜 어긋나는가" 를 제목에 걸면 본문이 그 답을 못 준다 — 제목이 약속한
    것을 본문이 못 주면 그 제목이 틀린 것이다.
    """
    # 판정은 steps/payload.py 가 한다. 단계끼리 import 하지 않는다 —
    # 여러 단계가 읽는 판단은 거기 모아 두기로 했다.
    rows = _claims(d, secs)
    citable = [c for c in rows if is_citable(c)]
    return {"citable": len(citable), "total": len(rows),
            "can_assert": bool(citable)}


def _claims(d, secs) -> list[dict]:
    """구조가 `claim_refs` 로 건 명제만. 안 쓰는 것까지 넘길 이유가 없다."""
    refs = {r for x in secs for r in x["claim_refs"]}
    out = []
    for c in pay(d, "evidence").get("items") or []:
        if not isinstance(c, dict) or c.get("claim_id") not in refs:
            continue
        out.append({"claim_id": c["claim_id"],
                    "claim": c.get("claim") or c.get("title", ""),
                    "claim_type": c.get("claim_type", ""),
                    "status": c.get("status", ""),
                    "authority": c.get("authority", ""),
                    "limitations": [z_ for s_ in (c.get("sources") or [])
                                    for z_ in (s_.get("limitations") or [])][:3]})
    return out


def _bad(title, atype) -> str:
    """유형과 어긋나는 표현. 없으면 빈 문자열."""
    for bad in BAN.get(atype, ()):
        if bad in title:
            return bad
    return ""


def make(d, inp) -> list[dict]:
    atype = inp.get("article_type") or "정보형"
    cands = (llm.candidates(STEP.prompt_of(inp.get("channel", "")), inp, ("title",))
             if llm.ENABLED else _offline(d, inp))

    rows = []
    for c in cands:
        t = z.s(c["title"])
        if t:
            rows.append((t, c, _bad(t, atype)))

    clean = [r for r in rows if not r[2]]
    # 전부 어긋나면 지우지 않고 표시만 한다. 후보가 0개가 되면 화면이 막힌다.
    keep, warn = (clean, False) if clean else (rows, True)

    out = []
    for i, (t, c, bad) in enumerate(keep):
        style = c.get("title_style") or "직접"
        kws = used_keywords(t, inp.get("keywords") or [])
        meta = f"{len(t)}자" + (f" · 쓰인 키워드 {', '.join(kws)}" if kws else "")
        if warn and bad:
            meta += f" · {atype}에 안 맞는 표현 \"{bad}\""
        why = c.get("rationale") or f"{atype}에 맞춘 {style} 제목"
        # 첫 후보가 추천이다. 프롬프트가 "질문에 가장 직접 답하는 제목을
        # 첫 번째로" 라고 정한다.
        out.append(opt(f"t{i}", t, why,
                       pick_meta(meta, why) if not out else meta,
                       payload(t, style, inp.get("keywords") or [],
                               channel=inp.get("channel", "site"), got=c)))
    return out


def _offline(d, inp):
    subject = label_of(d, "topic") or "이 주제"
    role = pay(d, "reader").get("role", "담당자")
    kws = [k["keyword"] for k in inp.get("keywords") or []] or ["대응"]
    kw = kws[0]
    head = subject.split(",")[0].strip()
    # 숫자형("대응 5단계")을 만들지 않는다. 구조가 실제로 5개인지 모르는데
    # 제목이 그 수를 약속하면 뒤 단계가 그 수를 채우려 한다.
    return [
        {"title": f"{head}, 무엇부터 확인해야 하나", "title_style": "질문형"},
        {"title": f"{role}를 위한 {head} 정리", "title_style": "독자지정형"},
        {"title": f"{head} 대응에서 먼저 볼 기준", "title_style": "기준형"},
        {"title": f"{kw} 준비, 놓치기 쉬운 지점", "title_style": "키워드형"},
        {"title": f"지금 시점에서 {head} 판단 기준", "title_style": "선언형"},
    ]


def written(t, inp=None):
    """직접 쓴 제목.

    메타·슬러그·태그는 빈다. 그건 채널마다 다른 것을 만들어야 해서 별도
    프롬프트가 필요하고, 아직 없다 — 발행 전 확인 목록이 그 사실을 알린다.

    다만 **쓰인 키워드는 코드가 센다.** 그건 계산이라 모델이 필요 없다.
    """
    inp = inp or {}
    return (t, f"{len(t)}자 · 직접 쓴 제목",
            payload(t, "직접", inp.get("keywords") or [],
                    channel=inp.get("channel", "site")))


STEP = Step(
    key="title", name="제목", eyebrow="TITLE", h1="제목 선택",
    hint="제목을 직접. 글자 수는 저장할 때 세어 둔다.",
    build_input=build_input, make=make, written=written,
    prompt="_prompt.md", by_channel=True, written_needs_input=True,
)
