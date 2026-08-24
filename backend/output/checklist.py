"""발행 전에 사람이 확인할 것.

**결과물에 넣지 않는다.** 미확인 근거를 본문이나 참고자료에 그대로 실으면
확인되지 않은 것에 출처가 붙은 글이 된다 — 이 파이프라인의 오래된 실패다.

채널을 받는 이유는 채널마다 확인할 것이 다르기 때문이다. 네이버는 도식을
사람이 캡처해 넣어야 하고, 홈페이지는 작성자·검토자가 신뢰 요소다.

**빠진 것을 조용히 넘기지 않는다.** 지어내지 않기로 한 것(작성자 이름,
서비스명)은 안 나가는 대신 여기 뜬다. 안 뜨면 사람이 뭐가 빠졌는지 모른다.
"""

from . import common as C
from ..data import channels, company
from ..steps.evidence import policy


# 결과물에 넣지 않는다. 미확인 근거를 본문이나 참고자료에 그대로 실으면
# 확인되지 않은 것에 출처가 붙은 글이 된다 — 이 파이프라인의 오래된 실패다.

def build(d, ch: str = "site"):
    w = C.body(d)
    out = []

    for u in w.get("unverified") or []:
        out.append({"kind": "근거 확인", "text": u.get("title", ""),
                    "note": u.get("where_to_look") or "확인처 미정"})

    for order in w.get("dropped_figures") or []:
        out.append({"kind": "도식 빠짐",
                    "text": f"{order}번 섹션의 도식을 만들지 못했습니다",
                    "note": "본문을 다시 만들면 채워질 수 있습니다"})

    made = C.hero_made(d)
    hero = C.hero_plan(d).get("purpose")
    if made.get("file"):
        out.append({"kind": "이미지 확인",
                    "text": "대표 이미지가 계획과 맞는지, 글자가 들어가지 않았는지 봅니다",
                    "note": made.get("alt") or hero})
    elif hero:
        out.append({"kind": "이미지 없음",
                    "text": "대표 이미지가 아직 없습니다", "note": hero})

    _authority(out, d, w)
    _media(out, d, ch)
    _title_meta(out, d, ch)
    _structure(out, d)
    _evidence_gap(out, d)
    _service_link(out, d, ch)
    _stale_articles(out, d)
    _rhythm(out, d)
    _specificity(out, d)
    _figure_sense(out, d)
    _type_must(out, d)
    _placeholders(out, d, ch)
    _ending(out, d, ch)
    _volume(out, d, ch)

    if ch == "site" and not company.has_trust():
        # 홈페이지는 작성자·검토자가 신뢰 요소다. 지금은 비어 있어서 안
        # 나간다 — 지어내지 않기로 했으므로 사람에게 알리는 것까지가 코드 몫이다.
        out.append({"kind": "작성 주체 없음",
                    "text": "작성자·검토자가 결과물에 나가지 않습니다",
                    "note": "backend/data/company.py 에 채우면 자동으로 붙습니다"})

    if channels.of(ch).figure_render == "capture":
        n = sum(1 for s in w.get("sections", [])
                for b in C.blocks(s) if b.get("type") == "figure")
        if n:
            out.append({"kind": "도식 캡처",
                        "text": f"도식 {n}개를 이미지로 저장해 넣어야 합니다",
                        "note": "홈페이지 미리보기에서 저장 버튼을 씁니다"})

    return out




def _authority(out, d, w) -> None:
    """자격이 모자란 출처로 규정·사실을 서술했는지 알린다.

    **코드가 문장을 못 읽는다.** 프롬프트에 "규정이 정한다 대신 보도에
    따르면" 이라고 적어 두었지만 지켰는지는 사람이 봐야 안다. 그래서 막지
    않고 어디를 봐야 하는지만 짚는다.

    막지 않는 이유는 자격으로 인용을 막으면 근거 없는 글이 나오기
    때문이다 — 그 판단은 policy.citable() 에 이미 적혀 있다.
    """
    used = {c for sec in (w.get("sections") or []) if isinstance(sec, dict)
            for c in (sec.get("cites") or [])}
    weak = [s_ for s_ in (w.get("sources") or [])
            if isinstance(s_, dict) and s_.get("id") in used
            and s_.get("claim_type") in ("regulation", "fact")
            and s_.get("authority") == "insufficient"]
    if not weak:
        return
    out.append({
        "kind": "출처 자격",
        "text": f"공식 원문 없이 서술한 주장이 {len(weak)}건 있습니다",
        "note": "제도가 정한 것처럼 쓰였는지 봅니다 — "
                + " / ".join(z_title(s_) for s_ in weak[:3])})


def z_title(s_) -> str:
    t = str(s_.get("title") or "")
    return t[:60] + ("…" if len(t) > 60 else "")


def _media(out, d, ch="site") -> None:
    """사람이 준비해야 할 사진·캡처.

    **생성하지 않는다.** 회의 사진이나 공식 문서 화면을 모델이 그리면 그건
    사진이 아니라 가짜 현장이다. 구조 단계가 "어떤 자료가 필요한지" 까지만
    정하고, 실제로 채우는 일은 여기서 사람에게 넘어간다.

    안 알리면 결과물에 자리표시만 남은 채 발행된다.
    """
    rows = list(C.media_of(d).items())
    il = list(C.illustrations_of(d).items())
    if il:
        out.append({
            "kind": "본문 그림",
            "text": f"만들어야 할 본문 그림이 {len(il)}장 있습니다",
            "note": " / ".join(f"{n}번 섹션 — {v['purpose'][:40]}" for n, v in il[:3])})
    if not rows:
        return
    out.append({
        "kind": "준비할 자료",
        "text": f"직접 넣어야 할 사진·자료 화면이 {len(rows)}건 있습니다",
        "note": " / ".join(
            f"{n}번 섹션 {channels.label(ch, m['type'])} — {m['purpose'][:40]}"
            for n, m in rows[:3])})


def _title_meta(out, d, ch) -> None:
    """채널이 요구하는 제목 부가정보가 비었을 때.

    직접 쓴 제목이 그렇다. 만들어 주려면 채널마다 다른 프롬프트가 필요해서
    아직 없고, 안 알리면 메타 설명 없이 발행된다.
    """
    pay = (d.get("title", {}).get("payload") or {})
    if not pay:
        return
    want = []
    pol = channels.of(ch)
    if pol.meta_required:
        if not pay.get("meta_description"):
            want.append("메타 설명")
        if not pay.get("slug"):
            want.append("URL 슬러그")
    if pol.tags_allowed:
        if not pay.get("main_keyword"):
            want.append("대표 키워드")
        if not pay.get("tags"):
            want.append("태그")
    if not want:
        return
    # **조사를 이어 붙이지 않는다.** 앞말 받침에 따라 이/가가 달라지는데
    # 목록 끝이 무엇일지 모른다 — "URL 슬러그이" 가 실제로 나왔다.
    out.append({"kind": "제목 부가정보",
                "text": "비어 있습니다 — " + " · ".join(want),
                "note": "직접 쓴 제목에는 자동으로 채워지지 않습니다"})


def _structure(out, d) -> None:
    """구조가 평면적인지 짚는다.

    **후보를 못 고르게 막는 것이 아니다.** 이미 고른 뒤라 되돌릴 수 없고,
    다만 결과물을 읽기 전에 어디를 볼지 알려 준다.

    두 가지를 본다.

        같은 명제를 여러 섹션이 맡았나   → 같은 설명이 반복된다
        결론이 명제를 다시 들었나        → 전부 다루는 섹션이 하나 더 생긴 셈

    구조 카드에도 표시되지만, 사람이 그걸 안 보고 넘어갔을 수 있다.
    """
    secs = (d.get("outline", {}).get("payload") or {}).get("sections") or []
    if not secs:
        return

    seen, dup = {}, []
    for x in secs:
        for r in (x.get("claim_refs") or []):
            seen[r] = seen.get(r, 0) + 1
            if seen[r] == 2:
                dup.append(r)
    if dup:
        out.append({
            "kind": "근거 배치",
            "text": f"같은 근거를 여러 섹션이 다룹니다 ({len(dup)}건)",
            "note": "본문에 같은 설명이 반복됐는지 봅니다 — " + " · ".join(dup[:4])})

    last = secs[-1]
    if len(secs) > 2 and len(last.get("claim_refs") or []) >= 3:
        out.append({
            "kind": "마지막 섹션",
            "text": "마지막 섹션이 근거를 여러 개 다시 듭니다",
            "note": f"\"{last.get('title', '')[:30]}\" — 앞 내용을 되풀이하는지 봅니다"})


def _evidence_gap(out, d) -> None:
    """근거가 왜 미확인인지 갈라서 알린다.

    **"안 찾아봤다" 와 "찾았는데 없다" 는 사람이 할 일이 다르다.** 앞은
    키를 넣거나 원문을 올리면 되고, 뒤는 명제를 다시 세우거나 다른 자료를
    찾아야 한다. 뭉쳐서 "확인 필요" 로만 보이면 어느 쪽인지 모른다.
    """
    items = (d.get("evidence", {}).get("payload") or {}).get("items") or []
    rows = [c for c in items if isinstance(c, dict) and c.get("claim_id")]
    if not rows:
        return

    off = [c for c in rows if c.get("reason_code") == "search_disabled"]
    if off:
        out.append({
            "kind": "근거 검색 꺼짐",
            "text": f"검색을 하지 않아 {len(off)}건이 미확인입니다",
            "note": "TAVILY_API_KEY 를 넣거나 원문 PDF 를 올려 주세요 — "
                    "찾아봤는데 없는 것이 아닙니다"})

    weak = [c for c in rows if not policy.citable(c)]
    if weak and len(weak) == len(rows):
        out.append({
            "kind": "인용할 근거 없음",
            "text": "본문에 출처를 달 수 있는 근거가 하나도 없습니다",
            "note": "확인된 것이 없으면 본문이 사실을 단정하지 못합니다"})


# 이것이 확인 목록에 있으면 그대로 내면 안 된다.
BLOCKING = ("인용할 근거 없음", "출처 자격", "근거 검색 꺼짐")


def ready(d, rows) -> dict:
    """이 글을 그대로 내도 되나.

    **확인 목록을 다 읽지 않아도 한 줄로 보이게 한다.** 목록이 길면 사람이
    안 읽고 발행하는데, 그게 실제로 났던 실패다 — 인용 가능한 근거가 0건인
    글이 완성본처럼 보였다.

    막지는 않는다. 근거 없이도 내야 할 때가 있고, 그 판단은 사람 몫이다.
    """
    blocking = [r for r in rows if r["kind"] in BLOCKING]
    items = (d.get("evidence", {}).get("payload") or {}).get("items") or []
    claims = [c for c in items if isinstance(c, dict) and c.get("claim_id")]
    citable = [c for c in claims if policy.citable(c)]

    if blocking:
        return {"ok": False,
                "text": f"발행 전에 확인할 것이 {len(blocking)}건 있습니다",
                "why": [r["text"] for r in blocking],
                "cited": len(citable), "claims": len(claims)}
    return {"ok": True,
            "text": ("인용할 수 있는 근거 " + str(len(citable)) + "건"
                     if citable else "확인할 것이 없습니다"),
            "why": [], "cited": len(citable), "claims": len(claims)}


def _service_link(out, d, ch) -> None:
    """서비스 연결과 안내가 빠졌을 때.

    **지어내지 않는 대신 알린다.** 서비스 이름을 모르면 관련 서비스도 CTA 도
    안 나가는데, 안 알리면 글이 "그래서 뭘 하면 되나" 없이 끝난 채 발행된다.
    """
    sid = (d.get("topic", {}).get("payload") or {}).get("service_id", "")
    if company.service(sid):
        return
    out.append({
        "kind": "서비스 연결 없음",
        "text": "관련 서비스와 안내 문구가 나가지 않습니다",
        "note": (f"소재에 service_id 가 없습니다" if not sid
                 else f"backend/data/company.py 의 SERVICES 에 {sid} 가 없습니다")})


SHAPE_LABELS = {"list": "번호형 목록", "check": "체크 문항",
                "callout": "강조 박스", "figure": "도식", "para": "줄글"}


def _rhythm(out, d) -> None:
    """읽는 리듬이 평평한지 짚는다.

    같은 모양으로 끝나는 섹션이 셋 이어지면 논리는 맞아도 글이 평평해진다.
    도식이 하나뿐인 것도 같은 문제다 — 시각적으로 볼 것이 없다.

    **막지 않는다.** 이미 만들어진 본문을 코드가 다시 쓸 수는 없고, 정당한
    경우도 있다. 어디를 볼지 알려 주는 것까지다.
    """
    from . import write as W
    secs = C.body(d).get("sections") or []
    if len(secs) < 3:
        return

    run = W.flat_run(secs)
    if run:
        names = " · ".join(SHAPE_LABELS.get(t, t) for t in run)
        out.append({
            "kind": "읽는 리듬",
            "text": f"같은 모양으로 끝나는 섹션이 셋 이어집니다 ({names})",
            "note": "하나를 도식이나 줄글로 바꾸면 읽는 흐름이 살아납니다"})

    figs = sum(1 for s_ in secs for b in C.blocks(s_) if b.get("type") == "figure")
    if figs <= 1:
        out.append({
            "kind": "도식이 적다",
            "text": f"본문 도식이 {figs}개입니다",
            "note": "글이 텍스트로만 이어지는지 봅니다 — "
                    "필요 없으면 그대로 두어도 됩니다"})


def _stale_articles(out, d) -> None:
    """소재에 딸려온 기사 주소가 낡았을 때.

    뉴스 주소는 기사가 내려가면 다른 기사로 넘어간다. 코드가 걸러 내지만
    **소재를 고른 근거였던 기사가 사라졌다는 뜻**이라, 사람이 알아야 한다.
    """
    rows = (d.get("evidence", {}).get("payload") or {}).get("items") or []
    bad = [r for r in rows if isinstance(r, dict) and r.get("status") == "wrong_page"]
    if not bad:
        return
    out.append({
        "kind": "기사 주소가 낡음",
        "text": f"소재에 딸려온 기사 {len(bad)}건을 가져오지 못했습니다",
        "note": "그 주소에 다른 글이 있습니다 — 소재를 고른 근거가 사라졌을 수 있습니다"})


def _specificity(out, d) -> None:
    """무엇을 하라고만 하고 무엇을 보라고는 안 한 문장.

    **"확인합니다" 로 끝나는 문장은 아무것도 안 알려 준다.** 독자는 이미
    확인해야 한다는 걸 알고 있고, 무엇을 어떤 기준으로 보는지를 모른다.
    실제로 네이버 글이 그런 문장으로 채워져 나왔다.

    막지 않는다. 어느 문장을 손볼지 알려 주는 것까지다.
    """
    from . import write as W
    rows = W.vague_rows(C.body(d).get("sections") or [])
    if not rows:
        return
    out.append({
        "kind": "구체 기준 부족",
        "text": f"무엇을 볼지 안 적은 문장이 {len(rows)}개 있습니다",
        "note": " / ".join(f'{r["heading"][:12]} — {r["text"][:34]}'
                           for r in rows[:3])})


def _figure_sense(out, d) -> None:
    """도식이 관계를 왜곡하는가.

    **틀린 정보를 그림으로 확정하는 것**이 글로 쓰는 것보다 나쁘다. 글은
    고칠 수 있지만 그림은 캡처해서 나가면 못 고친다. 실제로 "신고 의무"
    아래에 신고 주체와 자료 제공자가 나란히 놓인 적이 있다.

    막지 않는다. 확실히 못 가르는 것이라 사람이 봐야 한다.
    """
    from . import figures
    from . import figures
    from . import write as W2

    # 도식이 본문에 없는 기준을 드는가. 읽는 사람이 나머지를 어디서
    # 확인해야 할지 모른다.
    ahead = []
    for s_ in C.body(d).get("sections") or []:
        for k in W2.figure_ahead(s_):
            ahead.append(f'{s_.get("heading", "")[:12]} — {k}')
    if ahead:
        out.append({
            "kind": "도식이 본문보다 앞섬",
            "text": f"본문에 없는 기준이 도식에 {len(ahead)}개 있습니다",
            "note": " / ".join(ahead[:3])})

    bad = []
    for n, (sec, b) in enumerate(
            [(s_, b) for s_ in C.body(d).get("sections") or []
             for b in C.blocks(s_) if b.get("type") == "figure"], 1):
        for why in figures.flaws(b.get("component"), b.get("data")):
            bad.append(f"도식 {n} — {why}")
    if not bad:
        return
    out.append({
        "kind": "도식 관계 확인",
        "text": f"관계가 어긋나 보이는 도식이 {len(bad)}건 있습니다",
        "note": " / ".join(bad[:3])})


def _type_must(out, d) -> None:
    """이 유형의 뼈대가 빠졌는가.

    **비교형인데 같은 기준이 없으면 비교가 아니다.** 유형을 골라 놓고 그
    뼈대가 빠지면 글이 그 유형이 아니게 된다.
    """
    from ..data import skeletons
    from ..steps.outline.payload import missing_must
    atype = (d.get("type", {}).get("payload") or {}).get("article_type", "")
    pay = d.get("outline", {}).get("payload") or {}
    if not atype or not pay.get("sections"):
        return
    gap = missing_must(pay, skeletons.for_outline(atype).get("must_have"))
    if not gap:
        return
    out.append({
        "kind": f"{atype}에 필요한 내용",
        "text": f"이 유형이 답해야 할 것 {len(gap)}가지가 안 다뤄집니다",
        "note": " · ".join(gap[:5])})


# 결과물에 남으면 안 되는 말. 미리보기·개발용으로 넣은 값이 그대로 나가면
# 회사 글에 남의 이름과 없는 주소가 실린다.
LEFTOVER = ("example.com", "example.org", "localhost",
            "김OO", "홍길동", "OOO", "TODO", "TBD", "lorem ipsum")


def _placeholders(out, d, ch) -> None:
    """자리표시가 결과물에 남았는가.

    **미완료 표시가 남은 글은 최종본이 아니다.** 도식·사진 자리는 사람이
    채우는 것이라 여기서 안 본다 — 그건 따로 알리고 있다. 여기서 보는 것은
    **채워졌어야 하는데 견본이 남은 것**이다.
    """
    from . import render as _r
    body = C.body(d)
    text = " ".join(
        [body.get("lead", "")]
        + [t for s_ in body.get("sections") or [] for b in C.blocks(s_)
           for t in _texts(b)]
        + [s_.get("title", "") for s_ in body.get("sources") or []]
        + [s_.get("url", "") for s_ in body.get("sources") or []])
    from ..data import company
    text += " " + " ".join(
        str(v) for a in (company.AUTHORS + company.REVIEWERS) for v in a.values())

    hit = sorted({w for w in LEFTOVER if w.lower() in text.lower()})
    if not hit:
        return
    out.append({
        "kind": "견본 값이 남음",
        "text": f"바꿔야 할 자리표시가 {len(hit)}건 있습니다",
        "note": " / ".join(hit[:4])})


def _texts(b) -> list:
    from . import write as W
    return W._texts(b)


def _ending(out, d, ch) -> None:
    """네이버 글이 갑자기 끝나는가.

    마지막 섹션이 목록이나 강조 박스로 끝나면 **글이 멈춘 것처럼 읽힌다.**
    실제로 그렇게 났다 — 점검 항목을 늘어놓고 바로 안내 문구가 나왔다.

    홈페이지는 참고자료·작성자·서비스가 뒤에 붙어 마무리가 되므로 안 본다.
    """
    if ch != "naver":
        return
    secs = C.body(d).get("sections") or []
    if len(secs) < 2:
        return
    # **진짜 마지막 블록**을 본다. shape_of 는 그 섹션의 인상을 보려고
    # 뒤에서 첫 구조 블록을 찾는데, 맺음은 정말 끝에 무엇이 있는지다.
    blocks = C.blocks(secs[-1])
    last = (blocks[-1] if blocks else {}).get("type", "")
    if last == "para":
        return
    out.append({
        "kind": "맺음이 없다",
        "text": f"마지막 섹션이 {SHAPE_LABELS.get(last, last)}(으)로 끝납니다",
        "note": "앞에서 짚은 판단을 모으고 다음 확인으로 넘기는 문단이 필요합니다"})


def _volume(out, d, ch) -> None:
    """근거가 있는데 글이 일찍 끝나는가.

    **글자 수만 세면 반복이 는다.** 같은 말을 늘려 써도 넘기 때문이다.
    섹션 수 · 서로 다른 내용 · 쓴 명제 · 본문 글자 수를 함께 본다.

    실제로 근거가 열 묶음인데 셋만 쓰고 900자로 끝난 글이 나왔다.
    """
    from ..data import skeletons
    from ..steps.outline.payload import volume
    atype = (d.get("type", {}).get("payload") or {}).get("article_type", "")
    pay = d.get("outline", {}).get("payload") or {}
    if not atype or not pay.get("sections"):
        return

    v = volume(pay, atype, ch)
    short = dict(v["short"])
    # **근거 부족은 구조 탓이 아니다.** 구조를 바꿔도 안 풀린다 — 근거를
    # 더 찾아야 한다. 그래서 따로 알린다.
    if "claims" in short:
        a, b = short.pop("claims")
        out.append({
            "kind": "근거가 적다",
            "text": f"확인된 근거 현재 {a}건 / 기준 {b}건",
            "note": "구조를 바꿔도 안 풀립니다 — 근거를 더 확보해야 합니다"})

    # 본문 글자 수는 여기서만 잴 수 있다. **도식 안 글자는 안 센다** —
    # 표 하나로 하한을 넘길 수 있다.
    n = _body_chars(d)
    lo = v["want"]["chars"][0]
    if n and n < lo:
        short["chars"] = (n, lo)
    if not short:
        return

    # 화면에 나가는 말. 내부 이름을 그대로 보이지 않는다.
    if not short:
        return
    name = {"sections": "부분", "covers": "다루는 내용", "chars": "본문 글자"}
    out.append({
        "kind": "담은 것이 적다",
        "text": f"이 유형에 견주면 {len(short)}가지가 모자랍니다",
        "note": " / ".join(f"{name[k]} 현재 {a} / 기준 {b}"
                           for k, (a, b) in short.items())})


def _body_chars(d) -> int:
    """읽는 사람이 실제로 읽는 글자. 도식 안 글자는 빼고 센다."""
    from . import write as W
    body = C.body(d)
    n = len(body.get("lead") or "")
    for s_ in body.get("sections") or []:
        n += len(s_.get("heading") or "")
        for b in C.blocks(s_):
            if b.get("type") == "figure":
                n += len(b.get("takeaway") or "") + len(b.get("caption") or "")
                continue
            n += sum(len(t) for t in W._texts(b))
    return n
