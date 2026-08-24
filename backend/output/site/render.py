"""회사 홈페이지 결과물.

HTML 그대로 붙는다. 도식이 마크업 그대로 들어가고 스타일이 맨 위에 한 번
실린다.

네이버와 다른 것은 셋이다.

    메타       description · slug 를 낸다 (`meta_required: True`)
    신뢰 요소   작성자·검토자·기준일. **값이 없으면 영역째 뺀다**
    서비스 연결  소재에 붙은 service_id 로 회사 서비스를 잇는다

**신뢰 요소를 지어내지 않는다.** 작성자 이름이 없으면 "환경 전문가" 같은
문구로 메우지 않고 그 줄을 통째로 뺀다. 신뢰 요소는 지어내는 순간 정반대로
작동한다. `data/company.py` 가 비어 있으면 지금이 그 상태다.

**네이버 렌더러를 import 하지 않는다.** 공유가 필요한 것은 `common.py` 에 있다.
"""

from datetime import date
from html import escape as _e

from .. import common as C, figures
from ...data import brand, channels, company

CH = "site"


# ── 본문 요소 스타일 ──────────────────────────────────────────
#
# 본문 요소 스타일. 도식은 figures.CSS 가 맡고 여기는 목록·체크리스트·
# 강조 박스만 본다. 최소한만 건다 — h1·h2·p 는 회사 사이트 스타일을 따르는
# 편이 자연스럽고, 여기서 덮으면 오히려 페이지와 어긋난다.

BODY_CSS = """\
.post-list{padding-left:22px;margin:20px 0;color:#374151;line-height:1.7}
.post-list li{margin:12px 0}
.post-list strong{color:#111827;font-weight:600;letter-spacing:-0.02em}
.post-check{list-style:none;padding:0;margin:20px 0;color:#374151;line-height:1.7}
.post-check li{margin:8px 0;text-indent:-22px;padding-left:22px}
.post-callout{margin:24px 0;padding:16px 20px;border-left:3px solid var(--bs-accent);
 background:var(--bs-accent-bg);color:var(--bs-text);line-height:1.7}
.post-callout.warn{border-left-color:#C2761B;background:var(--bs-surface)}
.post-callout.warn strong{color:#C2761B}
.post-callout.def{border:1px solid var(--bs-primary);border-left-width:1px;
 background:var(--bs-background)}
.post-callout.def strong{color:var(--bs-primary)}
.post-callout strong{display:block;margin-bottom:6px;font-size:14px;
 font-weight:600;color:var(--bs-accent);letter-spacing:0.02em}
.post-callout p{margin:0}
.post-takeaway{margin:-20px 0 32px;color:#4B5563;font-size:15px;line-height:1.7}
.post-hero{display:block;width:100%;height:auto;border-radius:var(--bs-radius);margin:0 0 28px}
.post-trust{margin:-8px 0 22px;font-size:13px;color:var(--bs-text-muted)}
.post-sum{margin:24px 0;padding:18px 22px;background:var(--bs-surface);
 border:1px solid var(--bs-border);border-radius:var(--bs-radius)}
.post-sum strong{display:block;margin-bottom:8px;font-size:13px;
 font-weight:600;color:var(--bs-accent);letter-spacing:0.02em}
.post-sum ul{margin:0;padding-left:20px;color:var(--bs-text);line-height:1.7}
.post-svc{margin:36px 0 0;padding-top:24px;border-top:1px solid var(--bs-border)}
.post-svc h2{font-size:16px;margin:0 0 8px}
.post-svc-s{margin:4px 0 0;color:var(--bs-text-muted);font-size:14px}
.post-cta{margin:28px 0 0;padding:20px 22px;background:var(--bs-accent-bg);
 border:1px solid var(--bs-border);border-radius:var(--bs-radius)}
.post-cta p{margin:0;color:var(--bs-text);line-height:1.7}
.post-cta-b{margin-top:12px !important}
.post-cta-a{display:inline-block;padding:10px 18px;border-radius:var(--bs-radius);
 background:var(--bs-accent);color:#fff;text-decoration:none;font-weight:600}
"""

# 강조 박스 종류 → 클래스. 회사 가이드가 핵심·주의·정의를 다르게 그린다.
KIND = {"주의": "warn", "정의": "def"}


def _block(h, b):
    """블록 하나를 홈페이지 마크업으로.

    도식만 figures.py 가 그리고 나머지는 평범한 태그다. CSS 가 CMS 에서
    걸러져도 목록은 목록으로, 인용은 인용으로 읽힌다.
    """
    t = b["type"]

    if t == "para":
        if b.get("text"):
            h.append(f'  <p>{_e(b["text"])}</p>')

    elif t == "list":
        rows = [x for x in (b.get("items") or []) if isinstance(x, dict)]
        if rows:
            h.append('  <ol class="post-list">')
            for x in rows:
                inner = (f'<strong>{_e(x["title"])}</strong><br>' if x.get("title") else "")
                inner += _e(x.get("body", ""))
                h.append(f'    <li>{inner}</li>')
            h.append('  </ol>')

    elif t == "check":
        items = C.items(b)
        if items:
            h.append('  <ul class="post-check">')
            for x in items:
                # □ 를 글자로 넣는다. CSS ::before 로 그리면 CMS 가 style 을
                # 걸러낼 때 사라지고, 캡처한 그림에도 안 남는다.
                h.append(f'    <li>□ {_e(x)}</li>')
            h.append('  </ul>')

    elif t == "callout":
        if b.get("text"):
            label = b.get("label", "")
            lab = f'<strong>{_e(label)}</strong>' if label else ""
            # 종류마다 모양이 다르다. 다 같은 파란 박스면 셋을 가른 뜻이 없다.
            cls = "post-callout" + (f" {KIND[label]}" if label in KIND else "")
            h.append(f'  <blockquote class="{cls}">{lab}'
                     f'<p>{_e(b["text"])}</p></blockquote>')

    elif t == "figure":
        fig = {k: b[k] for k in ("component", "caption", "data") if k in b}
        drawn = figures.html(fig) if fig.get("component") else ""
        if drawn:
            h.append('  ' + drawn)
        # 해석 문장은 <figure> 밖에 둔다. 안에 두면 캡처할 때 그림에 딸려
        # 들어가 네이버 본문에 텍스트로 남지 않는다.
        if b.get("takeaway"):
            h.append(f'  <p class="post-takeaway">{_e(b["takeaway"])}</p>')


def build(d):
    w = C.body(d)
    title = C.title(d)
    lead = w.get("lead", "")
    reader = d.get("reader", {}).get("payload", {})
    atype = d.get("type", {}).get("payload", {}).get("article_type", "")
    desc = lead[:80]

    # 메타는 주석으로 맨 위에 붙인다. 통째로 붙여넣어도 렌더되지 않고,
    # CMS 에 제목·설명 입력칸이 따로 있으면 눈으로 보고 옮기면 된다.
    pay = d.get("title", {}).get("payload", {})
    desc = pay.get("meta_description") or desc
    slug = pay.get("slug") or "영문 슬러그는 아직 없습니다"

    h = ['<!--',
         f'  title: {title}',
         f'  description: {desc}',
         f'  url_slug: {slug}',
         '-->',
         '<style>',
         brand.css_vars(),
         brand.with_fallback(BODY_CSS).rstrip(),
         figures.CSS.rstrip(),
         '</style>',
         '<article class="post">']

    made = C.hero_made(d)
    hero = C.hero_plan(d).get("purpose")
    if made.get("file"):
        alt = made.get("alt") or hero
        h.append(f'  <img class="post-hero" src="{_e(made["file"])}" '
                 f'alt="{_e(alt)}">')
    elif hero:
        h.append(f'  <!-- HERO_SLOT — {hero} -->')

    h.append(f'  <h1>{_e(title)}</h1>')
    _trust(h)
    if lead:
        h.append(f'  <p class="lead">{_e(lead)}</p>')
    _summary(h, w)

    for s in w.get("sections", []):
        h.append(f'  <h2>{_e(s["heading"])}</h2>')
        for b in C.blocks(s):
            _block(h, b)

    src = C.references(w)
    if src:
        h.append('  <section class="references">')
        h.append('    <h2>참고한 자료</h2>')
        h.append('    <ul>')
        for s in src:
            label = _e(s["title"])
            url = s.get("url") or ""
            inner = (f'<a href="{_e(url)}" target="_blank" rel="noopener">{label}</a>'
                     if url.startswith(("http://", "https://")) else label)
            sub = f' <span>{_e(s["source"])}</span>' if s.get("source") else ''
            # 올린 문서는 링크가 없다. 사람이 CMS 에서 채우거나 그대로 둔다.
            tail = ' <span>첨부 문서</span>' if s.get("file") and not url else ''
            # **어느 쪽을 봤는지 적는다.** 문서명만 있으면 읽는 사람이 그
            # 문서 어디를 보라는 것인지 알 수 없다.
            if s.get("pages"):
                tail += f' <span>{"·".join(s["pages"])}쪽</span>'
            h.append(f'      <li>{inner}{sub}{tail}</li>')
        h.append('    </ul>')
        h.append('  </section>')

    _service(h, d)
    _cta(h, d)

    h.append('</article>')

    return {"html": "\n".join(h), "meta_description": desc, "slug": slug,
            "meta_note": f"{atype} · {reader.get('role', '')} 대상"}


# ── 신뢰 요소 ─────────────────────────────────────────────────
#
# **값이 없으면 영역째 뺀다.** 이름을 지어내거나 "환경 전문가" 같은 문구로
# 메우면 신뢰 요소가 정반대로 작동한다. data/company.py 가 비어 있는 지금은
# 아무것도 안 나가고, 발행 전 확인 목록이 그 사실을 알려 준다.

def _who(p) -> str:
    return " ".join(x for x in [p.get("name", ""), p.get("role", "")] if x)


def _trust(h) -> None:
    a, r = company.author(), company.reviewer()
    rows = []
    if a:
        rows.append(f'<span class="post-by">{_e(_who(a))}</span>')
    if r:
        rows.append(f'<span class="post-rv">검토 {_e(_who(r))}</span>')
    # 날짜는 사람이 없어도 뜻이 있다. 규제 정보는 언제 기준인지가 내용이다.
    rows.append(f'<time datetime="{date.today()}">{date.today()} 기준</time>')
    h.append('  <div class="post-trust">' + " · ".join(rows) + "</div>")


def _summary(h, w) -> None:
    """핵심 요약. 본문 작성이 냈을 때만 나간다 — 없으면 자리도 없다."""
    rows = [x for x in (w.get("summary") or []) if isinstance(x, str) and x.strip()]
    if not rows:
        return
    h.append('  <aside class="post-sum">')
    h.append('    <strong>핵심 요약</strong>')
    h.append('    <ul>')
    for x in rows[:4]:
        h.append(f'      <li>{_e(x)}</li>')
    h.append('    </ul>')
    h.append('  </aside>')


def _cta(h, d) -> None:
    """글 끝의 안내. **서비스를 모르면 안 나간다.**

    예전에는 `<!-- CTA_SLOT -->` 주석 한 줄이었다. 자리만 있고 아무것도 안
    들어가서, 글이 "그래서 뭘 하면 되나" 없이 끝났다 — `cta_strength` 를
    채널마다 정해 두고 아무도 안 읽던 자리다.

    문구는 `data/company.py` 가 든다. 모델이 만들면 글마다 다른 회사처럼
    보이고, 없는 서비스를 권하게 된다.
    """
    sid = (d.get("topic", {}).get("payload") or {}).get("service_id", "")
    row = company.cta(channels.of(CH).cta_strength, company.service(sid))
    if not row:
        return
    url = row["url"]
    act = _e(row["action"])
    btn = (f'<a class="post-cta-a" href="{_e(url)}">{act}</a>'
           if url.startswith(("http://", "https://")) else f'<strong>{act}</strong>')
    h.append('')
    h.append('  <aside class="post-cta">')
    h.append(f'    <p>{_e(row["lead"])}</p>')
    h.append(f'    <p class="post-cta-b">{btn}</p>')
    h.append('  </aside>')


def _service(h, d) -> None:
    """관련 서비스. 소재에 붙은 service_id 로 찾는다.

    **모델이 만들지 않는다.** 서비스 이름을 지어내면 없는 상품을 파는 글이
    된다. data/company.py 의 SERVICES 에 없으면 아무것도 안 나간다.
    """
    sid = (d.get("topic", {}).get("payload") or {}).get("service_id", "")
    svc = company.service(sid)
    if not svc:
        return
    url = svc.get("url") or ""
    label = _e(svc.get("name", ""))
    inner = (f'<a href="{_e(url)}">{label}</a>'
             if url.startswith(("http://", "https://")) else label)
    h.append('  <section class="post-svc">')
    h.append('    <h2>이 글과 관련된 서비스</h2>')
    h.append(f'    <p>{inner}</p>')
    if svc.get("summary"):
        h.append(f'    <p class="post-svc-s">{_e(svc["summary"])}</p>')
    h.append('  </section>')


