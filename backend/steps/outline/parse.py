"""직접 쓴 구조 읽기.

규칙 네 줄이다.

    "이미지:" 로 시작  →  바로 위 소제목의 이미지
    "근거:"   로 시작  →  바로 위 소제목이 다룰 명제 id
    "사진:"   로 시작  →  바로 위 소제목에 넣을 실제 사진 (네이버)
    "캡처:"   로 시작  →  바로 위 소제목에 넣을 자료 화면 (네이버)
    "대표:"   로 시작  →  대표 이미지
    그 밖의 줄         →  소제목
    빈 줄              →  무시

**바로 위 소제목에 붙인다.** 번호나 소제목 이름으로 가리키지 않는 이유는,
소제목을 고치거나 순서를 바꾸는 것이 이 칸의 목적이기 때문이다. 붙어 있는
줄에 붙이면 소제목을 고쳐도 연결이 끊기지 않는다.

같은 규칙이 frontend/js/shape.js 에도 있다. 그쪽은 **타이핑하는 동안 결과를
보여 주는 용도**고, 확정값은 여기서 만든 것을 쓴다. 두 곳에 같은 규칙이 있는
것은 알고 있다 — 타이핑마다 서버를 부르지 않고, 프론트가 보낸 값을 믿지도
않기 위한 선택이다. 어긋나도 숫자만 틀리게 보이고 저장되는 값은 이쪽 것이다.
"""

from ... import sanitize as z
from . import payload as P

_IMG_P = ("이미지:", "이미지 :")
_HERO_P = ("대표:", "대표 :")
# 근거 배치. **없어도 된다.** 안 적으면 빈 배열이고, 자동으로 전체 명제를
# 붙이거나 제목이 비슷하다고 임의로 잇지 않는다 — 그러면 사람이 안 정한
# 배치가 정한 것처럼 뒤로 흘러간다.
_REF_P = ("근거:", "근거 :")
# 사람이 준비할 자료. 생성하지 않는다.
_MEDIA_P = {("사진:", "사진 :"): "photo", ("캡처:", "캡처 :"): "capture"}

# 긴 대시를 먼저 본다. 짧은 붙임표는 앞뒤에 공백이 있을 때만 구분자로 센다 —
# 안 그러면 "Before-Process-After" 같은 형식 이름이 잘린다.
_DASH = ("—", "–", " - ")


def _after(s, prefixes):
    """접두어를 떼고 나머지를 준다. 접두어가 아니면 None."""
    for pre in prefixes:
        if s.startswith(pre):
            return s[len(pre):]
    return None


def _img_line(s):
    """'전후 비교 도식 — 서류 항목 차이' 를 형식과 목적으로 쪼갠다.
    구분자가 없으면 전체를 형식으로 읽는다."""
    for d in _DASH:
        if d in s:
            form, _, purpose = s.partition(d)
            return {"form": z.s(form), "purpose": z.s(purpose)}
    return {"form": z.s(s), "purpose": ""}


def read(text):
    """직접 쓴 구조 → (label, detail, payload)."""
    secs, hero = [], None
    for line in text.splitlines():
        s = z.s(line)
        if not s:
            continue

        body = _after(s, _HERO_P)
        if body is not None:
            # 대표는 form 이 없다. 쓴 줄 전체가 purpose 다.
            hero = {"purpose": z.s(body)}
            continue

        body = _after(s, _IMG_P)
        if body is not None:
            if secs:                       # 붙일 소제목이 없으면 버린다
                secs[-1]["image"] = _img_line(body)
            continue

        hit = None
        for pats, kind in _MEDIA_P.items():
            body = _after(s, pats)
            if body is not None:
                hit = (kind, body)
                break
        if hit is not None:
            if secs:
                secs[-1]["media"] = {"type": hit[0], "purpose": z.s(hit[1])}
            continue

        body = _after(s, _REF_P)
        if body is not None:
            if secs:
                secs[-1]["claim_refs"] = [x.strip() for x in
                                          body.replace("·", ",").split(",")
                                          if x.strip()]
            continue

        secs.append({"title": s, "image": None, "illustration": None,
                     "claim_refs": [], "media": None})

    # 직접 쓸 때는 채널을 모른다. 코드가 비우는 일은 확정 시점이 아니라
    # 후보를 만들 때 하므로, 여기서는 쓴 대로 받는다.
    pay = P.payload(secs, hero)
    n = len(pay["sections"])
    body_n = sum(1 for x in pay["sections"] if x["image"])
    media_n = sum(1 for x in pay["sections"] if x.get("media"))
    hero_n = 1 if pay["hero_image"] else 0
    return P.label(n, body_n, hero_n, media_n), P.detail(pay), pay
