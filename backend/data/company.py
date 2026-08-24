"""회사 정보.

홈페이지 결과물의 신뢰 요소 — 작성자, 검토자, 관련 서비스, 연락처 — 가
여기서 온다. **모델이 만들지 않는다.**

이름을 지어내면 신뢰 요소가 정반대로 작동한다. "환경 전문가" 같은 임의
문구로 빈칸을 메우는 것도 같은 문제다. 그래서 값이 없으면 **그 영역을 통째로
빼고 렌더한다.** 화면에 안 나오는 편이 지어낸 이름이 나가는 것보다 낫다.

지금은 비어 있다. 채우는 자리만 있다.

`services` 는 나중에 시트에서 온다. 소재에 `service_id` 가 붙어 내려오므로
(n8n 2단계), 그때 여기는 id → 이름·설명·링크 표만 들고 있으면 된다.

**여기는 아무것도 import 하지 않는다.**
"""

COMPANY = {
    "name": "SOLUTIS C&T",
    "contact": {
        "homepage": "",
        "email": "",
        "phone": "",
    },
}

# 글에 이름을 올릴 사람. [{"name", "role", "org"}]
AUTHORS: list[dict] = []
REVIEWERS: list[dict] = []

# service_id → {name, summary, url}. 소재가 들고 오는 id 로 찾는다.
#
# **비어 있다.** 코드는 다 붙어 있고 데이터만 없다 — 채우는 순간 관련
# 서비스와 글 끝 안내가 자동으로 나간다.
#
# 채울 때는 세 가지를 맞춘다.
#
#   name     실제 사이트에 쓰는 이름 그대로. 여기서 새로 짓지 않는다
#   summary  한 줄. 이 서비스가 무엇을 해 주는지
#   url      실제 주소. **모르면 비운다** — 없는 주소로 버튼을 내보내면
#            눌렀을 때 아무 데도 안 간다. 비우면 이름만 나가고 링크는 안 붙는다
#
# service_id 는 n8n 2단계가 소재에 붙여 주는 값이다. 개발용 데이터
# (data/fake.py)에는 없으므로, 지금은 발행 전 확인 목록에 "소재에
# service_id 가 없습니다" 가 뜨는 것이 정상이다.

SERVICES: dict[str, dict] = {}


def author(name: str = "") -> dict | None:
    """이름을 주면 그 사람, 안 주면 첫 번째. 없으면 None.

    None 을 돌려주는 것이 중요하다. 부르는 쪽이 None 을 보고 그 영역을
    통째로 건너뛴다 — 빈 문자열을 주면 이름 없는 작성자 줄이 나간다.
    """
    return _find(AUTHORS, name)


def reviewer(name: str = "") -> dict | None:
    return _find(REVIEWERS, name)


def _find(rows, name):
    if not rows:
        return None
    if not name:
        return rows[0]
    return next((r for r in rows if r.get("name") == name), None)


def service(service_id: str = "") -> dict | None:
    """소재에 붙은 service_id 로 찾는다. 없으면 None."""
    return SERVICES.get(service_id) if service_id else None


# ── 글 끝의 안내 문구 ─────────────────────────────────────────
#
# **모델이 만들지 않는다.** 회사가 무엇을 어떻게 권하는지는 회사가 정할
# 것이고, 매번 다르게 지어내면 글마다 다른 회사처럼 보인다.
#
# 채널이 아니라 **강도**로 고른다. `cta_strength` 는 채널이 정하는 값이지만
# (홈페이지 medium, 네이버 soft), 나중에 같은 채널에서 강도를 바꿀 수 있어야
# 한다 — 그러라고 둔 값이다.
#
# `{service}` 자리에는 소재에 붙은 서비스 이름이 들어간다. **서비스를 모르면
# 이 영역은 통째로 안 나간다** — 작성자 이름을 안 지어내는 것과 같다.

CTA = {
    "soft": {
        "lead": "이 글에서 다룬 판단이 자사 상황에 어떻게 적용되는지는"
                " 자료와 공정에 따라 달라집니다.",
        "action": "{service} 관련 자료 보기",
    },
    "medium": {
        "lead": "실제 적용 범위와 준비 수준은 기업마다 다릅니다.",
        "action": "{service} 안내 보기",
    },
    "strong": {
        "lead": "대응 시점과 자료 준비 상태를 함께 점검해야 합니다.",
        "action": "{service} 상담 요청하기",
    },
}


def cta(strength: str, service: dict | None) -> dict | None:
    """글 끝에 붙일 안내. 서비스를 모르면 None.

    None 을 돌려주는 것이 중요하다. 부르는 쪽이 None 을 보고 그 영역을
    통째로 건너뛴다 — 빈 문자열을 주면 이름 없는 버튼이 나간다.

    **주소가 없어도 안내는 나간다.** 이름과 설명만으로도 "이 글이 어느
    업무와 이어지는가" 는 전해진다. 링크만 안 붙고, 확인 목록이 주소를
    채우라고 알린다.
    """
    row = CTA.get(strength)
    if not row or not service or not service.get("name"):
        return None
    return {"lead": row["lead"],
            "action": row["action"].format(service=service["name"]),
            "url": service.get("url", ""),
            "summary": service.get("summary", "")}


def has_trust() -> bool:
    """신뢰 요소를 넣을 수 있는 상태인가. 발행 전 확인 목록이 쓴다."""
    return bool(AUTHORS or REVIEWERS)
