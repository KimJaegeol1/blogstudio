"""본문 도식.

글자가 뜻을 지고 있는 도식은 생성하지 않고 마크업으로 그린다. 회사 가이드의
forms 18개가 전부 한글 글자가 곧 내용인 도식이고, 생성 모델은 그 글자를
제대로 못 쓴다. 더 나쁜 것은 틀린 수치가 그림 안에 박히면 아무도 교정하지
못한다는 점이다.

18개를 묶으면 넷이다. 목록 밖의 form 은 받지 않는다 — 조용히 매칭이
실패하는 것보다 도식 없이 나가는 편이 낫다.

    순서열    시간·단계 순서가 있는 것
    대조표    같은 기준으로 둘 이상을 나란히 놓는 것
    항목카드  나열되는 항목
    구조도    포함·계층 관계

여기는 아무것도 import 하지 않는다. payload.py 와 같은 이유다 — 결과물
조립이 LLM 을 호출하는 모듈에 의존하면 방향이 거꾸로다.

빌더는 LLM 출력을 그대로 믿지 않는다. 못 쓸 모양이면 None 을 준다.
그 도식 하나만 빠지고 본문은 그대로 나간다. 도식 하나 때문에 글이 막히면 안 된다.

클래스 이름에 fig- 를 붙인다. 이 HTML 은 회사 사이트에 붙는데, .card 나
.step 같은 이름은 그쪽 CSS 와 부딪힌다.

**색과 곡률은 여기서 정하지 않는다.** data/brand.py 가 정하고 여기는
CSS 변수로 받는다. 값을 박아 두면 같은 색이 figures·render·프론트 세 군데에
흩어지고, 한 곳만 고쳤을 때 그 어긋남은 조용히 지나간다.

변수만 쓰면 캡처에서 깨진다 — 도식을 이미지로 저장할 때 `.post` 밖에 복제해
찍으므로 변수 선언이 안 잡힌다. 그래서 기본값을 함께 싣는다. 값은 brand 에
한 벌만 있고 여기서 문자열을 만들 때 끼운다.

brand 는 아무것도 import 하지 않는 잎이라 방향이 거꾸로 되지 않는다.
"""

import re

from html import escape

from ..data import brand

# ── form → 컴포넌트 ───────────────────────────────────────────
#
# 프롬프트는 컴포넌트 이름 넷 중 하나를 직접 고르는 것이 원칙이다.
# 아래 표는 그 이전 형태(유형별 forms 이름)를 받아 주는 흡수 계층이다.
#
# 실제 실행 로그에서 동향형 forms 에 없는 "흐름도" 가 나왔다. 프롬프트가
# "목록에 맞는 것이 없으면 다른 형식을 써도 된다"고 열어 둔 탓인데, 열어 둔
# 것 자체보다 유형별로 forms 를 묶어 둔 게 문제였다 — 도식은 섹션 단위
# 판단인데 선택지를 글 전체 유형으로 제한하고 있었다. 동향형 글에도
# 데이터 흐름을 보여줘야 하는 섹션은 나온다.
#
# 그래서 흡수하고, 프롬프트는 컴포넌트 넷에서 직접 고르게 바꾼다.

# 별칭은 "이 form 은 사실 이 컴포넌트다" 를 옮기는 것이다. 뜻이 다른 것을
# 억지로 이어 붙이면 프롬프트가 체크리스트를 요청해도 카드가 나온다.
# 체크리스트·번호형 목록·강조 박스는 도식이 아니라 본문 요소로 그린다 —
# 네이버 에디터가 ul·ol·blockquote 를 그대로 받으므로 캡처할 필요가 없다.
ALIAS = {
    # 순서열
    "타임라인": "순서열",
    "단계별 프로세스": "순서열",
    "순서도": "순서열",
    "작업 흐름도": "순서열",
    "프로세스 흐름도": "순서열",
    "Before-Process-After": "순서열",
    # 대조표
    "전후 비교 도식": "대조표",
    "양쪽 비교 도식": "대조표",
    "비교표": "대조표",
    "선택 기준 매트릭스": "대조표",
    # 항목카드
    "성과 요약": "항목카드",
    "상태 구분 도식": "항목카드",
    # 구조도
    "개념도": "구조도",
    "구조도": "구조도",
    "용어 관계도": "구조도",
    # forms 목록 밖이지만 실제로 나온 것들
    "흐름도": "순서열",
    "데이터 흐름도": "순서열",
    "플로우차트": "순서열",
    "비교 도식": "대조표",
}

NAMES = ("순서열", "대조표", "항목카드", "구조도")


def component_of(form):
    """컴포넌트 이름이면 그대로, 옛 form 이름이면 흡수해서. 모르면 None."""
    f = (form or "").strip()
    return f if f in NAMES else ALIAS.get(f)


# ── 다듬기 ────────────────────────────────────────────────────

def _s(v, n=200):
    if v is None:
        return ""
    return str(v).strip()[:n]


def _list(v):
    return v if isinstance(v, list) else []


# ── 빌더 ──────────────────────────────────────────────────────
#
# 각 컴포넌트가 무엇을 필요로 하는지가 여기 한 곳에만 있다.
# 최소 개수를 두는 이유는 한 칸짜리 순서열이나 카드 한 장은 도식이 아니기
# 때문이다. 그럴 바에는 본문 문장으로 두는 게 낫다.

def _steps(d):
    """순서열. [{label, body}] — 2~7개."""
    out = []
    for x in _list(d.get("steps")):
        if not isinstance(x, dict):
            continue
        label, body = _s(x.get("label"), 40), _s(x.get("body"), 300)
        if label or body:
            out.append({"label": label, "body": body})
    return {"steps": out[:7]} if len(out) >= 2 else None


MAX_COLS = 4

# 행끼리 이만큼 겹치면 같은 것을 말하는 것으로 본다.
SAME_ROW = 0.5

# 행동을 가리키는 말. 한 칸은 이름이고 한 칸은 행동이면 축이 어긋난다.
_ACT = re.compile(r"(확인|점검|판단|검토|수행|제출|신청|준비)")


def _compare(d):
    """대조표. 첫 칸은 기준 이름이고 나머지가 비교 대상이다.

    **모델이 `columns` 를 두 가지 모양으로 보낸다.**

        A. 비교 대상만        columns=[스코프1,스코프2,스코프3]  cells 3개
        B. 기준 이름까지      columns=[판단 결과,중요도,조건,기록]  cells 3개

    A 에서 columns[0] 을 기준 이름으로 쓰면 **스코프1 자료가 통째로
    사라지고 나머지가 한 칸씩 밀린다.** B 에서 안 쓰면 이름이 하나
    남아돌아 표가 밀린다. 실제로 둘 다 겪었다.

    **칸 수로 가른다.** 이건 모양을 물어보는 것이 아니라 세는 것이라
    확실하다.

        cells == columns        A. 기준 열 이름이 없다 → "구분"
        cells == columns - 1    B. columns[0] 이 기준 열 이름

    칸 수가 들쭉날쭉하면 가장 많이 나온 수를 따른다. 모자라면 채우고
    넘치면 자른다 — 어긋난 채로 렌더하면 엉뚱한 값이 엉뚱한 열에 붙는다.
    """
    cols = [_s(c, 40) for c in _list(d.get("columns")) if _s(c)]
    if len(cols) < 2:
        return None

    raw = []
    for r in _list(d.get("rows")):
        if not isinstance(r, dict):
            continue
        crit = _s(r.get("criterion"), 60)
        cells = [_s(c, 200) for c in _list(r.get("cells"))]
        if crit or any(cells):
            raw.append((crit, cells))
    if not raw:
        return None

    # 행마다 칸 수가 다를 수 있다. 가장 흔한 수를 기준으로 본다.
    counts = {}
    for _, cells in raw:
        counts[len(cells)] = counts.get(len(cells), 0) + 1
    typical = max(counts, key=lambda k: (counts[k], k))

    if typical == len(cols) - 1:
        head, rest = cols[0], cols[1:]          # B
    else:
        head, rest = "구분", cols               # A

    rest = rest[:MAX_COLS - 1]
    rows = []
    for crit, cells in raw[:8]:
        cells = cells[:len(rest)]
        cells += [""] * (len(rest) - len(cells))
        rows.append({"criterion": crit, "cells": cells})

    return {"head": head, "columns": rest, "rows": rows}


def _cards(d):
    """항목카드. [{title, body}] — 2~6개."""
    out = []
    for x in _list(d.get("cards")):
        if not isinstance(x, dict):
            continue
        title, body = _s(x.get("title"), 60), _s(x.get("body"), 300)
        if title or body:
            out.append({"title": title, "body": body})
    return {"cards": out[:6]} if len(out) >= 2 else None


DEPTH = 3

# 루트 이름 길이. 기준이 되는 대상 하나라 길 이유가 없다.
ROOT_MAX = 20


def _node(x, depth):
    """구조도 마디 하나. 깊이를 넘으면 자른다.

    임의의 노드-링크 그래프가 아니라 포함·계층 관계만 다룬다. 깊이를 안 막으면
    LLM 이 계속 파고들어 화면에서 읽을 수 없는 상자가 된다.
    """
    if not isinstance(x, dict) or depth > DEPTH:
        return None
    label = _s(x.get("label"), 60)
    if not label:
        return None
    kids = []
    if depth < DEPTH:
        for k in _list(x.get("children")):
            n = _node(k, depth + 1)
            if n:
                kids.append(n)
    return {"label": label, "children": kids[:5]}


def _tree(d):
    """구조도. {root: {label, children[]}}

    루트는 **기준이 되는 대상 하나**다. 도식 제목이 아니다 — 모델이
    "보고기업 기준 가치사슬" 같은 제목을 넣으면 "그 아래에 업스트림이
    있다" 가 되어 같은 것을 두 번 말하게 된다. 그건 `caption` 이 맡는다.

    제목인지 대상인지는 코드가 확실히 못 가른다. 프롬프트가 막고, 여기서는
    **너무 긴 루트만** 자른다 — 이름 하나가 그렇게 길 이유가 없다.
    """
    root = _node(d.get("root"), 1)
    if not root or not root["children"]:
        return None
    if len(root["label"]) > ROOT_MAX:
        root["label"] = root["label"][:ROOT_MAX].rstrip()
    return {"root": root}


BUILD = {"순서열": _steps, "대조표": _compare, "항목카드": _cards, "구조도": _tree}


def flaws(component, data) -> list[str]:
    """도식이 관계를 왜곡하는가.

    **틀린 정보를 그림으로 확정하는 것**이 글로 쓰는 것보다 나쁘다. 글은
    고칠 수 있지만 그림은 캡처해서 나가면 못 고친다.

    실제로 이렇게 났다.

        신고 의무
        ├─ 수입자              ← 신고 의무 주체가 맞다
        └─ 수출 제조기업        ← 자료를 대는 쪽인데 같은 자리에 있다

    **부모가 자식을 다 포괄하는지**를 본다. 모양은 이미 맞춰 놨고, 여기서
    보는 것은 뜻이다. 확실히 못 가르는 것은 지우지 않고 표시만 한다.
    """
    fn = FLAW.get(component_of(component) or "")
    return fn(data) if fn and isinstance(data, dict) else []


def _tree_flaws(d) -> list[str]:
    """구조도. 부모·자식 관계와 계층이 맞는가."""
    root = (d.get("root") or {})
    kids = root.get("children") or []
    out = []
    if len(kids) < 2:
        out.append("갈래가 하나뿐이라 나누는 그림이 아닙니다")

    # 자식이 부모와 같은 말이면 계층이 아니다.
    top = _key(root.get("label"))
    same = [k["label"] for k in kids if _key(k.get("label")) == top]
    if same:
        out.append(f'같은 이름이 위아래에 있습니다 — {same[0]}')

    # **깊이가 들쭉날쭉하면 같은 계층이 아니다.** 하나는 손자까지 있고
    # 하나는 잎도 없으면, 나란히 놓인 것처럼 보여도 다른 층이다.
    depth = [len(k.get("children") or []) for k in kids]
    if len(depth) >= 2 and min(depth) == 0 and max(depth) >= 2:
        out.append("갈래마다 깊이가 달라 같은 층으로 안 읽힙니다")
    return out


def _compare_flaws(d) -> list[str]:
    """대조표. 모든 열이 같은 기준으로 견주는가."""
    from .. import sanitize as z
    out = []
    rows = d.get("rows") or []
    if len(rows) < 2:
        out.append("견줄 기준이 하나뿐이라 표가 아닙니다")

    # 행끼리 같은 말을 하는지는 **코드가 못 가른다.** 실제로 이랬다.
    #
    #     신고 주기   분기별 보고     연간 신고
    #     일정 관리   분기 단위 마감   연간 단위 마감
    #
    # 둘 다 "분기와 연간의 차이" 인데, 낱말 겹침으로는 정상인 표
    # ("보고 신고자" vs "분기별 보고") 가 더 높게 나온다. 프롬프트가 막는다.

    # **한 행 안에서 비교 축이 어긋나는가.** 왼쪽은 주체인데 오른쪽은
    # 행동이면 나란히 놓아도 견준 것이 아니다.
    for r in rows:
        cells = [c for c in (r.get("cells") or []) if c.strip()]
        if len(cells) < 2:
            continue
        acts = [bool(_ACT.search(c)) for c in cells]
        if any(acts) and not all(acts):
            out.append(f'"{r.get("criterion", "")}" 행의 칸이 같은 축이 아닙니다')
    # 한 열이 통째로 비면 그 대상은 견준 것이 아니다.
    cols = d.get("columns") or []
    for i, name in enumerate(cols):
        if rows and all(not (r.get("cells") or [""] * len(cols))[i:i + 1][0]
                        for r in rows):
            out.append(f'"{name}" 열이 비어 있습니다')
    return out


def _steps_flaws(d) -> list[str]:
    """순서열. 실제로 순서가 있는가."""
    steps = d.get("steps") or []
    return ["단계가 하나뿐이라 순서가 아닙니다"] if len(steps) < 2 else []


def _cards_flaws(d) -> list[str]:
    """항목카드. 항목이 서로 독립인가."""
    cards = d.get("cards") or []
    seen, dup = set(), []
    for c in cards:
        k = _key(c.get("title"))
        if k and k in seen:
            dup.append(c.get("title"))
        seen.add(k)
    return [f'같은 항목이 두 번 있습니다 — {dup[0]}'] if dup else []


def _key(t: str) -> str:
    return "".join((t or "").split()).lower()


FLAW = {"순서열": _steps_flaws, "대조표": _compare_flaws,
        "항목카드": _cards_flaws, "구조도": _tree_flaws}


def figure(component, caption, data):
    """도식 하나. 못 쓸 모양이면 None.

    부르는 쪽은 None 을 받으면 그 섹션을 도식 없이 둔다.
    """
    fn = BUILD.get(component_of(component) or "")
    if not fn or not isinstance(data, dict):
        return None
    built = fn(data)
    if not built:
        return None
    return {"component": component_of(component), "caption": _s(caption, 120), "data": built}


# ── HTML ──────────────────────────────────────────────────────
#
# 결과물로 내보낼 블로그 HTML 이다. 화면 마크업이 아니다.
# 홈페이지는 이 블록을 그대로 쓰고, 네이버는 이걸 그려서 PNG 로 캡처한다.
# 원본이 하나라 두 갈래가 어긋나지 않는다.

def _e(s):
    return escape(str(s), quote=True)


def _steps_html(d):
    h = ['<ol class="fig-steps">']
    for i, s in enumerate(d["steps"], 1):
        h.append('<li class="fig-step">')
        h.append(f'<span class="fig-num">{i}</span>')
        h.append('<span class="fig-stepb">')
        if s["label"]:
            h.append(f'<span class="fig-steph">{_e(s["label"])}</span>')
        if s["body"]:
            h.append(f'<span class="fig-stept">{_e(s["body"])}</span>')
        h.append('</span></li>')
    h.append('</ol>')
    return "".join(h)


def _compare_html(d):
    cols = d["columns"]
    # 첫 칸에 기준 열의 이름이 들어간다. 예전에는 빈 <th> 를 뒀는데,
    # 모델이 그 자리 이름을 columns[0] 으로 보내면서 표가 한 칸 밀렸다.
    h = [f'<table class="fig-cmp"><thead><tr><th>{_e(d.get("head", ""))}</th>']
    h += [f'<th>{_e(c)}</th>' for c in cols]
    h.append('</tr></thead><tbody>')
    for r in d["rows"]:
        h.append(f'<tr><th scope="row">{_e(r["criterion"])}</th>')
        h += [f'<td>{_e(c)}</td>' for c in r["cells"]]
        h.append('</tr>')
    h.append('</tbody></table>')
    return "".join(h)


def _cards_html(d):
    h = ['<div class="fig-cards">']
    for c in d["cards"]:
        h.append('<div class="fig-card">')
        if c["title"]:
            h.append(f'<div class="fig-cardh">{_e(c["title"])}</div>')
        if c["body"]:
            h.append(f'<div class="fig-cardt">{_e(c["body"])}</div>')
        h.append('</div>')
    h.append('</div>')
    return "".join(h)


# 가지 사이 여백. CSS 의 .fig-branch gap 과 같아야 한다.
BRANCH_GAP = 16


def _edge(n: int) -> str:
    """가로 연결선의 끝 위치.

    첫 가지 가운데에서 마지막 가지 가운데까지만 그어야 양끝에 꼬리가 안
    남는다. **`gap` 을 빼야 정확하다** — 노드 폭은 전체에서 여백을 뺀
    나머지를 나눈 것이라, `50% / n` 만 쓰면 안쪽으로 들어간다.

        n=2, gap=16  →  25% - 4px
        n=3, gap=16  →  16.6667% - 5.3333px

    CSS 안에서는 gap 을 못 세므로 여기서 계산해 넘긴다.
    """
    if n < 2:
        return "--n:1"
    pct = 50 / n
    off = BRANCH_GAP * (n - 1) / (2 * n)
    return f"--n:{n};--edge:calc({pct:.4f}% - {off:.4f}px)"


def _tree_html(d):
    root = d["root"]
    h = ['<div class="fig-tree">',
         f'<div class="fig-root">{_e(root["label"])}</div>',
         f'<div class="fig-branch" style="{_edge(len(root["children"]))}">']
    for kid in root["children"]:
        h.append('<div class="fig-node">')
        h.append(f'<div class="fig-nodeh">{_e(kid["label"])}</div>')
        if kid["children"]:
            h.append('<ul class="fig-leaf">')
            h += [f'<li>{_e(g["label"])}</li>' for g in kid["children"]]
            h.append('</ul>')
        h.append('</div>')
    h.append('</div></div>')
    return "".join(h)


RENDER = {"순서열": _steps_html, "대조표": _compare_html,
          "항목카드": _cards_html, "구조도": _tree_html}


def html(fig):
    """도식 하나를 <figure> 로. figure() 를 통과한 것만 넣는다."""
    if not fig:
        return ""
    body = RENDER[fig["component"]](fig["data"])
    cap = (f'<figcaption class="fig-cap">{_e(fig["caption"])}</figcaption>'
           if fig["caption"] else "")
    return f'<figure class="fig" data-fig="{_e(fig["component"])}">{body}{cap}</figure>'


# ── 스타일 ────────────────────────────────────────────────────
#
# 회사 사이트 디자인 가이드의 값을 그대로 쓴다. 결과물 맨 위에 한 번만 실린다.
# 네이버 쪽은 이 스타일로 그린 것을 캡처하므로 여기 값이 두 갈래의 유일한 출처다.

_CSS = """\
.fig{margin:32px 0;font-family:__FONT__;
 color:var(--bs-text);font-size:16px;line-height:1.7;max-width:820px}
/* 캡처할 때는 폭 제한을 푼다. 상자를 960px 로 잡아도 .fig 가 820 에 갇히면
   바깥 흰 여백만 늘고 표 열은 그대로 짓눌린다. 본문에서는 820 이 맞다 —
   글줄이 길어지면 읽기 나쁘다. */
.bs-shot .fig{max-width:none;width:100%}
.fig-cap{margin-top:12px;font-size:14px;color:var(--bs-text-muted)}

/* 순서열 */
.fig-steps{list-style:none;margin:0;padding:0}
.fig-step{display:flex;gap:16px;padding:0 0 20px;position:relative}
.fig-step:last-child{padding-bottom:0}
.fig-step::before{content:'';position:absolute;left:15px;top:32px;bottom:0;
 width:2px;background:var(--bs-border)}
.fig-step:last-child::before{display:none}
.fig-num{flex:0 0 32px;width:32px;height:32px;border-radius:999px;
 background:var(--bs-accent);color:#fff;font-size:14px;font-weight:600;
 display:flex;align-items:center;justify-content:center;position:relative;z-index:1}
.fig-stepb{display:block;padding-top:3px}
.fig-steph{display:block;font-size:17px;font-weight:600;color:var(--bs-primary);
 letter-spacing:-0.02em}
.fig-stept{display:block;margin-top:4px}

/* 대조표 */
/* table-layout:fixed 로 열 너비를 고르게 나눈다. auto 로 두면 긴 셀이
   열을 다 먹고 나머지가 짓눌린다. keep-all 은 한국어를 낱말 단위로 끊는다 —
   없으면 "우선 산 / 정" 처럼 낱말 가운데서 줄이 바뀐다. */
.fig-cmp{width:100%;border-collapse:collapse;border:1px solid var(--bs-border);
 table-layout:fixed;word-break:keep-all;overflow-wrap:normal;
 border-radius:var(--bs-radius);overflow:hidden}
.fig-cmp th,.fig-cmp td{padding:14px 16px;text-align:left;vertical-align:top;
 border-bottom:1px solid var(--bs-border)}
.fig-cmp thead th{background:var(--bs-primary);color:#fff;font-weight:600;font-size:15px}
.fig-cmp tbody th{background:var(--bs-surface);color:var(--bs-primary);font-weight:600;
 white-space:nowrap;width:1%}
.fig-cmp tbody tr:last-child th,.fig-cmp tbody tr:last-child td{border-bottom:none}

/* 항목카드 */
.fig-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
 gap:24px}
.fig-card{background:var(--bs-background);border:1px solid var(--bs-border);
 border-radius:var(--bs-radius);padding:20px;box-shadow:none}
.fig-cardh{font-size:17px;font-weight:600;color:var(--bs-primary);letter-spacing:-0.02em;
 margin-bottom:8px}
.fig-cardt{font-size:15px}

/* 구조도 */
.fig-tree{position:relative}
/* 상위와 하위를 잇는 선. 없으면 상자 셋을 그냥 늘어놓은 것으로 보인다 —
   순서열에는 세로선이 있는데 구조도에만 없었다. */
.fig-root{position:relative;background:var(--bs-primary);color:#fff;border-radius:var(--bs-radius);padding:16px 20px;
 font-size:17px;font-weight:600;letter-spacing:-0.02em;text-align:center}
/* 세 선이 정확히 이어지게 좌표를 맞춘다. 어긋나면 가운데에 짧은 꼬리가
   보이거나 선이 끊겨 보인다.

       루트 아래 10px  →  가로선  →  노드 위 10px
       (가지 margin-top 20px 의 가운데)                */
.fig-root::after{content:"";position:absolute;left:50%;bottom:-10px;
 width:2px;height:10px;background:var(--bs-border, #E3E8EF)}
.fig-branch{position:relative;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
 gap:16px;margin-top:20px}
/* 가지들을 잇는 가로선. **첫 가지 가운데에서 마지막 가지 가운데까지**만
   그린다. 끝 위치는 렌더러가 계산해 --edge 로 넘긴다 — CSS 안에서
   계산하면 gap 을 못 세서 양끝이 안쪽으로 들어간다(2가지 4px, 3가지 5.3px).
   하나뿐이면 잇는 것이 없어 안 그린다. */
.fig-branch::before{content:"";position:absolute;top:-10px;
 left:var(--edge, 25%);right:var(--edge, 25%);
 height:2px;background:var(--bs-border, #E3E8EF)}
.fig-branch>.fig-node:only-child{grid-column:1/-1}
/* 가지가 하나면 잇는 것이 없다. :has() 는 캡처 라이브러리가 못 읽을 수
   있어서 개수로 막는다. */
.fig-branch[style*="--n:1"]::before{display:none}
.fig-node{position:relative;background:var(--bs-accent-bg);border-radius:var(--bs-radius);padding:16px 18px}
.fig-node::before{content:"";position:absolute;left:50%;top:-10px;
 width:2px;height:10px;background:var(--bs-border, #E3E8EF)}
.fig-nodeh{font-size:16px;font-weight:600;color:var(--bs-primary);letter-spacing:-0.02em}
.fig-leaf{margin:10px 0 0;padding:0;list-style:none}
.fig-leaf li{background:#fff;border-radius:999px;padding:5px 12px;margin-top:6px;
 font-size:14px;color:var(--bs-text-muted);display:inline-block;margin-right:6px}

@media (max-width:767px){
 .fig-cards,.fig-branch{grid-template-columns:1fr}
 .fig-cmp thead th,.fig-cmp tbody th{font-size:14px}
}
"""

# 변수 선언이 안 잡히는 자리(캡처)에서도 읽히도록 기본값을 끼운다.
CSS = brand.with_fallback(_CSS)
