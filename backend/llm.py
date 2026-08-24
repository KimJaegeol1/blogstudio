"""프롬프트를 보내고 JSON 을 받는다.

세 조각을 조립하는 자리다. 셋 다 이 파일에 있던 것을 갈라낸 것이다.

    config.py            키와 모델 이름
    prompt.py            프롬프트 원문
    external/openai.py   실제 호출

여기가 아는 것은 "어느 단계가 어느 등급을 쓰는가"와 "받은 것을 어떻게
믿을 것인가"다. 부르는 쪽은 generate() 와 candidates() 만 안다.

어느 단계가 상위 등급을 쓰는지는 그 단계 폴더가 들고 있고(Step.strong),
여기는 등급을 모델 이름으로 바꾸기만 한다. 호출하는 쪽은 모델 이름을
고르지 않는다 — 고르게 두면 판단이 여기저기 흩어진다.
"""

import json

from . import config, prompt as prompts
from .external import openai as api

MODEL = config.OPENAI_MODEL
MODEL_STRONG = config.OPENAI_MODEL_STRONG

ENABLED = api.ENABLED

def model_for(strong: bool = False) -> str:
    """등급으로 모델을 고른다.

    등급은 그 단계가 무엇을 결정하느냐에 달린 성질이라 단계 쪽이 들고 있고,
    모델 이름은 설정이라 config 가 들고 있다. 여기는 둘을 잇기만 한다.
    등급을 넘기는 것과 모델 이름을 고르는 것은 다르다 — 부르는 쪽은 여전히
    "gpt-..." 를 모른다.

    어느 단계가 상위 등급인지는 steps/*/ 의 Step.strong 과 output/ 의
    호출부에 있다. 전체 매핑은 /api/health 에서 한눈에 볼 수 있다.

    나머지 단계는 후보를 여러 개 내고 사람이 그중 하나를 고른다. 몇 개가
    시원찮아도 나머지에서 고르면 되니 모델이 조금 약해도 버틴다.
    구조는 다르다. 글 전체의 뼈대라 잘못 잡히면 뒤가 전부 흔들리고,
    사람이 소제목 목록만 보고 좋은지 나쁜지 판단하기도 어렵다.
    본문은 고를 여지 없이 나온 그대로 나간다.
    """
    return MODEL_STRONG if strong else MODEL


class LLMError(Exception):
    """호출이나 응답이 쓸 수 없는 상태. 감추지 않고 화면까지 올린다."""


# 프롬프트 이름별 마지막 응답 원문.
#
# 자취에는 검증을 통과한 값만 남는다. 그러면 "왜 이 후보가 안 보이나",
# "도식이 왜 버려졌나" 를 나중에 알 수 없다 — 버려진 것은 어디에도 없기
# 때문이다. 원문을 여기 두고 부르는 쪽이 자취 행에 실어 보낸다.
LAST: dict[str, str] = {}

RAW_MAX = 20000

COMMON = prompts.COMMON


def prompt(name: str) -> str:
    """단계 프롬프트 + 공통 규칙. prompt.py 가 읽는다."""
    return prompts.build(name)


def generate(name: str, payload: dict, strong: bool = False) -> dict:
    """프롬프트 하나를 보내고 JSON 객체 하나를 받는다."""
    if not ENABLED:
        raise LLMError("OPENAI_API_KEY 가 없다")

    model = model_for(strong)
    try:
        system = prompt(name)
    except prompts.MissingPrompt as e:
        raise LLMError(str(e)) from e

    try:
        text = api.chat(model, system, payload)
    except api.CallError as e:
        LAST.pop(name, None)
        raise LLMError(f"{name} {e}") from e

    LAST[name] = text[:RAW_MAX]
    return parse(text)


def raw(name: str) -> str:
    """그 프롬프트의 마지막 응답 원문. 없으면 빈 문자열."""
    return LAST.get(name, "")


def parse(text: str) -> dict:
    """프롬프트로 금지해도 코드 펜스를 붙여 오는 일이 있다. 벗겨서 읽는다."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        out = json.loads(t)
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON 이 아니다: {e}") from e
    if not isinstance(out, dict):
        raise LLMError("객체가 아니라 다른 게 왔다")
    return out


def candidates(name: str, payload: dict, required: tuple[str, ...],
               strong: bool = False) -> list[dict]:
    """후보 목록을 받는다. 필수 필드가 빈 항목은 버린다.

    LLM 출력은 검증 없이 믿지 않는다. 여기서 거르지 않으면 뒤쪽
    payload 빌더가 KeyError 로 터지거나, 빈 카드가 화면에 나간다.
    """
    out = generate(name, payload, strong).get("candidates")
    if not isinstance(out, list):
        raise LLMError(f"{name}: candidates 배열이 없다")

    good = [c for c in out
            if isinstance(c, dict) and all(_filled(c.get(k)) for k in required)]
    if not good:
        raise LLMError(f"{name}: 쓸 수 있는 후보가 없다 (받은 것 {len(out)}개)")
    return good


def _filled(v) -> bool:
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return bool(v)
    return v is not None
