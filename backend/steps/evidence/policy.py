"""근거의 최종 상태를 정한다.

**`supported` 는 모델이 쓰지 않는다.** 모델이 자기 출력에 "이건 사실이다"
라고 적으면 그건 검증이 아니라 주장이다. 그래서 역할을 가른다.

    LLM     의미가 대응하는가(`verdict`) + 원문의 어느 대목인가(`evidence_spans`)
    코드    원문이 실제로 있는가 + 인용한 대목이 원문에 실제로 있는가 → 상태

## 왜 참·거짓이 아닌가

부분적으로만 뒷받침되는 주장과 완전히 틀린 주장은 다르다. 참·거짓으로 두면
본문 작성이 "범위를 줄여 조건을 붙여 쓰기" 를 못 한다.

    supported       그대로 쓴다
    partial         범위를 좁히고 조건을 붙여 쓴다
    contradicted    쓰지 않는다
    unverified      확인 대상으로만 둔다
    invalid_check   검증이 어긋났다. 한 번 다시 묻는다

## 인용 대조는 정규화한 다음에 한다

원문 그대로 비교하면 **정상 인용도 걸린다.** pypdf 는 하이픈 분철을 남기고,
웹 본문에는 `&nbsp;` 와 유니코드 따옴표가 섞이고, 모델이 인용을 옮기면서
공백 하나를 흘린다. 그래서 공백을 접고 따옴표를 통일한 뒤에 찾는다.

여기는 record 말고 아무것도 import 하지 않는다.
"""

import re
import unicodedata

# ── 상한 ──────────────────────────────────────────────────────
#
# 상한이 없으면 프롬프트가 claim 을 열둘 내는 날 그대로 터진다. claim 마다
# 질의를 만들고 결과마다 본문을 가져오고 쌍마다 대조하므로, 곱이 그대로
# 호출 수가 된다.
#
# 넘쳐서 못 본 것은 버리지 않고 unverified 로 남긴다. 조용히 사라지면
# 왜 근거가 없는지 알 수 없다.

MAX_CLAIMS = 6       # searchable 인 것 중 검증에 태울 수
MAX_QUERIES = 2      # claim 당 질의
MAX_FETCH = 2        # 질의당 본문 가져오기
MAX_CHECKS = 12      # claim × source 대조 총합

# 올린 문서는 따로 센다. 검색 결과와 같은 예산을 쓰면 문서 하나가 검색
# 근거를 다 밀어낸다 — 문서가 있다고 검색을 안 해도 되는 것이 아니다.
MAX_DOCUMENT_CLAIMS = 2   # 문서 하나가 걸릴 수 있는 명제 수
MAX_PDF_PER_CLAIM = 1     # 명제 하나에 붙일 문서 수
MAX_PDF_CHECKS = 4        # 문서 대조 쌍 총합

# 어느 명제부터 문서를 붙일지. 공식 원문이 필요한 것이 먼저다.
CLAIM_ORDER = {t: i for i, t in enumerate(
    ("regulation", "fact", "interpretation", "inference"))}

# invalid_check 재시도. 상한이 없으면 같은 인용으로 무한히 돈다.
MAX_RETRY = 1

# ── 값 목록 ───────────────────────────────────────────────────

CLAIM_TYPES = ("fact", "regulation", "interpretation", "inference")

# 모델이 내는 판정. 최종 상태와 이름이 겹치지 않게 둔다 — 겹치면 어느 쪽이
# 코드가 정한 값인지 로그만 보고 가릴 수 없다.
VERDICTS = ("supported", "partial", "contradicted", "insufficient")

STATUSES = ("supported", "partial", "contradicted", "unverified", "invalid_check")

# 출처 성격. 프롬프트에 기관명을 박지 않기 위해 성격으로 프레이밍한다.
SOURCE_TARGETS = ("official_primary", "domestic_official", "standards",
                  "research", "secondary")

# 어느 성격을 먼저 가져올지. 본문 가져오기가 비싸서 순서가 곧 예산이다.
PRIORITY = {t: i for i, t in enumerate(SOURCE_TARGETS)}

# ── 출처의 자격 ───────────────────────────────────────────────
#
# 의미가 대응하는 것과 **그 출처가 그 말을 할 자격이 있는가**는 다른 문제다.
# 언론 기사가 법령을 정확히 요약했더라도 그 기사는 법령이 아니다.
#
# 두 축을 나누는 이유는 하나로 접으면 정보를 버리기 때문이다. "규정 명제는
# 공식 원문 아니면 미확인" 으로 두면, 공식 원문을 못 찾은 날 본문이 아무것도
# 단정하지 못하고 근거 없는 글이 나온다. 대신 상태는 살려 두고 **표현 강도를
# 낮춘다** — "규정이 정한다" 대신 "◯◯ 보도에 따르면".

AUTHORITY = ("sufficient", "limited", "insufficient")

# claim_type → 그 말을 할 자격이 있는 출처 성격.
#   충분    그 성격이면 공식 표현을 써도 된다
#   제한적  쓸 수 있지만 어디서 온 말인지 밝힌다
ENOUGH = {
    "regulation":     {"official_primary"},
    "fact":           {"official_primary", "domestic_official", "standards"},
    "interpretation": {"official_primary", "domestic_official", "standards", "research"},
    "inference":      set(SOURCE_TARGETS),
}
LIMITED = {
    "regulation":     {"domestic_official", "standards"},
    "fact":           {"research"},
    "interpretation": set(),
    "inference":      set(),
}


def authority_of(claim_type: str, targets) -> str:
    """이 명제를 뒷받침한 출처들이 그 말을 할 자격이 있는가."""
    got = {t for t in targets if t}
    if got & ENOUGH.get(claim_type, set()):
        return "sufficient"
    if got & LIMITED.get(claim_type, set()):
        return "limited"
    return "insufficient"

REASONS = {
    # **"안 찾았다" 와 "찾았는데 없다" 를 가른다.** 뭉쳐 두면 원인을 고칠
    # 수 없다 — 키를 안 넣은 것인지, 검색이 실패한 것인지, 정말 자료가
    # 없는 것인지가 화면에서 똑같이 보인다.
    "search_disabled": "근거 검색이 꺼져 있습니다 (TAVILY_API_KEY 없음)",
    "no_search_result": "검색했지만 쓸 만한 자료가 없습니다",
    "no_source": "뒷받침할 원문을 찾지 못했습니다",
    "fetch_failed": "원문을 가져오지 못했습니다",
    "check_limit_exceeded": "확인할 것이 많아 이 항목까지 보지 못했습니다",
    "not_searchable": "검색으로 확인할 수 있는 주장이 아닙니다",
    "document_check_limit_exceeded": "올린 문서를 이 항목까지 대조하지 못했습니다",
}

# 화면에 나가는 말. **내부 이름을 그대로 보이지 않는다** — 사람은
# `authority` 나 `insufficient` 가 무엇인지 알 이유가 없다.
AUTHORITY_LABELS = {
    "sufficient": "공식 근거 있음",
    "limited": "보조 근거",
    "insufficient": "공식 근거 부족",
}


# ── 인용 대조 ─────────────────────────────────────────────────

_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"',
                         "\u201d": '"', "\u2013": "-", "\u2014": "-"})


def norm(t: str) -> str:
    """대조하기 전에 다듬는다.

    자간·줄바꿈·따옴표 모양이 달라 정상 인용이 걸리는 것을 막는다.
    분철 하이픈(`require-\\nment`)은 붙여 읽는다.
    """
    t = unicodedata.normalize("NFKC", t or "")
    t = t.translate(_QUOTES)
    t = re.sub(r"-\s*\n\s*", "", t)          # 줄 끝 분철
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def span_ok(quote: str, source_text: str) -> bool:
    """인용한 대목이 원문에 실제로 있는가.

    너무 짧은 인용은 우연히 맞는다. 그것을 근거로 삼으면 아무 문장이나
    통과하므로 길이를 본다.
    """
    q = norm(quote)
    if len(q) < 12:
        return False
    return q in norm(source_text)


# ── 상태 계산 ─────────────────────────────────────────────────

def verdict_of(got: dict) -> str:
    v = str((got or {}).get("verdict") or "")
    return v if v in VERDICTS else "insufficient"


def status_of(got: dict, source_text: str) -> tuple[str, str]:
    """대조 결과 하나 → (상태, 사유 코드).

    **`supported` 는 인용이 원문에 실제로 있을 때만 나온다.** 모델이
    뒷받침된다고 해도 인용한 대목을 원문에서 못 찾으면 그건 검증이 어긋난
    것이고, 그대로 통과시키면 지어낸 인용에 출처가 붙는다.
    """
    if not (source_text or "").strip():
        return "unverified", "no_source"

    v = verdict_of(got)
    if v == "contradicted":
        return "contradicted", ""
    if v == "insufficient":
        return "unverified", "no_source"

    spans = [s for s in (got.get("evidence_spans") or [])
             if isinstance(s, dict) and s.get("quote")]
    if not spans:
        return "invalid_check", ""
    if not all(span_ok(s["quote"], source_text) for s in spans):
        return "invalid_check", ""

    return ("supported" if v == "supported" else "partial"), ""


def best(statuses) -> str:
    """한 claim 에 여러 출처가 붙었을 때의 최종 상태.

    가장 좋은 것을 취한다 — 출처 하나가 뒷받침하면 그 주장은 뒷받침된다.
    다만 **반박이 있으면 그것이 이긴다.** 하나가 틀렸다고 하는데 다른 하나가
    맞다고 해서 쓰면, 반박을 못 본 척하는 글이 된다.
    """
    rows = list(statuses)
    if not rows:
        return "unverified"
    if "contradicted" in rows:
        return "contradicted"
    for s in ("supported", "partial", "invalid_check"):
        if s in rows:
            return s
    return "unverified"


# 검증을 못 해 본 사유. 이때는 미확인이어도 고를 수 있다 — 아래 참고.
UNTRIED = ("search_disabled", "check_limit_exceeded",
           "document_check_limit_exceeded")


def selectable(claim: dict) -> bool:
    """사람이 이 주장을 골라 본문에 쓸 수 있는가.

    **판단이 여기 한 곳에 있다.** 근거 카드·구조 단계·확정 경로·화면이 같은
    질문을 하는데, 따로 적으면 곧바로 어긋난다 — `is_confirmed()` 가 두 곳에
    흩어졌다가 올린 PDF 가 인용은 되면서 라벨에는 "확인 필요" 로 세어진 적이
    있고, 화면이 상태를 다시 해석하다가 미확인 추론을 전부 막은 적도 있다.

    미확인이라도 고를 수 있는 경우가 둘이다.

    ① **추론.** 원문으로 확인되는 종류가 아니다. 본문이 추론임을 밝히고 쓴다.
    ② **검증을 못 해 본 것.** 검색이 꺼져 있거나 상한에 걸려 **시도조차
       안 한** 명제다. 이것까지 막으면 키가 없는 날 고를 수 있는 근거가
       하나도 없어 사람이 막다른 길에 놓인다. "찾아봤는데 없다" 와
       "안 찾아봤다" 는 다르다.

    인용은 여전히 못 한다(`citable`). 확인 안 된 것에 출처가 붙는 것이
    이 파이프라인의 오래된 실패다.
    """
    st = claim.get("status", "")
    if st in ("supported", "partial"):
        return True
    if st != "unverified":
        return False
    return (claim.get("claim_type") == "inference"
            or claim.get("reason_code") in UNTRIED)


def citable(claim: dict) -> bool:
    """본문이 이 주장에 출처를 달 수 있는가.

    고를 수 있는 것과 인용할 수 있는 것은 다르다. 추론은 골라 쓸 수 있지만
    원문이 없으므로 출처를 달면 안 된다 — 확인되지 않은 것에 출처가 붙은
    글이 이 파이프라인의 오래된 실패다.

    **자격은 여기서 보지 않는다.** 자격이 모자라도 인용은 한다. 다만 본문이
    "규정이 정한다" 가 아니라 "◯◯ 보도에 따르면" 으로 쓴다. 자격으로 인용을
    막으면 근거를 붙이려다 근거 없는 글이 나온다.
    """
    return claim.get("status", "") in ("supported", "partial")


def rank_claim(claim: dict) -> tuple:
    """문서를 어느 명제부터 붙일지."""
    return (CLAIM_ORDER.get(claim.get("claim_type", ""), 9),)


def rank(source: dict) -> tuple:
    """본문을 어느 것부터 가져올지.

    **실제 성격**으로 줄 세운다. 계획이 원한 성격(`requested_target`)으로
    세우면 공식 원문을 노린 질의에 걸린 기사가 맨 앞에 온다 — 원했던 것이지
    걸린 것이 아니다.
    """
    return (PRIORITY.get(source.get("actual_target", ""), len(PRIORITY)),
            -float(source.get("score") or 0))
