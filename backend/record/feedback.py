"""사람이 남긴 평가.

세션은 메모리라 서버를 끄면 사라진다. 평가는 남아야 한다 — 지금 프롬프트는
전부 추측으로 쓴 것이고, "사람이 어떤 후보를 왜 버렸나"가 그걸 고칠 유일한
근거다.

id 만 남기면 나중에 아무 의미가 없다. 2~7단계 후보 id 는 그 세션 한정
임시 번호라 p0 가 무엇이었는지 알 길이 없다. 그래서 후보 내용과 그때
프롬프트에 넣은 입력을 통째로 함께 남긴다.

쓰고 읽는 일은 log.py 가 한다. 여기는 무엇을 남길지만 안다.
"""

from . import log

STREAM = "feedback"


def record(**row) -> None:
    log.write(STREAM, **row)


def read(day: str | None = None) -> list[dict]:
    return log.read(STREAM, day)
