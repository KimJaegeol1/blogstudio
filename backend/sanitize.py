"""값 다듬기.

단계가 폴더로 갈리면서 제일 먼저 복제될 위험이 있는 것들이다. `_s` 하나가
여섯 폴더에 복사되면 정리한 게 아니라 망가뜨린 것이다 — 자르는 길이가
달라지거나 한쪽만 고쳐지고, 그런 어긋남은 예외 없이 조용히 지나간다.

LLM 출력을 그대로 믿지 않는 것이 이 모듈의 목적이다. 문자열 자리에 객체가
오고, 배열 자리에 null 이 섞이고, 정해 둔 값 밖의 표기가 온다. 여기서 걸러야
뒤쪽 빌더가 KeyError 로 터지거나 빈 카드가 화면에 나가는 일이 없다.

여기는 아무것도 import 하지 않는다.
"""


def s(v, n=999) -> str:
    """문자열 한 칸. 앞뒤를 털고 길이를 자른다."""
    return (v or "").strip()[:n] if isinstance(v, str) else str(v or "").strip()[:n]


def lines(v, n=120, cap=5) -> list[str]:
    """문자열 목록 한 칸. 빈 것과 넘치는 것을 걷어낸다.

    문자열이 아닌 항목은 통째로 버린다. 문자열로 바꿔 담으면 LLM 이 객체를
    섞어 보냈을 때 "{'title': ...}" 같은 것이 화면에 그대로 나간다.
    """
    if not isinstance(v, list):
        return []
    out = [s(x, n) for x in v if isinstance(x, str)]
    return [x for x in out if x][:cap]


def texts(v, n=99) -> list[str]:
    """문자열 목록. lines 와 달리 항목 길이를 자르지 않고 개수만 본다."""
    if not isinstance(v, list):
        return []
    return [s(x) for x in v if isinstance(x, str) and s(x)][:n]


def enum(v, allowed) -> str:
    """정해 둔 값 중 하나. 밖이면 빈 문자열.

    프롬프트에 "이 값만 쓴다" 를 적어 두어도 다른 표기가 온다. 그것을
    그대로 확정값에 넣으면 뒤 단계 규칙이 조용히 죽는다.
    """
    v = s(v)
    return v if v in allowed else ""


# 낱말 앞 몇 글자로 볼지. 한국어는 조사와 어미가 붙으므로 앞부분만 본다.
STEM = 3


def stems(text: str) -> set:
    """낱말의 앞부분. 조사·어미를 떼려는 것이다.

    "적용되었다" 와 "적용된다", "수입품의" 와 "수입품에" 를 같게 만든다.
    같은 것을 두 번 세지 않으려고 여러 곳이 쓴다 — 명제가 같은지, 섹션이
    같은 내용을 다루는지.
    """
    out = set()
    for w in " ".join((text or "").split()).lower().split():
        if len(w) < 2:
            continue
        # 낱말이 짧으면 어미를 떼면 남는 게 없다. "정의" 와 "정의가" 는
        # 앞 3글자가 다른데 같은 말이다. 짧은 쪽에 맞춰 자른다.
        out.add(w[:min(STEM, max(2, len(w) - 1))])
    return out


def overlap(a: str, b: str) -> float:
    """두 글이 얼마나 겹치나. 0~1."""
    x, y = stems(a), stems(b)
    if not x or not y:
        return 0.0
    return len(x & y) / max(len(x), len(y))
