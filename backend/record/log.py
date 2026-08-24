"""줄 단위 로그.

쌓아 두는 기록이 두 갈래다.

    feedback/   사람이 남긴 평가 — 좋음·별로·메모
    trail/      저절로 쌓이는 자취 — 무엇을 넣었더니 무엇이 나왔고, 무엇을 골랐나

쓰는 방식은 같으므로 여기 한 번만 적는다. 갈래마다 파일을 따로 두면
"하루에 한 파일, 한 줄에 한 건, 실패해도 안 막음" 을 두 벌 관리하게 된다.

한 줄에 한 건씩 붙여 쓴다(JSON Lines). 통째로 읽고 다시 쓰지 않으므로
중간에 끊겨도 앞부분이 멀쩡하고, 나중에 그대로 읽어 표로 만들 수 있다.
"""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from .. import paths

_announced: set[str] = set()


def where(stream: str) -> Path:
    """이 스트림이 실제로 쓰이는 자리. 절대 경로다.

    폴더를 여러 벌 두고 헷갈리는 일이 잦으므로 밖에서 물어볼 수 있게 연다.
    """
    return paths.stream(stream)


def write(stream: str, **row) -> None:
    """한 건을 오늘 파일에 붙인다.

    쓰기가 실패해도 예외를 올리지 않는다. 기록은 곁가지고, 못 남겼다고
    사람이 하던 작업이 멈추면 안 된다.
    """
    now = datetime.now().astimezone()
    line = {"at": now.isoformat(timespec="seconds"), **row}
    d = where(stream)
    f_path = d / f"{now:%Y-%m-%d}.jsonl"
    try:
        d.mkdir(parents=True, exist_ok=True)
        with f_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
        if stream not in _announced:
            # 첫 기록 때 어디에 쌓이는지 콘솔에 한 번 알린다. 엉뚱한 폴더를
            # 열어 놓고 "안 쌓인다" 하는 일이 없게.
            _announced.add(stream)
            print(f"[log] {stream} 첫 기록 → {f_path}", file=sys.stderr)
    except Exception:
        # 예외를 올리지는 않는다. 기록은 곁가지고, 못 남겼다고 사람이 하던 일이
        # 끊기면 안 된다. 다만 조용히 넘기지도 않는다 — 삼켜 버리면 "왜 로그가
        # 안 쌓이나" 를 알아낼 방법이 없어진다. 서버 콘솔에 이유를 찍는다.
        print(f"[log] {stream} 쓰기 실패 → {d}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


def read(stream: str, day: str | None = None) -> list[dict]:
    """쌓인 것을 읽는다. day 를 안 주면 전부."""
    d = where(stream)
    out = []
    for f in sorted(d.glob(f"{day or '*'}.jsonl")) if d.exists() else []:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass                      # 깨진 줄 하나가 나머지를 막지 않는다
    return out
