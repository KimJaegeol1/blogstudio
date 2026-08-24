"""OpenAI 호출.

여기만 OpenAI 를 안다. 모델 이름을 받아 문자열 하나를 돌려주는 것이 전부다.
어느 단계가 어느 모델을 쓰는지, 응답을 어떻게 읽는지는 llm.py 가 안다.

층을 나눈 이유는 회사를 갈아탈 때 고칠 곳을 한 파일로 묶기 위해서다.
다른 회사로 옮기면 이 파일만 새로 쓰고 llm.py 는 그대로 둔다.

여기는 우리 오류 분류를 모른다. 실패는 CallError 로만 올리고,
그것을 LLMError 로 바꾸는 일은 부르는 쪽이 한다.
"""

import json

from .. import config

API_KEY = config.OPENAI_API_KEY
ENABLED = bool(API_KEY)


class CallError(Exception):
    """호출이 실패했다. 네트워크·인증·한도 전부 여기로."""


def chat(model: str, system: str, payload: dict) -> str:
    """시스템 메시지와 입력을 보내고 응답 본문 문자열을 받는다.

    JSON 하나만 받도록 response_format 을 건다. 프롬프트로도 금지하지만
    양쪽에서 막는 편이 낫다.
    """
    if not ENABLED:
        raise CallError("OPENAI_API_KEY 가 없다")

    try:
        from openai import OpenAI
    except ImportError as e:            # 키 없이 쓸 땐 설치도 필요 없다
        raise CallError("openai 패키지가 없다. pip install -r requirements.txt") from e

    try:
        res = OpenAI(api_key=API_KEY).chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
    except Exception as e:
        raise CallError(f"{model} 호출 실패: {e}") from e

    return res.choices[0].message.content or ""
