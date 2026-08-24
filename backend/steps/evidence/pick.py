"""올린 문서에서 근거로 쓸 구간 고르기.

**앞에서부터 자르면 안 되는 이유가 이 파일의 전부다.**

58쪽 EU 이행규정을 올려서 재 봤다. 앞 6,000자에 들어간 것은 표지와 목차와
전문(Whereas) 아홉 개뿐이었고, 실제로 인용할 조항 — 보고 의무, 요구 정보,
검증 요건 — 은 14,812자·15,106자·30,116자 지점에 있어 하나도 안 들어갔다.
길어서 아쉬운 게 아니라 **가장 쓸모없는 구간을 골라 보내고 있었다.**

그러면 두 가지가 무너진다.

    ① 7단계 프롬프트가 문서를 헛본다. 아는 것이 표지 문구뿐이라 "이미 올린
       것과 겹치지 마라" 를 판단할 수 없고, 방금 올린 규정을 다시
       "규정 원문에서 확인할 것" 으로 내놓는다.
    ② 카드에는 "출처 확인됨" 이 뜨는데 넘어간 것은 전문뿐이다. 모델이 표지
       문구로 그럴듯한 문장을 지으면 **확인된 출처로 표시된 채** 나간다.

## 어떻게 고르나

쪽별 앞머리만 모아 한 번 물어보고 쪽 번호를 받는다. 전문을 다 넣으면 입력이
터지고, 키워드로 코드가 맞추는 방식은 이 도메인에서 못 쓴다 — 글은 한글로
쓰고 근거는 영문 규정인 경우가 흔해 겹치는 낱말이 거의 없다.

**무엇을 기준으로 고르나.** 예전에는 확정된 제목과 소제목을 봤다. 근거가
구조 앞으로 옮겨 오면서 그 신호가 없어져, 지금은 이 글이 답할 질문
(`intent.question` 과 `sub_questions`)과 각도·유형을 본다. 소제목보다 신호가
얇으므로, 긴 문서에서 엉뚱한 쪽을 고르는지 `response/` 의 `evidence_pick`
행으로 확인해야 한다.

**한도 안에 들어가는 문서는 물어보지 않는다.** 첨부 대부분은 몇 쪽짜리
고시나 가이드라 그대로 통과한다. 호출은 긴 문서에만 든다.

## 못 골라도 막지 않는다

실패하면 예전처럼 앞부분으로 떨어지되 이유를 남긴다. 조용히 되돌아가면 왜
엉뚱한 근거가 들어갔는지 나중에 알 방법이 없다.
"""

import pathlib
import time

from ... import llm, prompt as prompts, sanitize as z
from ...record import response as rec
from ..step import label_of, pay
from . import upload

prompts.register("evidence_pick", pathlib.Path(__file__).parent / "pick.md")

NAME = "evidence_pick"

# 쪽마다 보여 줄 앞부분. 규정 문서는 앞머리에 조항 번호와 제목이 있어서
# 이만큼이면 무엇이 실린 쪽인지 갈린다. 상수는 upload 에 있다 — 목록이
# 얼마나 커질지 재는 곳이 거기고, 반대로 두면 순환 import 가 된다.
PEEK = upload.PEEK

# 고를 수 있는 쪽 수 상한. 넘겨도 발췌 한도에서 어차피 잘린다.
MAX_PAGES = 12


def _budget(pages_text, picked) -> tuple[str, list[dict]]:
    """고른 쪽을 발췌 한도 안에서 이어 붙인다.

    쪽 번호를 함께 박아 둔다. 발행 전에 사람이 원문에서 대조할 수 있어야
    하기 때문이다. 본문에는 쪽수를 쓰지 않는다 — 독자가 볼 것이 아니다.
    """
    # 머리글은 문서 전체를 봐야 안다. 쪽 하나만 보면 그게 제목인지
    # 되풀이되는 장식인지 가릴 수 없다.
    skip = upload.headers(pages_text)
    parts, segs, used = [], [], 0
    for n in picked:
        body = pages_text[n - 1]
        if not body:
            continue
        chunk = f"[{n}쪽]\n{body}"
        if used + len(chunk) > upload.EXCERPT:
            room = upload.EXCERPT - used
            if room < 400:              # 토막만 남으면 넣지 않는다
                break
            chunk = chunk[:room]
        parts.append(chunk)
        segs.append({"page": n, "head": upload.head(body)})
        used += len(chunk) + 2
    return "\n\n".join(parts), segs


def _whole(doc) -> dict:
    """한도 안에 들어가는 문서. 물어보지 않고 통째로 쓴다."""
    body, segs = _budget(doc["pages_text"], range(1, doc["pages"] + 1))
    doc["excerpt"] = body
    doc["segments"] = segs
    doc["picked"] = False
    doc["truncated"] = False
    doc["preview"] = z.s(body[:upload.PREVIEW].replace("\n", " "))
    return doc


def _fallback(doc, reason) -> dict:
    """고르지 못했다. 앞부분으로 떨어지되 이유를 남긴다."""
    body, _ = _budget(doc["pages_text"], range(1, doc["pages"] + 1))
    doc["excerpt"] = body
    # 구간은 비운다. 앞부분에 걸린 쪽들은 고른 것이 아니라 그냥 앞이라
    # 걸린 것이다. 이것을 구간으로 남기면 7단계 프롬프트가 표지와 목차를
    # "이 문서가 다루는 것" 으로 읽는다.
    doc["segments"] = []
    doc["picked"] = False
    doc["truncated"] = True
    doc["pick_error"] = reason
    doc["preview"] = z.s(body[:upload.PREVIEW].replace("\n", " "))
    return doc


def narrow(doc, draft) -> dict:
    """문서 하나에서 쓸 구간을 정한다. doc 를 채워서 돌려준다."""
    if doc["chars"] <= upload.EXCERPT:
        return _whole(doc)

    if not llm.ENABLED:
        return _fallback(doc, "OPENAI_API_KEY 가 없어 구간을 고르지 못했습니다")

    it = pay(draft, "intent")
    inp = {
        "topic": label_of(draft, "topic"),
        "question": it.get("question", ""),
        "sub_questions": it.get("sub_questions", []),
        "angle": pay(draft, "angle"),
        "article_type": pay(draft, "type").get("article_type", ""),
        "document": {
            "title": doc["title"],
            "pages": [{"no": i + 1, "head": z.s(t.replace("\n", " "), PEEK)}
                      for i, t in enumerate(doc["pages_text"]) if t],
        },
    }

    sid = draft.get("_sid", "")
    t0 = time.perf_counter()
    try:
        got = llm.generate(NAME, inp)
    except llm.LLMError as e:
        rec.failed(sid, NAME, inp, str(e), doc=doc["id"],
                   ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
        return _fallback(doc, str(e))

    # 쪽 번호를 그대로 믿지 않는다. 범위 밖이나 중복이 섞여 온다.
    seen, picked = set(), []
    for v in (got.get("pages") or []):
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= doc["pages"] and n not in seen:
            seen.add(n)
            picked.append(n)
    picked = sorted(picked)[:MAX_PAGES]

    if not picked:
        rec.failed(sid, NAME, inp, "쓸 만한 쪽을 하나도 고르지 못했다", doc=doc["id"],
                   ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
        return _fallback(doc, "이 글에 쓸 만한 구간을 찾지 못했습니다")

    body, segs = _budget(doc["pages_text"], picked)
    doc["excerpt"] = body
    doc["segments"] = segs
    doc["picked"] = True
    doc["truncated"] = len(segs) < len(picked)
    doc["pick_why"] = z.s(got.get("why"), 200)
    doc["preview"] = z.s(body[:upload.PREVIEW].replace("\n", " "))

    rec.generated(
        sid, NAME, inp,
        [{"id": f"p{s['page']}", "title": f"{s['page']}쪽",
          "summary": s["head"], "meta": "", "payload": {"page": s["page"]}}
         for s in segs],
        model=llm.model_for(False), source="llm", refresh=False, doc=doc["id"],
        ms=round((time.perf_counter() - t0) * 1000), raw=llm.raw(NAME))
    return doc
