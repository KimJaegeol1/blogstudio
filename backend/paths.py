"""경로.

파일이 어디 있는지 아는 유일한 파일이다.

여기저기서 `Path(__file__).parent.parent` 를 세면, 파일을 한 칸만 옮겨도
가리키는 곳이 조용히 달라진다. 예외도 안 나고 화면도 멀쩡한데 로그만
엉뚱한 폴더에 쌓인다 — 실제로 그것 때문에 시간을 썼다.

그래서 세는 일은 여기서 한 번만 한다. 다른 파일은 이 이름들을 가져다 쓴다.
폴더를 나누더라도 이 파일만 backend/ 바로 아래 두면 나머지는 어디로 가도 된다.
"""

from pathlib import Path

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent                    # blogstudio/

FRONTEND = ROOT / "frontend"
PROMPTS = BACKEND / "prompts"
DATA = BACKEND / "data"

ENV = ROOT / ".env"
IMAGES = ROOT / "images"
UPLOADS = ROOT / "uploads"       # 사람이 올린 근거 문서

# 로그 세 갈래. 물어보는 질문이 달라서 파일부터 나눠 둔다.
FEEDBACK = ROOT / "feedback"      # 사람이 남긴 평가
CHOICE = ROOT / "choice"          # 사람이 고른 것
RESPONSE = ROOT / "response"      # AI 가 내놓은 것


def stream(name: str) -> Path:
    """줄 로그가 쌓이는 폴더. log.py 가 쓴다."""
    return ROOT / name
