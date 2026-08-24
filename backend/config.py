"""키와 설정.

.env 를 읽는 유일한 파일이다. 다른 모듈은 여기서 이름으로 가져다 쓴다.

전에는 llm.py 가 .env 를 읽었고, imagen.py 가 그 부수효과를 얻으려고
llm.py 를 import 했다. Gemini 를 아는 파일이 OpenAI 를 아는 파일에
매달려 있었던 것이다 — 파는 회사가 하나 늘 때마다 그 줄이 하나씩 늘어난다.
설정을 잎으로 빼면 그 의존이 사라진다.

여기는 paths 말고 아무것도 import 하지 않는다.

    OPENAI_API_KEY        없으면 후보가 테스트 데이터로 나온다
    OPENAI_MODEL          기본 모델
    OPENAI_MODEL_STRONG   상위 모델 (없으면 기본과 같다)
    GEMINI_API_KEY        없으면 대표 이미지를 만들 수 없다
    GEMINI_IMAGE_MODEL    이미지 모델
    TAVILY_API_KEY        없으면 근거를 검색하지 않는다
"""

import os

from . import paths

# 자리표시가 그대로 남아 있으면 키가 없는 것으로 본다. 안 그러면
# "여기에-키를-넣으세요" 를 들고 호출하다 401 을 받는다.
PLACEHOLDER = "여기에-키를-넣으세요"

# .env 에 아무것도 없을 때만 쓰인다. 오래된 이름을 조용히 부르지 않도록
# 현재 세대로 맞춰 둔다.
DEFAULT_TEXT_MODEL = "gpt-5.6-luna"

# Imagen 계열은 2026-08-17 에 종료된다. 대표 이미지는 글자가 없는 상징 그림
# 한 장이라 4K 도 정밀한 텍스트 렌더링도 필요 없다.
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"


def _load_env() -> None:
    """.env 를 읽어 환경변수로 올린다. 이미 있으면 그쪽이 이긴다."""
    f = paths.ENV
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def key(name: str) -> str:
    """키 하나. 비었거나 자리표시면 빈 문자열."""
    v = os.environ.get(name, "").strip()
    return "" if v == PLACEHOLDER else v


def text(name: str, default: str = "") -> str:
    """키가 아닌 설정값 하나."""
    return (os.environ.get(name) or default).strip()


OPENAI_API_KEY = key("OPENAI_API_KEY")
OPENAI_MODEL = text("OPENAI_MODEL", DEFAULT_TEXT_MODEL)
OPENAI_MODEL_STRONG = text("OPENAI_MODEL_STRONG") or OPENAI_MODEL

GEMINI_API_KEY = key("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = text("GEMINI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)

# 없으면 근거 단계가 검색 없이 돈다 — 지금까지처럼 "무엇을 어디서 확인할지"
# 까지만 만들고 확인은 사람 몫이 된다. 있는데 실패하면 조용히 넘어가지 않는다.
TAVILY_API_KEY = key("TAVILY_API_KEY")
