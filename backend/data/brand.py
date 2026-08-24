"""디자인 언어.

**글마다 구조가 달라도 같은 회사가 만든 것처럼 보이게 하는 것**이 여기다.
통일성은 구조에서 오지 않는다 — 모든 글을 같은 뼈대로 찍어 내면 통일된 게
아니라 똑같아진다. 색, 곡률, 선 굵기, 여백, 캡션 형식만 일정하면 구조가
글마다 달라도 한 브랜드로 읽힌다.

값을 여기 모아 두는 이유는 지금 색이 세 군데에 흩어져 있어서다 —
figures.CSS, render 의 BODY_CSS, 프론트 app.css. 한 곳만 고치면 나머지가
조용히 어긋난다.

솔루티스 사이트 팔레트를 따른다. 곡률은 4px 하나로 간다. 사이트가 전반적으로
각진 디자인이라 도식만 둥글면 그쪽이 튄다.

**여기는 아무것도 import 하지 않는다.**
"""

FONT = "Pretendard, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

COLORS = {
    "primary": "#16233A",      # 로고 네이비. 제목과 본문 글자
    "accent": "#2B8AE0",       # 강조. 링크·라벨·왼쪽 선
    "accent_bg": "#F1F7FD",    # 강조 배경
    "background": "#FFFFFF",
    "surface": "#F6F8FB",      # 도식 바탕
    "border": "#E3E8EF",
    "text": "#374151",         # 본문
    "text_muted": "#5F6B7A",   # 캡션·해석
}

RADIUS = "4px"
SHADOW = "none"

# 생성 이미지의 결. hero 프롬프트가 읽는다.
IMAGE_STYLE = "clean editorial illustration, restrained, no text"


def css_vars() -> str:
    """도식·본문 CSS 가 쓰는 변수 선언.

    값을 문자열로 박지 않고 변수로 내보내는 이유는, 결과물 HTML 이 회사
    사이트에 붙었을 때 사람이 한 줄만 고쳐 색을 맞출 수 있게 하려는 것이다.
    """
    rows = [f"  --bs-{k.replace('_', '-')}: {v};" for k, v in COLORS.items()]
    rows.append(f"  --bs-radius: {RADIUS};")
    return ".post{\n" + "\n".join(rows) + "\n}"


# ── 네이버 인라인 스타일 ──────────────────────────────────────
#
# 네이버 에디터는 class 를 지우므로 style 을 인라인으로 넣는다. 값은 여기
# 한 곳에 둔다 — 렌더러에 색을 박으면 브랜드가 또 죽은 데이터가 된다.
#
# 에디터가 살려 주는 속성만 쓴다. margin · padding · background ·
# border-left · color · font-size · font-weight · text-align 은 남고,
# class · id · flex · grid 는 지워진다.

NAVER = {
    # 소제목. 위 여백이 본문 사이 여백보다 훨씬 커야 섹션이 갈려 보인다.
    # 예전에는 둘 다 14px 이라 스크롤할 때 어디서 시작하는지 안 보였다.
    "heading": (f"margin:32px 0 10px;font-size:19px;font-weight:700;"
                f"color:{COLORS['primary']};line-height:1.5"),
    # 본문. **line-height 를 반드시 준다.** 네이버 에디터 기본이 1.5~1.6 이라
    # 안 주면 본문만 빽빽해진다 — 리드·목록·강조는 다 1.8~1.9 인데 글에서
    # 제일 많은 자리가 빠져 있었다.
    "para": "margin:0 0 18px;line-height:1.9",
    # 리드는 본문 진입부다. **박스로 감싸지 않는다** — 감싸면 안내·요약처럼
    # 보여서 본문이 아직 시작 안 한 것으로 읽힌다.
    "lead": "margin:24px 0 28px;font-size:17px;line-height:1.9",
    "lead_q": (f"margin:24px 0 14px;font-size:18px;font-weight:700;"
               f"text-align:center;color:{COLORS['primary']}"),
    # 목록. 항목 사이를 벌려야 표처럼 안 보인다.
    "list": "margin:0 0 18px;padding-left:22px",
    "item": "margin:0 0 14px;line-height:1.8",
    "item_title": f"color:{COLORS['primary']};font-weight:700",
    # 강조 박스. 회색이 아니라 브랜드 색이다.
    "callout": (f"margin:22px 0;padding:14px 18px;background:{COLORS['accent_bg']};"
                f"border-left:3px solid {COLORS['accent']};color:{COLORS['text']};"
                f"line-height:1.8"),
    # 라벨과 본문을 각각 <p> 로 낸다. display:block 에 기대면 에디터가
    # 그것을 지웠을 때 "실무 포인트여러 채널에..." 로 붙는다.
    "callout_label": (f"margin:0 0 6px;font-size:13px;font-weight:700;"
                      f"color:{COLORS['accent']}"),
    "callout_body": "margin:0;line-height:1.8",
    # 그림을 넣을 자리. 구분선 대신 옅은 상자로 감싼다 — 구분선은 그림을
    # 넣고 나서도 남아서 위아래에 이유 없는 줄이 붙는다.
    "slot": (f"margin:22px 0;padding:16px 18px;background:{COLORS['surface']};"
             f"border:1px dashed {COLORS['border']};color:{COLORS['text_muted']};"
             f"text-align:center;line-height:1.7"),
    "slot_label": f"font-weight:700;color:{COLORS['accent']}",
    # 글 끝 안내.
    "cta": (f"margin:32px 0 0;padding:18px 20px;background:{COLORS['accent_bg']};"
            f"line-height:1.8"),
    "cta_action": f"font-weight:700;color:{COLORS['primary']}",
    "rule": f"margin:28px 0;color:{COLORS['border']};text-align:center",
}


def with_fallback(css: str) -> str:
    """`var(--bs-accent)` 를 `var(--bs-accent, #2B8AE0)` 로 채운다.

    변수만 쓰면 캡처에서 깨진다. 도식을 이미지로 저장할 때 화면 밖에 복제해
    찍는데, 그때 `.post` 바깥이라 변수 선언이 안 잡힌다. 색이 통째로 사라진
    도식이 네이버에 올라간다.

    기본값을 CSS 에 직접 적으면 색이 두 군데가 되므로, 값은 여기 한 곳에
    두고 문자열을 만들 때 끼운다.
    """
    out = css.replace("__FONT__", FONT)
    for k, v in COLORS.items():
        out = out.replace(f"var(--bs-{k.replace('_', '-')})",
                          f"var(--bs-{k.replace('_', '-')}, {v})")
    return out.replace("var(--bs-radius)", f"var(--bs-radius, {RADIUS})")


# ── 캡처용 덧씌우기 ───────────────────────────────────────────
#
# 네이버 도식은 같은 마크업을 이미지로 찍어 넣는다. 휴대폰에서 읽히므로
# 폭이 좁고 글자가 커야 하는데, 그건 렌더러를 새로 만들 일이 아니라
# **찍을 때 스타일만 갈아 끼우면 되는 일**이다.
#
# 렌더러를 둘로 만들면 도식 내용이 두 채널에서 어긋날 수 있다. 마크업이
# 한 벌이면 어긋날 수가 없다 — 그 성질을 지키면서 배치만 바꾼다.

# 도식을 찍을 때의 폭. **본문 폭과 다르다.**
#
# 본문은 680px 이 맞다 — 휴대폰에서 읽는 글이다. 그런데 도식을 같은 폭으로
# 찍으면 4열 대조표의 열이 짓눌려서 "우선 산 / 정" 처럼 낱말 가운데서 줄이
# 바뀐다. 캡처한 그림은 네이버 본문에서 화면 폭에 맞춰 줄어드니, 원본을
# 넓게 찍어도 최종 크기는 같다.
#
# 형식마다 필요한 폭이 다르다. 카드는 좁아도 되고 표는 넓어야 한다.
FIGURE_WIDTHS = {
    "항목카드": 760,
    "순서열": 820,
    "구조도": 900,
    "대조표": 960,
}

NAVER_FIGURE_CSS = """\
.fig{font-size:18px;max-width:none}
/* 항목카드만 한 줄로 세운다. **구조도는 그대로 둔다** — 세로로 쌓으면
   가지들을 잇는 가로선이 붕 뜨고, 상하위 관계가 목록처럼 보인다.
   구조도는 900px 로 찍으므로 두 갈래가 나란히 들어간다. */
.fig-cards{grid-template-columns:1fr;gap:14px}
.fig-branch{gap:14px}
.fig-cmp th,.fig-cmp td{padding:12px 14px;font-size:16px}
.fig-cmp thead th,.fig-cmp tbody th{font-size:16px}
.fig-cmp tbody th{white-space:normal;width:auto}
.fig-steph,.fig-cardh,.fig-nodeh{font-size:18px}
.fig-stept,.fig-cardt{font-size:16px}
.fig-cap{font-size:15px}
"""


def image_hint() -> str:
    """대표 이미지 프롬프트에 실을 결. 색은 이름이 아니라 값으로 준다."""
    return (f"{IMAGE_STYLE}; palette around {COLORS['primary']} and "
            f"{COLORS['accent']} on {COLORS['background']}")
