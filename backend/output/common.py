"""두 채널 렌더러가 함께 쓰는 조각.

`site/render.py` 와 `naver/render.py` 가 같은 본문에서 서로 다른 결과물을
만든다. 그 둘이 각자 복사해 두면 안 되는 것들이 여기 있다 — 확정값을 어떻게
꺼내는지, 섹션의 표현 블록을 어떻게 읽는지.

**두 렌더러는 서로를 import 하지 않는다.** 한쪽이 다른 쪽을 부르면 "홈페이지
것을 조금 고쳐 네이버 것을 만든다" 가 되고, 그 순간 네이버가 홈페이지의
파생물이 되어 채널을 가른 뜻이 없어진다. 공유는 여기를 통해서만 한다.

`figures.py` 도 공유다. 도식 데이터는 한 벌이고 네이버 것은 그 마크업을
캡처해 쓴다 — 두 갈래가 각자 그리면 어긋나지만 하나에서 나오면 어긋날 수가
없다.

**추론이 없다.** 본문 작성이 만든 것을 꺼내 주기만 한다.
"""


def body(d):
    return d.get("write") or {}


def tags(d):
    """네이버 태그.

    **제목 단계가 만든 것을 쓴다.** 예전에는 여기서 `fake.load_keywords()` 를
    불러 소재 키워드로 채웠는데, 그건 검색량으로 뽑힌 값이라 이 글이 실제로
    다루는 것과 어긋날 수 있다. 제목이 비면 소재에 붙은 키워드로 메운다.
    """
    pay = d.get("title", {}).get("payload", {})
    made = [t for t in (pay.get("tags") or []) if t]
    if made:
        return made

    kws = [k.get("keyword", "") for k in
           ((d.get("topic", {}).get("payload") or {}).get("keywords") or [])
           if isinstance(k, dict)]
    used = pay.get("used_keywords", [])
    seen, out = set(), []
    for k in used + kws:
        k = k.strip().replace(" ", "")
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:6]


def title(d):
    return d.get("title", {}).get("payload", {}).get("title", "")


# ── 표현 블록 ─────────────────────────────────────────────────
#
# 섹션 하나가 문단만 갖는 게 아니다. 번호형 목록, 체크리스트, 강조 박스가
# 문단 사이 어디에도 올 수 있어야 한다. paragraphs + figure 두 칸으로는
# 순서를 적을 수 없어서 blocks 배열로 받는다.
#
#   para     문단
#   list     번호형 목록 — 순서 없는 핵심 사항 3~5개
#   check    체크리스트 — 독자가 자기 상태를 확인하는 문항
#   callout  강조 박스 — 섹션의 핵심 결론 한 문장
#   figure   도식 — figures.py 가 그린다. takeaway 를 같이 들고 있다
#
# list·check·callout 은 도식이 아니다. 네이버 에디터가 ol·ul·blockquote 를
# 그대로 받으므로 캡처가 필요 없다. 캡처가 필요한 것은 figure 뿐이다.
#
# takeaway 를 figure 안에 두는 이유는, 도식이 검증에 걸려 버려질 때 해석
# 문장만 고아로 남지 않게 하려는 것이다. 그리는 위치는 <figure> 밖이다.

BLOCKS = ("para", "list", "check", "callout", "figure")


def blocks(sec):
    """섹션의 표현 블록.

    blocks 가 있으면 그것을, 없으면 옛 paragraphs + figure 를 옮겨 담는다.
    write.md 가 blocks 를 내기 전까지 두 형식이 함께 돈다 — 그동안에도
    화면과 테스트가 그대로 돌아야 하므로 여기 한 곳에서 흡수한다.
    """
    got = sec.get("blocks")
    if isinstance(got, list) and got:
        return [b for b in got
                if isinstance(b, dict) and b.get("type") in BLOCKS]

    out = [{"type": "para", "text": p} for p in (sec.get("paragraphs") or []) if p]
    fig = sec.get("figure")
    if fig:
        out.append({"type": "figure", **fig})
    return out


def items(b):
    return [x for x in (b.get("items") or []) if x]


def hero_plan(d):
    """대표 이미지 계획. 6단계가 정한 것."""
    return (d.get("outline", {}).get("payload", {}) or {}).get("hero_image") or {}


def hero_made(d):
    """실제로 만들어진 대표 이미지. 없으면 빈 딕셔너리."""
    return d.get("hero") or {}




def _same_doc(url: str, title: str) -> str:
    """같은 문서인지 가르는 열쇠.

    URL 만 보면 같은 문서의 **PDF 와 안내 페이지**가 둘로 남는다. 실제로
    참고자료에 이렇게 나왔다.

        Corporate Value Chain (Scope 3) Accounting and ...
        Corporate Value Chain (Scope 3) Standard

    제목 앞부분이 같으면 같은 문서로 본다. 도메인이 다르면 다른 문서다 —
    같은 제목의 다른 기관 자료를 하나로 접으면 안 된다.
    """
    host = ""
    if url.startswith(("http://", "https://")):
        host = url.split("//", 1)[1].split("/")[0].lower()
    head = "".join((title or "").lower().split())[:24]
    return f"{host}|{head}" if head else (url or title)


# 자주 나오는 기관. 주소만으로는 이름을 알 수 없다.
ORGS = {
    "europa.eu": "European Commission",
    "dehst.de": "DEHSt",
    "epa.ie": "Ireland EPA",
    "naturvardsverket.se": "Swedish EPA",
    "ghgprotocol.org": "GHG Protocol",
    "iso.org": "ISO",
    "me.go.kr": "환경부",
    "keiti.re.kr": "한국환경산업기술원",
    "law.go.kr": "국가법령정보센터",
    "kemco.or.kr": "한국에너지공단",
}


def _org(url: str) -> str:
    """주소에서 기관 이름. 모르면 도메인을 그대로 쓴다.

    **참고자료에는 기관명이 있어야 한다.** 문서 제목만 있으면 그것이 공식
    자료인지 민간 해설인지 구분되지 않는다.
    """
    if not url.startswith(("http://", "https://")):
        return ""
    host = url.split("//", 1)[1].split("/")[0].lower()
    host = host[4:] if host.startswith("www.") else host
    for k, v in ORGS.items():
        if host.endswith(k):
            return v
    # 모르는 곳은 도메인을 보인다 — 어디서 왔는지는 알 수 있다.
    return host


def _tidy(t: str) -> str:
    """참고자료 제목을 다듬는다.

    검색 결과 제목을 그대로 쓰면 **잘린 티가 난다.** 실제로 이렇게 나갔다.

        European Commission sets conditions and procedures for authorized ...
        DEHSt  -  CBAM Certificates

    말줄임표는 검색 엔진이 붙인 것이고, 겹친 공백은 사이트 구분자에서
    온다. 이 상태로 발행하면 **자동 생성 결과라는 인상**을 준다.

    잘린 뒤를 만들어 내지는 않는다 — 없는 제목을 지어내는 것이 더 나쁘다.
    말줄임표만 떼고 낱말 경계에서 끊는다.
    """
    import re
    t = " ".join((t or "").split())
    # 사이트 이름 구분자를 정리한다. " - " 나 " | " 로 통일한다.
    t = re.sub(r"\s*[|·]\s*", " | ", t)
    t = re.sub(r"\s+-\s+", " - ", t)
    # 검색 엔진이 붙인 말줄임표를 뗀다.
    t = re.sub(r"\s*(\.\.\.|…|\u2026)\s*$", "", t)
    # 낱말 가운데서 끊긴 것은 그 낱말째 버린다.
    if t.endswith(("-", ",", ":", "|")):
        t = t.rstrip(" -,:|")
    return t


def _pages_of(s_) -> list[str]:
    """이 출처에서 실제로 인용한 쪽.

    대조가 인용마다 `location` 을 남긴다. 올린 문서는 거기에 `[4쪽]` 이
    박혀 있으므로 그것만 모은다. 웹 원문은 절 제목이라 쪽이 아니다.
    """
    import re
    if not s_.get("file"):
        return []
    out = []
    for sp in s_.get("evidence_spans") or []:
        m = re.search(r"(\d+)\s*쪽", str(sp.get("location") or ""))
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return sorted(out, key=int)


def references(w) -> list[dict]:
    """참고자료 목록. 두 렌더러가 같은 것을 본다.

    **명제는 참고자료가 아니다.** 명제는 검증 단위고 참고자료에 실려야 하는
    것은 그것을 뒷받침한 **원문**이다. 명제 문장을 그대로 실으면 "우리가
    한 말" 이 출처로 나간다.

    같은 원문이 여러 명제를 뒷받침하는 일이 흔하다. URL 로 겹치는 것을
    걷어낸다 — 안 걷으면 같은 문서가 참고자료에 서너 번 뜬다.

    **본문이 실제로 인용한 것만 싣는다.** `sources` 는 프롬프트에 넘긴 목록이라
    안 쓴 것도 들어 있다. 그것까지 실으면 읽어 보지도 않은 자료가 참고자료로
    나가고, 그건 "출처가 있다" 를 흉내 내는 것이다.

    섹션마다 `cites` 에 쓴 id 가 남아 있고, 그 id 로 거른다.

    미확인 근거는 애초에 여기 안 온다. `write._split()` 이 갈라 두고,
    그것들은 발행 전 확인 목록으로 간다.
    """
    used = {c for sec in (w.get("sections") or []) if isinstance(sec, dict)
            for c in (sec.get("cites") or [])}

    seen, out = set(), []
    for s_ in w.get("sources") or []:
        if not isinstance(s_, dict):
            continue
        # 본문이 안 쓴 것은 참고자료가 아니다.
        if s_.get("id") and s_["id"] not in used:
            continue
        # 명제면 뒷받침한 원문의 제목을, 아니면 그 항목 제목을 쓴다.
        title = _tidy(s_.get("ref_title") or s_.get("title") or "")
        # 올린 문서는 **어느 쪽을 썼는지** 안다. 문서명만 적으면 읽는
        # 사람이 그 문서 어디를 보라는 것인지 알 수 없다.
        pages = _pages_of(s_)
        url = s_.get("url") or ""
        key = _same_doc(url, title)
        if not title or key in seen:
            continue
        seen.add(key)
        # **기관명을 앞에 둔다.** `official_primary` 같은 내부 이름을 그대로
        # 내보내면 사람에게 아무 뜻이 없다. 주소에서 기관을 뽑는다.
        row = {"title": title, "url": url,
               "source": _org(url) or s_.get("source_name", ""),
               "file": s_.get("file", "")}
        if pages:
            row["pages"] = pages[:6]
        out.append(row)
    return out


def media_of(d) -> dict:
    """섹션 번호 → 사람이 준비할 사진·캡처.

    구조 단계가 정해 둔 것이라 확정값에서 읽는다. 본문에는 없다 — 본문은
    글을 쓰는 일이고 이건 사람이 파일을 넣는 일이다.
    """
    secs = (d.get("outline", {}).get("payload") or {}).get("sections") or []
    return {i: s_["media"] for i, s_ in enumerate(secs, 1)
            if isinstance(s_, dict) and s_.get("media")}


def illustrations_of(d) -> dict:
    """섹션 번호 → 본문 그림 계획.

    도식(`image`)과 다르다. 도식은 정보를 구조로 보이고 코드가 마크업으로
    그리는데, 이건 상황을 보이고 생성 모델이 그린다. `media` 와도 다르다 —
    저건 회사가 가진 실제 파일이다.
    """
    secs = (d.get("outline", {}).get("payload") or {}).get("sections") or []
    return {i: s_["illustration"] for i, s_ in enumerate(secs, 1)
            if isinstance(s_, dict) and s_.get("illustration")}
