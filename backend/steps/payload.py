"""확정값을 **읽는 법**.

각 단계가 자기 payload 를 만드는 빌더는 그 단계 폴더에 있다. 여기 있는 것은
"다른 단계가 그 값을 어떻게 꺼내 읽느냐" 다. 만드는 쪽에 두면 읽는 단계가
만드는 단계를 import 하게 되고, 그러면 단계끼리 엮인다.

지금은 하나뿐이다. 늘어나면 여기 모은다.
"""


def is_confirmed(item) -> bool:
    """이 근거는 실물이 손에 있는가.

    두 곳이 이 판단을 한다 — 7단계 확정 라벨("확인된 출처 N건")과 본문
    작성의 근거 가르기. **두 곳에 따로 적었더니 곧바로 어긋났다.** 라벨은
    url 만 보고 본문은 url·file 을 봐서, 올린 PDF 가 인용은 되는데
    라벨에는 "확인 필요" 로 세어졌다.

        url    소재에 딸려온 기사
        file   사람이 올린 PDF — 원문을 직접 올린 것이라 기사보다 확실하다

    둘 다 없으면 "무엇을 어디서 확인할지" 까지만 정해진 대상이다.
    """
    if not isinstance(item, dict):
        return False

    # 검증한 명제는 상태가 정한다. url·file 로 판단하면 명제 자체에는 둘 다
    # 없으므로 검증을 통과한 것까지 미확인으로 세어진다.
    #
    # 판정은 evidence/policy.py 한 곳에 있다. 여기서 다시 적으면 근거 카드와
    # 본문 작성이 서로 다른 답을 낸다 — 그 어긋남을 이미 한 번 겪었다.
    if item.get("claim_id"):
        from .evidence import policy
        return policy.citable(item)

    url = str(item.get("url") or "")
    return url.startswith(("http://", "https://")) or bool(item.get("file"))


def is_citable(claim) -> bool:
    """이 명제에 출처를 달 수 있나.

    `is_confirmed` 와 같은 자리다. 여러 단계가 같은 질문을 하는데 각자
    evidence 폴더를 import 하면 단계끼리 얽힌다 — 그건 이 프로젝트가
    금지한 것이고 test.py 가 막는다.
    """
    from .evidence import policy
    return policy.citable(claim if isinstance(claim, dict) else {})


def topic_brief(d, keywords=True) -> dict:
    """소재를 뒤 단계가 읽을 모양으로.

    **필드 이름이 두 벌이라 여기서 흡수한다.** 소재는 n8n·시트에서 오는
    것이라 `topic_title` · `topic_summary` 로 들어오는데, 단계들은
    `headline` · `summary` 를 읽고 있었다. 그래서 **다섯 단계 전부에서
    요약이 빈 문자열이었다** — 소재를 제목 한 줄에서 넓힌 작업이 통째로
    무효였고, 아무 오류도 안 났다.

    같은 일을 다섯 곳에서 각자 하지 않는다. 공급원이 바뀌면 여기만 고친다.
    """
    tp = (d.get("topic", {}) or {}).get("payload") or {}
    out = {
        "headline": tp.get("headline") or tp.get("topic_title")
        or (d.get("topic", {}) or {}).get("label", ""),
        "summary": tp.get("summary") or tp.get("topic_summary") or "",
        "service_name": tp.get("service_name", ""),
    }
    if keywords:
        out["keywords"] = topic_keywords(d)
    return out


def topic_keywords(d, cap=10) -> list[dict]:
    """소재에 붙은 대표 키워드. 검색량까지 그대로 준다."""
    tp = (d.get("topic", {}) or {}).get("payload") or {}
    rows = tp.get("keywords") or tp.get("topic_keywords") or []
    return [{"keyword": x.get("keyword", ""), "volume": x.get("volume", 0)}
            for x in rows[:cap] if isinstance(x, dict) and x.get("keyword")]


def titles(outline_payload) -> list[str]:
    """소제목만. 이미지 계획을 볼 필요가 없는 곳은 이걸 쓴다.

    7단계 근거와 결과물 조립이 그렇다. 각자 payload 를 뜯지 않게 한 곳에 뒀다.
    """
    return [x["title"] for x in (outline_payload or {}).get("sections", [])
            if isinstance(x, dict) and x.get("title")]
