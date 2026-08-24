"""백엔드 앱.

JSON API 만 제공한다. 템플릿도 정적 파일도 여기서 다루지 않는다.
프론트를 어떻게 붙일지는 run.py 가 정한다 — 백엔드는 프론트의 존재를 모른다.
"""

from fastapi import FastAPI, Request

from . import llm, session
from .api import router
from .deps import Refuse, llm_failed, refused

app = FastAPI(title="SOLUTIS C&T 콘텐츠 제작 API")
app.include_router(router)
app.add_exception_handler(Refuse, refused)
app.add_exception_handler(llm.LLMError, llm_failed)


@app.middleware("http")
async def carry_session(request: Request, call_next):
    """세션 쿠키를 물고 다닌다.

    요청이 거절될 때도 쿠키는 붙어야 한다. 안 그러면 거절될 때마다
    세션이 새로 생겨 앞에서 고른 게 사라진다.
    """
    sid = request.cookies.get(session.COOKIE) or session.new_sid()
    request.state.sid = sid
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.set_cookie(session.COOKIE, sid, httponly=True,
                            samesite="lax", max_age=60 * 60 * 12)
    return response
