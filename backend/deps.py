"""라우트가 매번 하던 준비 작업.

세션을 꺼내고, 드래프트를 확인하고, 모르는 단계를 막는 일은
모든 라우트에서 똑같이 벌어진다. 여기 모아 두고 주입한다.
"""

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from . import llm, session, steps


class Refuse(Exception):
    """요청을 받아들일 수 없을 때.

    어디로 보낼지는 프론트가 정한다. 백엔드는 이유만 알려 준다.
    """

    def __init__(self, reason: str, **extra):
        self.reason = reason
        self.extra = extra


def refused(request: Request, exc: Refuse) -> JSONResponse:
    return JSONResponse({"ok": False, "reason": exc.reason, **exc.extra})


def llm_failed(request: Request, exc: llm.LLMError) -> JSONResponse:
    """프롬프트 호출이 실패했다. 테스트 데이터로 조용히 떨어지지 않는다 —
    화면만 보고 무엇이 돌았는지 알 수 없게 되기 때문이다."""
    return JSONResponse({"ok": False, "reason": "llm_failed", "detail": str(exc)})


@dataclass
class Ctx:
    sid: str
    st: dict


@dataclass
class Drafting:
    sid: str
    st: dict
    d: dict


def ctx(request: Request) -> Ctx:
    """세션. 쿠키를 붙이는 건 미들웨어가 한다 — 거절될 때도 붙어야 하므로."""
    sid = request.state.sid
    _, st = session.get(sid)
    return Ctx(sid, st)


def drafting(c: Ctx = Depends(ctx)) -> Drafting:
    """소재가 정해진 드래프트. 없으면 여기서 막는다."""
    d = session.draft(c.st)
    if not d.get("topic"):
        raise Refuse("no_topic")
    return Drafting(c.sid, c.st, d)


def known(key: str) -> str:
    if key not in steps.BY_KEY:
        raise Refuse("unknown_step")
    return key


def editable(key: str = Depends(known)) -> str:
    """확정할 수 있는 단계. 승인은 고를 게 없다."""
    if key == "approve":
        raise Refuse("unknown_step")
    return key
