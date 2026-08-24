"""근거 검색.

여기만 Tavily 를 안다. 질의 하나를 받아 결과 목록을 돌려주고, URL 하나를
받아 본문 글자를 돌려주는 것이 전부다. 무엇을 검색할지·무엇을 믿을지는
근거 단계가 안다.

`external/openai.py` 와 같은 층이다. 회사를 갈아탈 때 고칠 곳을 한 파일로
묶고, 우리 오류 분류를 모른 채 `CallError` 만 올린다.

## 스니펫으로 판정하지 않는다

검색 결과에 딸려 오는 스니펫은 앞뒤 조건이 잘리고, 검색어가 든 문장만
강조되며, 검색엔진이 만든 요약일 수도 있다. 그것으로 "이 주장이 뒷받침된다"
를 판정하면 PDF 앞부분만 잘라 쓰던 것과 같은 실패다.

그래서 스니펫은 **어느 것을 가져올지 고르는 데만** 쓰고, 판정은 본문을
가져온 뒤에 한다. 못 가져오면 그 출처는 미확인으로 남는다.
"""

import json
import re
import urllib.error
import urllib.request
from html import unescape

from .. import config

API_KEY = config.TAVILY_API_KEY
ENABLED = bool(API_KEY)

SEARCH_URL = "https://api.tavily.com/search"
EXTRACT_URL = "https://api.tavily.com/extract"

TIMEOUT = 30

# 한 질의가 받아 오는 결과 수. 이 중에서 우선순위로 골라 본문을 가져온다.
PER_QUERY = 6

# 본문 하나에서 들고 갈 글자 수. 대조 프롬프트에 실린다.
MAX_TEXT = 12000


class CallError(Exception):
    """호출이 실패했다. 네트워크·인증·한도 전부 여기로."""


def _post(url: str, body: dict) -> dict:
    if not ENABLED:
        raise CallError("TAVILY_API_KEY 가 없다")
    req = urllib.request.Request(
        url,
        data=json.dumps({**body, "api_key": API_KEY}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise CallError(f"{e.code} {e.reason}") from e
    except Exception as e:
        raise CallError(str(e)) from e


def search(query: str, language: str = "ko") -> list[dict]:
    """질의 하나. [{title, url, snippet, score}]

    본문은 여기서 안 가져온다. 결과마다 가져오면 한 질의에 여섯 번을 더
    부르게 되고, 그중 대부분은 쓰지 않는다. 무엇을 가져올지는 부르는 쪽이
    우선순위로 고른다.
    """
    got = _post(SEARCH_URL, {
        "query": query,
        "max_results": PER_QUERY,
        "search_depth": "advanced",
        # 답을 만들어 달라고 하지 않는다. 우리가 원하는 것은 원문이지
        # 검색엔진이 요약한 문장이 아니다.
        "include_answer": False,
        "include_raw_content": False,
    })
    out = []
    for r in got.get("results") or []:
        url = str(r.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        out.append({
            "title": str(r.get("title") or "")[:200],
            "url": url,
            "snippet": str(r.get("content") or "")[:500],
            "score": float(r.get("score") or 0),
            "language": language,
        })
    return out


def plain_fetch(url: str) -> str:
    """키 없이 웹 페이지 본문. 태그를 걷어 낸 글자만.

    **주소를 이미 알고 있을 때 쓴다.** 소재에 딸려온 기사가 그렇다 —
    검색으로 다시 찾을 이유가 없고, 검색 키가 없어도 가져올 수 있어야 한다.

    거친 방식이다. 로그인·자바스크립트로 그리는 페이지는 못 읽고, 메뉴나
    광고 글자가 섞인다. 그래도 **주소만 있고 본문이 없어 근거로 못 쓰는
    것보다는 낫다** — 대조는 LLM 이 하므로 잡글이 섞여도 판단은 된다.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; blogstudio/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(2_000_000)
            enc = r.headers.get_content_charset() or "utf-8"
    except Exception as e:
        raise CallError(str(e)) from e

    html = raw.decode(enc, errors="replace")
    # 스크립트·스타일을 통째로 걷고 태그를 턴다.
    html = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if len(text) < 200:
        raise CallError("본문이 너무 짧다 (자바스크립트로 그리는 쪽일 수 있다)")
    return text[:MAX_TEXT]


def fetch(url: str) -> str:
    """본문 글자. 못 가져오면 CallError.

    판정에 쓰는 것은 이것뿐이다. 스니펫은 여기 안 섞는다 — 섞으면 어느
    문장이 원문에서 온 것인지 나중에 가릴 수 없다.
    """
    got = _post(EXTRACT_URL, {"urls": [url]})
    rows = got.get("results") or []
    if not rows:
        fail = (got.get("failed_results") or [{}])[0]
        raise CallError(str(fail.get("error") or "본문을 가져오지 못했다"))
    text = str(rows[0].get("raw_content") or "").strip()
    if not text:
        raise CallError("본문이 비어 있다")
    return text[:MAX_TEXT]
