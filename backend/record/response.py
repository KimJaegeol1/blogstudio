"""AI 응답 — 모델이 내놓은 것 전부.

    response/{날짜}.jsonl

세 갈래 중 하나다.

    feedback   사람이 남긴 평가        — 좋다 / 별로다 / 메모
    choice     사람이 고른 것
    response   AI 가 내놓은 것         ← 여기

세 가지 사건이 있다.

    generated   무엇을 넣었더니 어떤 후보들이 나왔나
    written     확정값을 넣었더니 어떤 본문·이미지가 나왔나
    failed      만들지 못했다

문서와 얽힌 행에는 doc(문서 id)이 붙는다. 쪽 고르기가 그렇다. 같은 id 로
choice/ 의 uploaded 행과 이어지므로, "이 파일을 넣었더니 모델이 이 쪽들을
골랐다" 가 조인 없이 한눈에 읽힌다.

행마다 raw 가 붙는다. 모델이 보낸 응답 원문이다. options·output 에는 검증을
통과한 것만 남으므로, 버려진 후보나 못 쓴 도식이 어디에도 안 남는다.
"왜 이게 안 보이나" 를 나중에 알려면 원문이 있어야 한다. 파싱이 깨졌을 때는
더 그렇다 — 실패 사유만으로는 무엇이 왔는지 알 수 없다.
프롬프트를 고칠 근거이고, 나중에 분류 파인튜닝 데이터로도 쓴다.

행을 만드는 일은 여기 한 곳에만 있다. 부르는 곳은 다섯이다.

    session._record_topic   1단계. 시트에서 온 목록 (source="sheet")
    options.options         2~7단계 후보 생성
    options._fill           직접 쓴 한 줄에서 부속 항목 채우기
    session.write           본문 작성
    output.hero.make        대표 이미지
"""

from . import log

STREAM = "response"


def generated(sid: str, step: str, inp: dict, items: list[dict],
              model: str, source: str, refresh: bool, ms: int,
              raw: str = "", doc: str = "") -> None:
    """후보를 만들었다.

    입력과 후보를 통째로 남긴다. 후보 id 는 세션 한정 임시 번호라
    나중에 p0 가 무엇이었는지 알 길이 없기 때문이다.
    """
    log.write(STREAM, kind="generated", sid=sid, step=step,
              source=source, model=model, refresh=refresh, ms=ms,
              input=inp, options=items, raw=raw,
              **({"doc": doc} if doc else {}))


def written(sid: str, inp: dict, out: dict, model: str, ms: int,
            step: str = "write", raw: str = "") -> None:
    """한 벌을 만들었다. 무엇을 넣었더니 무엇이 나왔나.

    본문과 대표 이미지가 여기 온다. 둘 다 후보를 고르는 단계가 아니라 나온
    그대로 나가므로, 프롬프트를 고칠 근거가 이 한 줄뿐이다. 입력과 출력을
    통째로 남긴다.
    """
    log.write(STREAM, kind="written", sid=sid, step=step,
              model=model, ms=ms, input=inp, output=out, raw=raw)


def failed(sid: str, step: str, inp: dict, reason: str, ms: int,
           raw: str = "", doc: str = "") -> None:
    """만들지 못했다.

    실패가 로그에 안 남으면 무엇이 왜 안 나왔는지 알 길이 없다. 화면에는
    이유가 뜨지만 그건 그 순간뿐이고, 나중에 프롬프트를 고칠 때 필요한 것은
    "이 입력을 줬더니 이렇게 실패했다"는 기록이다.
    """
    log.write(STREAM, kind="failed", sid=sid, step=step,
              reason=reason, ms=ms, input=inp, raw=raw,
              **({"doc": doc} if doc else {}))


def read(day: str | None = None) -> list[dict]:
    return log.read(STREAM, day)
