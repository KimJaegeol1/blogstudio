"""대표 이미지 생성.

openai.py 가 OpenAI 를 아는 유일한 파일이듯, 여기가 Gemini 를 아는 유일한
파일이다. 나눈 이유는 파는 회사가 달라서가 아니라 **만드는 것이 달라서**다.
저쪽은 글을 받고 여기는 그림을 받는다.

본문 도식은 여기 오지 않는다. figures.py 가 마크업으로 그린다 — 글자가 뜻을
지고 있는 그림을 생성 모델에 맡기면 한글이 깨지고, 틀린 수치가 그림 안에
박히면 아무도 교정하지 못한다. 여기서 만드는 것은 **글자가 없는 상징 그림
한 장**뿐이다.

SDK 대신 REST 를 직접 부른다. 호출이 하나뿐이라 패키지를 하나 더 얹을
이유가 없고, 키가 없는 환경에서 import 조차 실패하지 않는다.
"""

import base64
import json
import urllib.error
import urllib.request

from .. import config, paths

API = ("https://generativelanguage.googleapis.com/v1beta/"
       "models/{model}:generateContent")

KEY = config.GEMINI_API_KEY
MODEL = config.GEMINI_IMAGE_MODEL

ENABLED = bool(KEY)

TIMEOUT = 90


class ImagenError(Exception):
    """호출이나 응답이 쓸 수 없는 상태. 감추지 않고 화면까지 올린다."""


# 그림에 글자가 들어가면 못 고친다. **모델이 지시문에 안 넣으면 그만이라**
# 코드가 붙인다 — 실제로 "Existing reporting work" 가 철자까지 깨진 채
# 박혀 나왔다.
NO_TEXT = ("no text, no letters, no words, no numbers, no labels, "
           "no captions, no watermark. any documents or screens shown must be "
           "blank with no writing on them")


def with_no_text(prompt: str) -> str:
    """글자 금지를 지시문 끝에 붙인다. 이미 있으면 안 붙인다."""
    t = (prompt or "").strip()
    return t if "no text" in t.lower() else f"{t.rstrip('. ')}. {NO_TEXT}"


def draw(prompt: str) -> bytes:
    """영어 프롬프트를 주면 이미지 바이트를 준다.

    실패는 전부 ImagenError 로 올린다. 대표 이미지가 없어도 글은 나가므로
    부르는 쪽이 잡아서 자리표시로 되돌리면 된다.
    """
    if not ENABLED:
        raise ImagenError("GEMINI_API_KEY 가 없다")

    # **글자 금지는 코드가 붙인다.** 프롬프트에 규칙을 적어 뒀지만 모델이
    # 지시문에 안 넣으면 그만이다 — 실제로 철자가 깨진 영문이 박혀 나왔다.
    body = json.dumps({
        "contents": [{"parts": [{"text": with_no_text(prompt)}]}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API.format(model=MODEL), data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": KEY})

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            got = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 본문에 이유가 들어 있다. 상태 코드만 올리면 키 문제인지 한도인지
        # 프롬프트 문제인지 구별할 수 없다.
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        raise ImagenError(f"이미지 생성 실패 ({MODEL}, HTTP {e.code}) {detail}") from e
    except Exception as e:
        raise ImagenError(f"이미지 생성 실패 ({MODEL}): {e}") from e

    return _bytes(got)


def _bytes(got: dict) -> bytes:
    """응답에서 이미지만 꺼낸다.

    parts 에는 설명 문장이 섞여 오기도 한다. 자리로 찾지 않고 inlineData 를
    가진 것을 고른다 — 순서에 기대면 조용히 엉뚱한 걸 집는다.
    """
    for c in got.get("candidates") or []:
        for part in ((c.get("content") or {}).get("parts") or []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                try:
                    return base64.b64decode(blob["data"])
                except Exception as e:
                    raise ImagenError(f"이미지를 읽지 못했다: {e}") from e

    # 안전 필터에 걸리면 이미지 없이 이유만 온다.
    reason = ""
    for c in got.get("candidates") or []:
        reason = c.get("finishReason") or reason
    raise ImagenError(f"이미지가 없는 응답이 왔다{f' ({reason})' if reason else ''}")


def save(data: bytes, name: str) -> str:
    """images/ 에 쓰고 파일 이름을 준다. 같은 이름이면 덮어쓴다 — 다시 만들면
    이전 것을 남길 이유가 없다."""
    paths.IMAGES.mkdir(parents=True, exist_ok=True)
    f = paths.IMAGES / name
    f.write_bytes(data)
    return f.name
