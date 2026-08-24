"""선택 결과 — 주어진 후보 중에서 사람이 실제로 고른 것.

    choice/{날짜}.jsonl

세 갈래 중 하나다.

    feedback   사람이 남긴 평가        — 좋다 / 별로다 / 메모
    choice     사람이 고른 것          ← 여기
    response   AI 가 내놓은 것         — 후보 · 본문 · 이미지 · 실패

한 행이 그 자체로 읽혀야 한다. 그래서 `offered`(그때 주어진 후보의 id 와
제목)를 같이 남긴다. `chosen` 만 남기면 "o0 을 골랐다"가 되어 response 파일과
조인하지 않으면 아무 뜻이 없다. 내용 전체는 response 쪽 generated 행에 있으니
여기는 제목까지만 적는다.

사람이 올린 문서도 여기 온다. 고르는 일은 아니지만 **사람이 넣은 것**이고,
AI 가 내놓은 것과는 성격이 다르다. 같은 세션의 response 행과 시간순으로
붙여 읽으면 "이 문서를 넣었더니 모델이 이렇게 했다" 가 그대로 나온다.

1단계 소재도 여기 온다. LLM 이 만든 게 아니라 시트에서 오지만, 고르는 일은
같은 일이라 행 모양을 맞춰 둔다.
"""

from . import log

STREAM = "choice"


def _brief(o: dict) -> dict:
    """목록에 남길 요약. 내용 전체는 response 의 generated 행에 있다."""
    return {"id": o.get("id"), "title": o.get("title")}


def confirmed(sid: str, step: str, offered: list[dict],
              chosen: list[str], written: str, value: dict) -> None:
    """무엇이 주어졌을 때 무엇을 골랐나.

    written 이 비어 있지 않으면 고른 게 아니라 직접 쓴 것이다.
    """
    log.write(STREAM, kind="confirmed", sid=sid, step=step,
              offered=[_brief(o) for o in offered],
              chosen=chosen, written=written,
              value={"label": value.get("label"), "detail": value.get("detail"),
                     "payload": value.get("payload")})


def uploaded(sid: str, step: str, doc: dict) -> None:
    """사람이 문서를 올렸다.

    파일은 uploads/{sid}/{id}.pdf 에 id 로만 저장된다 — 사용자가 준 이름을
    경로에 쓰면 ../ 하나로 폴더 밖에 쓸 수 있기 때문이다. 그래서 **원래
    이름이 남는 곳은 여기뿐이다.** 나중에 폴더를 열었을 때 어느 파일이
    무엇이었는지 이 행으로만 알 수 있다.

    sha 는 내용 지문이다. id 는 올릴 때마다 새로 나므로 같은 문서를 두 번
    올렸는지 id 로는 알 수 없다.
    """
    log.write(STREAM, kind="uploaded", sid=sid, step=step,
              doc=doc.get("id"), name=doc.get("name"), sha=doc.get("sha"),
              pages=doc.get("pages"), chars=doc.get("chars"),
              bytes=doc.get("bytes"),
              picked=doc.get("picked"), segments=doc.get("segments") or [],
              pick_error=doc.get("pick_error", ""))


def rejected(sid: str, step: str, name: str, size: int, reason: str) -> None:
    """받지 않았다.

    거절이 안 남으면 상한을 조정할 근거가 없다. 지금 상한(40만 자·6만 자)은
    재서 정한 값이 아니라 어림이라, 무엇이 얼마나 자주 걸리는지 쌓여야 한다.
    """
    log.write(STREAM, kind="rejected", sid=sid, step=step,
              name=name, bytes=size, reason=reason)


def read(day: str | None = None) -> list[dict]:
    return log.read(STREAM, day)
