"""출처의 성격을 도메인으로 가른다.

## 왜 필요한가

검색 계획은 `official_primary` 를 **원했다**고만 말한다. 실제로 무엇이
걸려 왔는지는 다른 문제다. 공식 원문을 노린 질의에서 언론 기사가 나오는 일이
흔하고, 예전에는 그 기사에도 `official_primary` 가 붙었다.

    원한 것   official_primary
    걸린 것   언론 기사
    저장값    official_primary      ← 우선순위 정렬이 무의미해진다

그래서 두 값을 나눠 든다.

    requested_target   계획이 노린 성격
    actual_target      여기서 도메인을 보고 매긴 성격

## 왜 여기 있나

`policy.py` 는 규칙이고 이건 **설정**이다. 지역·주제가 늘면 같이 늘고,
`channels.py` · `company.py` 와 같은 성격이라 `data/` 에 둔다.

**프롬프트는 여전히 기관 이름을 모른다.** 프롬프트가 아는 것은 출처의
성격(`official_primary` 같은 값)뿐이고, 어느 도메인이 그 성격인지는 코드만
안다. 프롬프트에 기관명을 박으면 다른 주제에서 재사용이 깨진다.

## 목록에 없으면 secondary 다

모르는 곳을 공식으로 올리지 않는다. 잘못 낮춰 부르면 근거 하나를 덜 쓰지만,
잘못 높여 부르면 **블로그 글이 법령 행세를 한다.**

여기는 아무것도 import 하지 않는다.
"""

# 성격 → 도메인. 뒤에 오는 것이 앞을 못 덮도록 위에서부터 본다.
#
# `*.` 으로 시작하면 그 뒤가 붙는 모든 하위 도메인이다.
DOMAINS: dict[str, tuple[str, ...]] = {
    # 제도를 정한 주체의 원문·공식 안내
    "official_primary": (
        "eur-lex.europa.eu",
        "*.europa.eu",
        "*.un.org",
        "*.unfccc.int",
        "*.oecd.org",
    ),
    # 국내 정부·공공기관
    "domestic_official": (
        "*.go.kr",
        "*.or.kr",
        "law.go.kr",
    ),
    # 표준·방법론
    "standards": (
        "*.iso.org",
        "ghgprotocol.org",
        "*.ipcc.ch",
        "sciencebasedtargets.org",
        "*.cdp.net",
    ),
    # 연구기관
    "research": (
        "*.re.kr",
        "*.ac.kr",
        "*.edu",
        "*.iea.org",
        "*.worldbank.org",
    ),
}

FALLBACK = "secondary"


def host_of(url: str) -> str:
    """주소에서 호스트만. 못 읽으면 빈 문자열."""
    u = (url or "").strip().lower()
    for head in ("https://", "http://"):
        if u.startswith(head):
            u = u[len(head):]
            break
    else:
        return ""
    u = u.split("/")[0].split("?")[0].split("#")[0]
    if "@" in u:            # user:pass@host — 뒤가 진짜 호스트다
        u = u.rsplit("@", 1)[1]
    u = u.split(":")[0]     # 포트
    return u[4:] if u.startswith("www.") else u


def _hit(host: str, pattern: str) -> bool:
    if pattern.startswith("*."):
        tail = pattern[1:]          # ".europa.eu"
        return host == tail[1:] or host.endswith(tail)
    return host == pattern


def classify(url: str) -> str:
    """이 주소가 실제로 어떤 성격의 출처인가.

    모르면 `secondary`. 목록에 없는 곳을 공식으로 올리지 않는다.
    """
    host = host_of(url)
    if not host:
        return FALLBACK
    for target, patterns in DOMAINS.items():
        if any(_hit(host, p) for p in patterns):
            return target
    return FALLBACK
