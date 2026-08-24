"""지금 돌고 있는 코드가 무엇인지 알려 준다.

파일을 바꿨는데 화면이나 로그가 그대로일 때, 원인이 코드인지 실행인지
구별할 방법이 없으면 시간을 다 쓴다. 실제로 세 번 겪었다 — 압축이 옛것이었을
때, 브라우저가 css 를 캐시했을 때, 서버가 옛 모듈을 들고 있었을 때.

그래서 소스 파일 내용으로 짧은 지문을 만들어 /api/health 에 실어 보낸다.
숫자가 기대한 것과 다르면 코드가 안 바뀐 게 아니라 **안 돌고 있는** 것이다.

무거운 일이 아니다. 서버가 뜰 때 한 번만 읽는다.
"""

import hashlib

from . import paths

BACKEND = paths.BACKEND
FRONTEND = paths.FRONTEND


def _fingerprint(files) -> str:
    """내용 해시의 앞 8자리. 파일 하나만 바뀌어도 값이 달라진다."""
    h = hashlib.sha256()
    for f in sorted(files):
        if "__pycache__" in f.parts:
            continue
        h.update(str(f.relative_to(BACKEND.parent)).replace("\\", "/").encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:8]


# 코드와 내용을 나눈다.
#
# 한 덩이로 두면 프롬프트 한 글자만 고쳐도 값이 바뀐다. 그러면 "코드가
# 업데이트됐나" 를 이 값으로 판별할 수 없다. 프롬프트는 자주 고치는 것이고
# 코드는 배포할 때만 바뀌므로, 묻는 질문이 다르다.
CODE = _fingerprint(BACKEND.rglob("*.py"))
CONTENT = _fingerprint(
    list(BACKEND.rglob("*.md")) + list(FRONTEND.rglob("*.js"))
    + list(FRONTEND.rglob("*.css")))

BUILD = CODE          # 예전 이름. 코드 지문을 가리킨다.

def hooks() -> dict:
    """로그가 남는 자리가 실제로 걸려 있는지 센다.

    파일 이름을 짚지 않고 트리를 훑는다. 이름을 박아 두면 파일을 옮기는
    순간 조용히 깨진다 — 실제로 한 번 깨졌다.
    """
    src = "".join(
        f.read_text(encoding="utf-8")
        for f in BACKEND.rglob("*.py") if "__pycache__" not in f.parts)
    return {
        "topic": src.count("_record_topic("),
        "generated": src.count("rec.generated("),
        "confirmed": src.count("rec_choice.confirmed("),
        "written": src.count("rec.written("),
        "failed": src.count("rec.failed("),
    }
