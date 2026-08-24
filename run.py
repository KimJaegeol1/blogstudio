"""실행 진입점.

백엔드(JSON API)와 프론트(정적 파일)를 한 서버에 얹는다.
둘을 붙이는 건 여기서만 한다 — 백엔드는 프론트를 모르고,
프론트는 /api 주소만 안다. 나중에 따로 띄우려면 이 파일만 바꾼다.

  python run.py                     그대로. .env 의 값을 따른다
  PORT=8004 python run.py           그때만 다른 포트로

포트와 실행 방식은 .env 에 적어 둔다.

  BS_ENV=server
  PORT=8004

환경변수로 준 값이 .env 보다 우선한다.

내 컴퓨터와 서버는 다르게 뜬다.

  내 컴퓨터   코드를 고치면 다시 뜨고, 브라우저를 열어 준다
  서버        둘 다 안 한다. 파일을 감시하면 CPU 를 먹고, 열 브라우저도 없다

BS_ENV 를 server 로 두거나 화면(DISPLAY)이 없으면 서버로 본다.
"""
import os
import threading
import webbrowser

import uvicorn
from fastapi.staticfiles import StaticFiles

from backend import config  # noqa: F401  (import 만으로 .env 가 os.environ 에 오른다)
from backend import paths
from backend.main import app

FRONTEND = paths.FRONTEND

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# 서버인지 내 컴퓨터인지. 창을 띄울 수 없는 자리면 서버로 본다.
SERVER = (os.environ.get("BS_ENV", "").lower() == "server"
          or (os.name != "nt" and not os.environ.get("DISPLAY")))


@app.middleware("http")
async def no_stale(request, call_next):
    """정적 파일을 브라우저가 캐시해 두지 않게 한다.

    css·js 를 고쳤는데 화면이 그대로면 원인을 찾는 데 시간을 다 쓴다.
    no-store 가 아니라 no-cache 라서, 바뀐 게 없으면 서버가 304 로 답한다.
    """
    res = await call_next(request)
    if not request.url.path.startswith("/api/"):
        res.headers["Cache-Control"] = "no-cache"
    return res


# /api 라우트가 먼저 잡히도록 프론트는 맨 마지막에 붙인다.
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")

from backend import build, llm  # noqa: E402
from backend.external import gemini, search as tavily  # noqa: E402
from backend.record import history, log  # noqa: E402


def banner():
    print(f"  코드      {build.CODE}")
    print(f"  프롬프트   {build.CONTENT}")
    print(f"  주소      http://{HOST}:{PORT}")
    for s in history.STREAMS:
        print(f"  로그 {s:9s} {log.where(s)}")
    # 키가 없으면 화면에서만 알 수 있다. 뜰 때 한 번 알린다.
    if not llm.ENABLED:
        print("  [!] OPENAI_API_KEY 가 없습니다 — 후보가 가짜 데이터로 나옵니다")
    if not gemini.ENABLED:
        print("  [!] GEMINI_API_KEY 가 없습니다 — 대표 이미지를 만들 수 없습니다")
    if not tavily.ENABLED:
        print("  [!] TAVILY_API_KEY 가 없습니다 — 근거를 검색하지 않습니다."
              " 명제가 전부 '확인 필요' 로 남습니다")


if __name__ == "__main__":
    # reload 를 켜면 부모와 자식이 각각 이 파일을 읽는다. 모듈 바닥에서 찍으면
    # 같은 줄이 세 번 나와 재시작한 것처럼 보인다. 부모에서 한 번만 찍는다.
    banner()
    if not SERVER:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    uvicorn.run("run:app", host=HOST, port=PORT, reload=not SERVER)
