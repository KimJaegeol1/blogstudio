"""네이버 블로그 결과물.

스마트에디터에 텍스트로 붙는다. class·id 가 죽으므로 소제목을
`<p><strong>` 으로 세운다.

**도식은 자리표시만 둔다.** 태그가 살아남지 못하기 때문이다. 사진과 자료
화면도 자리표시로 둔다 — 그건 회사가 가진 파일이라 만들어 줄 수가 없다. 대신 사람이
홈페이지 쪽 마크업을 이미지로 저장해 그 자리에 넣는다 — 도식 데이터가 한
벌이라 두 채널이 어긋날 수가 없다. 캡처 폭과 글자 크기는
`data/channels.py` 의 `CAPTURE` 가 정한다.

메타 설명과 슬러그를 만들지 않는다(`meta_required: False`). 네이버가 알아서
만들고, 대신 태그가 검색 유입을 맡는다.

**홈페이지 렌더러를 import 하지 않는다.** 공유가 필요한 것은 `common.py` 에
있다. 한쪽이 다른 쪽을 부르면 네이버가 홈페이지의 파생물이 된다.
"""

from html import escape as _e

from .. import common as C, figures
from ...data import brand, channels, company

S = brand.NAVER

CH = "naver"



def build(d):
    """네이버는 제목·본문·태그 입력칸이 따로다. 그래서 셋으로 나눠 준다.

    본문은 서식 HTML 하나만 만든다. 텍스트 버전은 화면이 이걸 보고 만든다 —
    두 벌을 각각 만들면 한쪽만 고쳤을 때 서로 어긋난다.
    """
    tags = C.tags(d)
    return {"title": C.title(d), "html": _html(d), "figures": _figures(d),
            # **도식 스타일을 같이 보낸다.** 채널을 가르면서 figures.CSS 를
            # 싣는 곳이 홈페이지 렌더러 하나만 남았고, 네이버는 마크업만
            # 받았다. class 는 있는데 규칙이 없으니 브라우저 기본값으로
            # 그려지고, 그걸 캡처한 그림이 그대로 나갔다 — 상자도 선도
            # 색도 없는 글자 목록이었다.
            "figure_css": figures.CSS,
            "recipe": _recipe(d),
            "tags": tags, "tag_line": " ".join("#" + t for t in tags)}


def _recipe(d) -> list[dict]:
    """붙여넣은 뒤 에디터에서 손볼 것.

    **본문 데이터에 정렬·간격을 넣지 않는다.** 넣어 봐야 붙여넣기에서
    대부분 안 살아남고, 모델이 문단마다 정하면 장식이 과해진다. 대신
    본문 모양을 코드가 읽어서 **무엇을 어디서 손보면 되는지**만 적는다.

    이건 결과물이 아니라 안내다. 사람이 보고 판단한다.
    """
    w = C.body(d)
    secs = w.get("sections", [])
    out = []

    if w.get("lead"):
        out.append({"where": "도입", "what": "가운데 정렬 · 인용구",
                    "why": "첫 화면에서 눈이 멈추는 자리다"})
    if secs:
        out.append({"where": "소제목", "what": "본문보다 한 단계 큰 크기 · 굵게",
                    "why": f"{len(secs)}개. 스크롤로 읽으므로 구간이 보여야 한다"})
        out.append({"where": "섹션 사이", "what": "빈 줄 하나 또는 구분선",
                    "why": "화면이 좁아 문단이 붙어 보인다"})

    n_fig = sum(1 for s_ in secs for b in C.blocks(s_) if b.get("type") == "figure")
    if n_fig:
        out.append({"where": "도식 자리", "what": "이미지 넣고 가운데 정렬",
                    "why": f"[도식 N 삽입] {n_fig}곳"})
    n_call = sum(1 for s_ in secs for b in C.blocks(s_) if b.get("type") == "callout")
    if n_call:
        out.append({"where": "강조 문단", "what": "인용구 서식",
                    "why": f"{n_call}곳. 굵게만 하면 본문과 안 갈린다"})
    if C.media_of(d):
        out.append({"where": "사진·자료 화면", "what": "파일 넣고 설명 한 줄",
                    "why": "회사가 가진 파일이라 자동으로 안 들어간다"})

    out.append({"where": "마지막", "what": "태그 붙이고 대표 이미지 지정",
                "why": "대표 이미지는 목록과 검색에 나간다"})
    return out


def _figures(d) -> list[dict]:
    """본문에 자리표시로 빠진 도식을 마크업으로 따로 낸다.

    **에디터가 못 받는 것이지 그릴 수 없는 것이 아니다.** 본문에는
    `[도식 N 삽입]` 만 두고, 사람이 이미지로 저장해 그 자리에 넣는다.
    저장할 원본이 여기다.

    예전에는 홈페이지 결과물에서 캡처했다. 채널이 갈리면서 네이버 드래프트에
    홈페이지 결과물이 없으므로, 같은 `figures.py` 로 여기서 그린다 — 도식
    데이터는 여전히 한 벌이라 두 채널이 어긋날 수가 없다.

    `n` 은 본문 자리표시의 번호와 같다. 다르면 사람이 어느 그림을 어디에
    넣을지 알 수 없다.
    """
    out, n = [], 0
    for sec in C.body(d).get("sections", []):
        for b in C.blocks(sec):
            if b.get("type") != "figure":
                continue
            n += 1
            fig = {k: b[k] for k in ("component", "caption", "data") if k in b}
            html = figures.html(fig) if fig.get("component") else ""
            if not html:
                continue
            out.append({"n": n, "caption": b.get("caption") or f"도식 {n}",
                        "takeaway": b.get("takeaway", ""), "html": html})
    return out


def _block(h, b, n):
    """블록 하나를 에디터가 받는 태그로. 도식만 자리표시로 빠진다."""
    t = b["type"]

    if t == "para":
        if b.get("text"):
            h.append(f'<p style="{S["para"]}">{_e(b["text"])}</p>')

    elif t == "list":
        rows = [x for x in (b.get("items") or []) if isinstance(x, dict)]
        if rows:
            h.append(f'<ol style="{S["list"]}">')
            for x in rows:
                # 제목과 설명을 <br> 로 끊는다. 공백 하나로 두면 에디터가
                # 인라인으로 이어 붙여 "제품 단위 식별 제품 또는…" 처럼 붙는다.
                title = (f'<strong style="{S["item_title"]}">{_e(x["title"])}</strong><br>'
                     if x.get("title") else "")
                h.append(f'<li style="{S["item"]}">{title}{_e(x.get("body", ""))}</li>')
            h.append("</ol>")

    elif t == "check":
        items = C.items(b)
        if items:
            # <ul> 을 쓰지 않는다. 에디터가 자기 목록 컴포넌트로 바꾸면
            # 글머리 기호와 □ 가 겹쳐 "• □ 문항" 이 된다. 문단으로 두면
            # □ 가 그대로 남는다.
            for x in items:
                h.append(f'<p style="{S["para"]}">□ {_e(x)}</p>')

    elif t == "callout":
        if b.get("text"):
            label = (f'<p style="{S["callout_label"]}">{_e(b["label"])}</p>'
                     if b.get("label") else "")
            h.append(f'<blockquote style="{S["callout"]}">{label}'
                     f'<p style="{S["callout_body"]}">{_e(b["text"])}</p>'
                     f'</blockquote>')

    elif t == "figure":
        # 표·도식은 에디터에서 살아남지 못한다. 홈페이지 탭에서 그림으로
        # 저장한 파일을 여기 넣는다. 번호를 붙여 어느 파일인지 헷갈리지
        # 않게 한다 — 파일 이름도 같은 번호를 쓴다.
        n += 1
        # 작업 지시를 결과물에 섞지 않는다. 복사해서 붙이면 그대로 따라간다.
        # 어느 파일을 넣는지는 화면에서 안내한다.
        cap = b.get("caption") or b.get("component") or "도식"
        # **구분선으로 감싸지 않는다.** 그림을 넣고 나서도 위아래 줄이
        # 그대로 남아 이유 없는 선이 붙는다. 옅은 점선 상자 하나로 둔다 —
        # 그림으로 바꾸면 상자째 사라진다.
        h.append(f'<p style="{S["slot"]}">'
                 f'<strong style="{S["slot_label"]}">[도식 {n} 삽입]</strong><br>'
                 f'{_e(cap)}</p>')
        # 해석 문장은 그림이 아니라 글이다. 캡처에 딸려 들어가면 네이버 본문에
        # 남지 않고 검색에도 안 걸린다.
        if b.get("takeaway"):
            h.append(f'<p style="{S["para"]}">{_e(b["takeaway"])}</p>')

    return n


def _html(d):
    """서식 붙여넣기용. 네이버 에디터가 안전하게 받는 태그만 쓴다.

    class·id·section·article 은 쓰지 않는다. 에디터가 자기 마크업으로 다시
    감싸면서 버리거나 엉뚱한 스타일을 끼워 넣는다. 소제목도 <h2> 대신
    <p><strong> 으로 둔다.
    """
    w = C.body(d)
    h = []

    # **파일 이름을 본문에 쓰지 않는다.** `f9d0c23fea...png` 는 사람에게
    # 아무 뜻이 없고, 붙여넣을 글에 남으면 지워야 할 것이 하나 더 생긴다.
    # 어느 파일인지는 결과물 화면이 알려 준다.
    hero = C.hero_plan(d).get("purpose") or "글 전체를 상징하는 이미지"
    h.append(f'<p style="{S["slot"]}">'
             f'<strong style="{S["slot_label"]}">[대표 이미지 삽입]</strong><br>'
             f'{_e(hero)}</p>')

    # 리드는 본문 진입부다. **박스로 감싸지 않는다** — 감싸면 안내·요약처럼
    # 보여서 본문이 아직 시작 안 한 것으로 읽힌다. 글자만 한 칸 키운다.
    if w.get("lead"):
        h.append(f'<p style="{S["lead"]}">{_e(w["lead"])}</p>')

    media = C.media_of(d)
    illus = C.illustrations_of(d)
    n = 0
    for s in w.get("sections", []):
        # **위 여백이 본문 사이 여백보다 커야 섹션이 갈려 보인다.** 예전에는
        # 둘 다 14px 이라 스크롤할 때 어디서 시작하는지 안 보였다.
        h.append(f'<p style="{S["heading"]}">'
                 f'<strong>{_e(s["heading"])}</strong></p>')
        for b in C.blocks(s):
            n = _block(h, b, n)
        # 사람이 넣을 사진·자료 화면. 도식 자리표시와 같은 방식이다 —
        # 만들어 주는 것이 아니라 어디에 무엇이 필요한지 알려 준다.
        # 줄글만 이어지는 구간을 쉬어 가게 하는 그림. 아직 만들어 주지
        # 않으므로 자리표시로 둔다.
        il = illus.get(s.get("order"))
        if il:
            h.append(f'<p style="{S["slot"]}">'
                     f'<strong style="{S["slot_label"]}">[본문 그림 삽입]</strong><br>'
                     f'{_e(il["purpose"])}</p>')

        m = media.get(s.get("order"))
        if m:
            h.append(f'<p style="{S["slot"]}">'
                     f'<strong style="{S["slot_label"]}">'
                     f'[{channels.label(CH, m["type"])} 삽입]</strong><br>'
                     f'{_e(m["purpose"])}</p>')

    src = C.references(w)
    if src:
        h.append(f'<p style="{S["heading"]}"><strong>참고한 자료</strong></p>')
        h.append(f'<ul style="{S["list"]}">')
        for s in src:
            # 올린 문서는 링크가 없다. 무엇을 보고 썼는지만 남긴다.
            sub = f' ({_e(s["source"])})' if s.get("source") else ''
            # **어느 쪽을 봤는지 적는다.** 문서명만 있으면 읽는 사람이
            # 그 문서 어디를 보라는 것인지 알 수 없다.
            tail = ' — 첨부 문서' if s.get("file") and not s.get("url") else ''
            if s.get("pages"):
                tail += f' {"·".join(s["pages"])}쪽' 
            h.append(f'<li style="{S["item"]}">{_e(s["title"])}{sub}{tail}</li>')
        h.append('</ul>')

    _cta(h, d)
    return "\n".join(h)


def _cta(h, d) -> None:
    """글 끝의 안내. **서비스를 모르면 구분선만 둔다.**

    네이버는 링크를 눌러 나가는 곳이 아니라 글을 읽는 곳이라, 홈페이지보다
    한 칸 약하게 둔다(`cta_strength: soft`). 버튼 모양을 만들지 않고
    한 줄로 적는다 — 광고처럼 보이면 검색해서 들어온 사람이 나간다.
    """
    sid = (d.get("topic", {}).get("payload") or {}).get("service_id", "")
    row = company.cta(channels.of(CH).cta_strength, company.service(sid))
    # **서비스를 모르면 아무것도 안 나간다.** 구분선도 안 나간다 — 글이
    # 선 하나로 끝나면 그건 마무리가 아니라 잘린 것으로 보인다.
    if not row:
        return
    h.append(f'<p style="{S["rule"]}">─────────────</p>')
    tail = f'<br>{_e(row["url"])}' if row["url"].startswith(("http://", "https://")) else ""
    h.append(f'<p style="{S["cta"]}">{_e(row["lead"])}<br>'
             f'<strong style="{S["cta_action"]}">{_e(row["action"])}</strong>{tail}</p>')


