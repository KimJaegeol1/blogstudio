"""결과물 조립 — 채널로 갈린다.

여기는 분배만 한다. 실제 조립은 채널 폴더에 있다.

    site/render.py    HTML 그대로. 메타 · 신뢰 요소 · 서비스 연결
    naver/render.py   스마트에디터에 붙는 마크업. 태그. 도식은 자리표시

**한 드래프트는 한 채널이다.** 예전에는 본문 하나로 두 결과물을 만들었는데,
그러면 문체·구조·CTA 가 같고 표현만 다른 글이 둘 나온다. 지금은 채널을
2단계에서 고르고 본문부터 그 채널로 쓴다.

두 렌더러는 서로를 import 하지 않는다. 공유가 필요한 것은 `common.py` 에 있고,
도식은 `figures.py` 한 벌이다 — 네이버는 그 마크업을 캡처해 쓴다.
"""

from . import checklist, illust
from .naver import render as naver
from .site import render as site
from ..data import channels
from ..data.channels import channel_of

BY_CHANNEL = {"site": site.build, "naver": naver.build}


def build(d) -> dict:
    """그 드래프트의 채널 하나만 만든다.

    키는 채널 이름 그대로 두고 고른 쪽만 채운다. 화면이 어느 쪽이 왔는지
    보고 그린다 — `channel` 을 같이 실어 보내므로 키를 뒤지지 않아도 된다.
    """
    ch = channel_of(d)
    out = {name: None for name in BY_CHANNEL}
    out[ch] = BY_CHANNEL[ch](d)
    rows = checklist.build(d, ch)
    # 만들어진 본문 그림. 화면이 어느 자리에 무엇이 있는지 보여 준다.
    illus = {n: {"purpose": v.get("purpose", ""),
                 "made": bool((d.get("illust") or {}).get(str(n))),
                 "alt": ((d.get("illust") or {}).get(str(n)) or {}).get("alt", "")}
             for n, v in illust.plans(d).items()}
    return {"channel": ch, "capture": channels.capture(ch),
            # 이 글을 그대로 내도 되는지. 확인 목록을 다 읽지 않아도
            # 한 줄로 보이게 한다 — 안 읽고 발행하는 것이 실제 실패다.
            "ready": checklist.ready(d, rows),
            "illust": illus,
            "checklist": rows, **out}
