"""프롬프트 원문 읽기.

프롬프트는 .md 파일이다. 코드에 문자열로 박지 않는다 — 프롬프트를 고치는
일과 코드를 고치는 일은 주기가 다르고, 파일이면 서버를 껐다 켜지 않아도
다음 호출부터 반영된다.

파일이 어디 있는지는 **등록해서** 안다. 이름에서 경로를 규칙으로 유추하면
(reader → steps/reader/prompt.md) 오타가 났을 때 다음 규칙으로 조용히
흘러가거나 엉뚱한 파일을 집는다. 등록해 두면 없는 이름은 그 자리에서 터진다.

등록은 각 단계 폴더가 import 될 때 steps/__init__.py 가 한다. output/ 의
write·hero 도 자기 프롬프트를 등록한다.

_common.md 는 모든 프롬프트 뒤에 자동으로 붙는다. 사실성 규칙과 출력 규칙은
여덟 파일에 똑같이 들어가야 하는 것이라, 복붙해 두면 한 곳만 고치고 나머지를
잊는다. 뒤에 붙이는 이유는 마지막에 읽은 규칙이 더 잘 지켜지기 때문이다.
어느 단계에도 속하지 않으므로 prompts/ 에 그대로 남는다.

여기는 paths 말고 아무것도 import 하지 않는다.
"""

from pathlib import Path

from . import paths

COMMON = "_common"

# 이름 → 파일 경로. register() 로만 채운다.
REGISTRY: dict[str, Path] = {COMMON: paths.PROMPTS / f"{COMMON}.md"}

# 이름 → 그 앞에 깔리는 공통 원문. 채널마다 프롬프트가 갈릴 때 쓴다.
#
# 본문 작성 프롬프트는 360줄인데 채널 차이는 그중 문단 길이·말투·도입부
# 정도다. 통째로 복제하면 한쪽만 고쳐지고 그 어긋남은 조용히 지나간다 —
# sanitize 를 한 곳에 모은 것과 같은 문제다. 그래서 공통을 밑에 깔고 채널
# 파일은 차이만 적는다.
BASE: dict[str, Path] = {}


class MissingPrompt(Exception):
    """등록되지 않았거나 파일이 없다."""


def register(name: str, path: Path, base: Path | None = None) -> None:
    """프롬프트 하나를 이름에 붙인다.

    같은 이름을 두 번 등록하면 막는다. 단계를 복사해 만들다가 key 를 안
    바꾸면 뒤엣것이 앞엣것을 덮어쓰고, 그러면 엉뚱한 프롬프트가 도는데
    아무 데도 티가 안 난다.
    """
    if name in REGISTRY and REGISTRY[name] != path:
        raise ValueError(f"프롬프트 이름이 겹친다: {name}")
    REGISTRY[name] = Path(path)
    if base is not None:
        BASE[name] = Path(base)


def where(name: str) -> Path:
    f = REGISTRY.get(name)
    if f is None:
        raise MissingPrompt(f"등록되지 않은 프롬프트: {name}")
    if not f.exists():
        raise MissingPrompt(f"프롬프트 파일이 없다: {f}")
    return f


_cache: dict[str, str] = {}


def read(name: str) -> str:
    """파일 하나. 고쳐지면 다시 읽는다. 서버를 껐다 켤 필요가 없다."""
    f = where(name)
    stamp = f"{f.stat().st_mtime_ns}"
    if _cache.get(name + ":stamp") != stamp:
        _cache[name] = f.read_text(encoding="utf-8").strip()
        _cache[name + ":stamp"] = stamp
    return _cache[name]


def _text(f: Path) -> str:
    """파일 하나. 고쳐지면 다시 읽는다."""
    key = str(f)
    stamp = f"{f.stat().st_mtime_ns}"
    if _cache.get(key + ":stamp") != stamp:
        _cache[key] = f.read_text(encoding="utf-8").strip()
        _cache[key + ":stamp"] = stamp
    return _cache[key]


def build(name: str) -> str:
    """공통 밑바탕 + 단계 프롬프트 + 공통 규칙.

    순서가 뜻을 갖는다. 밑바탕이 먼저 오고 그 위에 채널 차이가 얹힌다 —
    뒤에 읽은 것이 더 잘 지켜지므로 겹치는 규칙은 채널 쪽이 이긴다.
    맨 뒤 공통 규칙(사실성·출력 형식)은 어느 쪽도 못 뒤집는다.
    """
    body = read(name)
    if name == COMMON:
        return body
    base = BASE.get(name)
    if base is not None:
        if not base.exists():
            raise MissingPrompt(f"밑바탕 프롬프트가 없다: {base}")
        body = f"{_text(base)}\n\n---\n\n{body}"
    return f"{body}\n\n---\n\n{read(COMMON)}"


def names() -> list[str]:
    """등록된 프롬프트 전부. /api/health 와 테스트가 쓴다."""
    return sorted(REGISTRY)
