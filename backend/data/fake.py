"""테스트 데이터.

스키마는 5단계(주제 확정) 실제 출력 계약에 맞췄다.
나중에 이 모듈만 시트 읽기로 갈아끼운다. 호출하는 쪽(main.py)은 안 바뀐다.

  load_topics()  -> 시트 B(topics) 읽기
  load_error()   -> 읽기 실패 메시지

sources 는 topics 시트에 비정규화해 둔 값이다.
5단계는 source_article_ids 만 주므로, n8n 이 시트에 적재할 때
시트 A(articles) 를 조인해 press/headline/url 을 미리 박아 넣는다.

시트에서 읽으면 건수가 가변이다. 화면은 스크롤로 처리한다.
"""

from copy import deepcopy

LOADED_AT = "07-27"

# 👎 사유 칩. 늘어나면 여기만 고친다.
DOWN_TAGS = [
    "근거 댈 게 없는 주제",
    "너무 넓음",
    "서비스랑 안 맞음",
    "이미 다룬 내용",
]

TOPICS = [
    {
        "topic_id": "t1",
        "topic_title": "CBAM 전환기간 종료와 본격 시행",
        "topic_summary": "전환기간이 끝나면서 보고 의무가 인증서 구매 의무로 넘어간다. 수출기업이 지금 확인해야 할 준비 상태를 정리한다.",
        "source_article_ids": ["a101", "a102"],
        "sources": [
            {"press": "임팩트온", "headline": "EU CBAM 본시행 앞두고 국내 수출기업 준비 미흡",
             "url": "http://www.impacton.net/news/articleView.html?idxno=19040"},
            {"press": "ESG경제", "headline": "CBAM 신고 의무, 무엇이 달라지나",
             "url": "https://www.esgeconomy.com/news/articleView.html?idxno=8812"},
        ],
        "business_relevance": 0.86, "search_demand": 0.74, "final_score": 0.81, "rank": 1,
        "rationale": "CBAM 대응 서비스와 직결되고, 시행 시점이 가까워 검색 수요가 오르는 중.",
        "collected_date": "07-27",
    },
    {
        "topic_id": "t2",
        "topic_title": "ESG 공시 데이터 체계부터 다시 짜기",
        "topic_summary": "공시 채널마다 숫자가 어긋나는 사례가 늘고 있다. 산정 근거와 조직 경계를 맞추는 순서를 짚는다.",
        "source_article_ids": ["a103"],
        "sources": [
            {"press": "환경일보", "headline": "공시 채널 간 데이터 불일치 지적 잇따라",
             "url": "http://www.hkbs.co.kr/news/articleView.html?idxno=772104"},
        ],
        "business_relevance": 0.79, "search_demand": 0.61, "final_score": 0.72, "rank": 2,
        "rationale": "공시 대응 서비스와 맞물리지만 근거기사가 1건이라 관통 가산이 없음.",
        "collected_date": "07-26",
    },
    {
        "topic_id": "t3",
        "topic_title": "스코프3 배출량 산정, 어디까지 해야 하나",
        "topic_summary": "공급망 배출량의 범위를 두고 실무 혼선이 이어진다. 카테고리별 우선순위 판단 기준을 정리한다.",
        "source_article_ids": ["a104", "a105"],
        "sources": [
            {"press": "에코타임스", "headline": "공급망 배출량 산정 범위 두고 혼선",
             "url": "http://www.ecotiger.co.kr/news/articleView.html?idxno=63118"},
            {"press": "ESG경제", "headline": "협력사 데이터 확보가 최대 병목",
             "url": "https://www.esgeconomy.com/news/articleView.html?idxno=8790"},
        ],
        "business_relevance": 0.81, "search_demand": 0.63, "final_score": 0.71, "rank": 3,
        "rationale": "인벤토리 서비스와 연결되고 근거기사 2건이 같은 병목을 지적함.",
        "collected_date": "07-26",
    },
    {
        "topic_id": "t4",
        "topic_title": "건축물 전과정평가 의무화 논의 본격화",
        "topic_summary": "설계 단계에서 탄소배출을 산정하도록 요구하는 흐름이 나타나고 있다. 자재 데이터 확보가 관건이다.",
        "source_article_ids": ["a106"],
        "sources": [
            {"press": "환경일보", "headline": "건축물 탄소배출 산정 제도화 검토",
             "url": "http://www.hkbs.co.kr/news/articleView.html?idxno=772044"},
        ],
        "business_relevance": 0.83, "search_demand": 0.48, "final_score": 0.69, "rank": 4,
        "rationale": "건물 LCA 서비스와 정확히 맞지만 아직 검색 수요가 형성되지 않음.",
        "collected_date": "07-25",
    },
    {
        "topic_id": "t5",
        "topic_title": "환경성적표지 인증 갱신, 놓치기 쉬운 지점",
        "topic_summary": "유효기간이 도래한 인증이 늘고 있다. 갱신 시 데이터 재산정 범위를 어디까지 볼지 정리한다.",
        "source_article_ids": ["a107"],
        "sources": [
            {"press": "그린포스트코리아", "headline": "EPD 인증 갱신 물량 증가",
             "url": "https://www.greenpostkorea.co.kr/news/articleView.html?idxno=210590"},
        ],
        "business_relevance": 0.88, "search_demand": 0.39, "final_score": 0.68, "rank": 5,
        "rationale": "EPD 서비스와 직결. 검색 수요는 낮지만 문의 전환 가능성이 높은 주제.",
        "collected_date": "07-25",
    },
    {
        "topic_id": "t6",
        "topic_title": "AI로 그린워싱 사전 진단하기",
        "topic_summary": "표시·광고 문구를 법무 검토 전에 걸러내려는 시도가 나오고 있다. 어디까지 자동화가 가능한지 본다.",
        "source_article_ids": ["a108", "a109"],
        "sources": [
            {"press": "임팩트온", "headline": "법무팀 가기 전 AI 먼저 돌려봤더니",
             "url": "http://www.impacton.net/news/articleView.html?idxno=18997"},
            {"press": "그린포스트코리아", "headline": "표시광고 심사지침 개정 논의",
             "url": "https://www.greenpostkorea.co.kr/news/articleView.html?idxno=210553"},
        ],
        "business_relevance": 0.52, "search_demand": 0.83, "final_score": 0.66, "rank": 6,
        "rationale": "검색 수요는 높지만 우리 서비스와 직접 연결되는 지점이 약함.",
        "collected_date": "07-25",
    },
    {
        "topic_id": "t7",
        "topic_title": "K-REACH 등록 유예 종료 앞둔 대응 점검",
        "topic_summary": "톤수 구간별 유예가 순차로 끝난다. 등록 대상 판단과 자료 준비 순서를 짚는다.",
        "source_article_ids": ["a110"],
        "sources": [
            {"press": "에코타임스", "headline": "화학물질 등록 유예 종료 임박",
             "url": "http://www.ecotiger.co.kr/news/articleView.html?idxno=63090"},
        ],
        "business_relevance": 0.85, "search_demand": 0.44, "final_score": 0.66, "rank": 7,
        "rationale": "화학물질 규제대응 서비스와 직결. 법령 근거를 명확히 댈 수 있는 주제.",
        "collected_date": "07-24",
    },
    {
        "topic_id": "t8",
        "topic_title": "재생원료 사용 의무 비율 도입 흐름",
        "topic_summary": "포장재를 시작으로 재생원료 사용 비율을 규정하려는 움직임이 이어진다. 산정 방식이 쟁점이다.",
        "source_article_ids": ["a111"],
        "sources": [
            {"press": "그린포스트코리아", "headline": "재생원료 의무 비율 논의 재점화",
             "url": "https://www.greenpostkorea.co.kr/news/articleView.html?idxno=210511"},
        ],
        "business_relevance": 0.67, "search_demand": 0.55, "final_score": 0.62, "rank": 8,
        "rationale": "순환경제 서비스와 연결되나 제도 윤곽이 아직 불확실함.",
        "collected_date": "07-24",
    },
    {
        "topic_id": "t9",
        "topic_title": "배출권 계획기간 할당 방식 변화",
        "topic_summary": "무상할당 축소 논의가 이어지면서 감축 투자 판단 시점이 앞당겨지고 있다.",
        "source_article_ids": ["a112"],
        "sources": [
            {"press": "산업통상자원부", "headline": "배출권거래제 운영 개선 방안 발표",
             "url": "https://www.korea.kr/news/pressReleaseView.do?newsId=156600000"},
        ],
        "business_relevance": 0.72, "search_demand": 0.46, "final_score": 0.60, "rank": 9,
        "rationale": "인벤토리·감축 서비스와 연결. 정부 발표라 근거 신뢰도가 높음.",
        "collected_date": "07-23",
    },
]

SAMPLE_ERROR = (
    "PermissionError: [Errno 13] Permission denied: "
    "'C:/solutis/data/sources_20260727.xlsx'"
)


def load_topics(state: str = "normal") -> list[dict]:
    """state 는 화면 상태 미리보기용이다.

    normal / last -> 목록 있음   (last 는 지난주 소재 다시 보기)
    empty / error -> 목록 없음
    """
    if state in ("empty", "error"):
        return []
    return deepcopy(TOPICS)


def load_error(state: str = "normal") -> str | None:
    return SAMPLE_ERROR if state == "error" else None

# ══════════════════════════════════════════════════════════════════
# 2~7단계 테스트 데이터
#
# 파이프라인 3·6·7·8단계가 만들 값들을 미리 손으로 적어 둔 것이다.
# 화면이 앞 단계 선택에 반응하는지 확인하는 게 목적이라, 소재마다
# 독자·키워드·근거를 다르게 뒀다.
#
#   load_personas(topic_id)   -> 3단계 personas
#   load_keywords(topic_id)   -> 4단계 representative_keywords
#   load_evidence(topic_id)   -> 7단계 근거 후보
#
# 이 세 함수만 실제 호출로 갈아끼우면 steps.py 는 안 바뀐다.
# ══════════════════════════════════════════════════════════════════

# 소재를 직접 쓴 경우엔 소재별 페르소나가 없다. 도메인 공통으로 받는다.
FALLBACK_PERSONAS = [
    {
        "is_main": True, "role": "ESG 실무 담당자", "expertise_level": "실무",
        "decision_authority": "추천자",
        "preferred_terms": ["대응 절차", "산정 근거", "내부 검토"],
        "pain_points": ["기준이 자주 바뀌어 어디까지 준비해야 하는지 판단이 어렵다",
                        "내부 보고용 근거를 문서로 남겨야 한다"],
        "avoid_terms": [],
    },
    {
        "is_main": False, "role": "환경안전팀 매니저", "expertise_level": "실무",
        "decision_authority": "결정자",
        "preferred_terms": ["법적 의무", "리스크", "일정"],
        "pain_points": ["의무 여부와 시점을 먼저 확정해야 예산을 잡을 수 있다"],
        "avoid_terms": ["과장된 위기 표현"],
    },
    {
        "is_main": False, "role": "구매·공급망 담당자", "expertise_level": "입문",
        "decision_authority": "영향자",
        "preferred_terms": ["협력사 요청", "제출 자료"],
        "pain_points": ["고객사가 요구하는 자료가 뭔지 용어부터 모르겠다"],
        "avoid_terms": ["약어 남발"],
    },
]

PERSONAS = {
    "t1": [
        {"is_main": True, "role": "수출기업 통관·물류 담당자", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["내재배출량", "신고서", "인증서 구매"],
         "pain_points": ["전환기간 종료 후 무엇이 의무로 바뀌는지 정리가 안 됐다",
                         "해외 고객사가 요구하는 배출량 자료를 못 맞추고 있다"],
         "avoid_terms": []},
        {"is_main": False, "role": "제조사 환경담당 팀장", "expertise_level": "전문가",
         "decision_authority": "결정자",
         "preferred_terms": ["내재배출량 산정", "검증기관", "기본값"],
         "pain_points": ["실측값과 기본값 중 무엇을 쓸지 판단 기준이 필요하다"],
         "avoid_terms": ["단정적 전망"]},
    ],
    "t2": [
        {"is_main": True, "role": "지속가능경영팀 매니저", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["공시 정합성", "산정 경계", "원천자료"],
         "pain_points": ["채널마다 숫자가 달라 외부 질의에 설명이 안 된다",
                         "산식과 집계 기간 근거를 내부에서 검증할 절차가 없다"],
         "avoid_terms": []},
        {"is_main": False, "role": "IR·재무 담당자", "expertise_level": "실무",
         "decision_authority": "영향자",
         "preferred_terms": ["투자자 질의", "공시 신뢰성"],
         "pain_points": ["사업보고서와 수치가 어긋나면 정정 부담이 크다"],
         "avoid_terms": ["마케팅성 표현"]},
    ],
    "t3": [
        {"is_main": True, "role": "온실가스 인벤토리 담당자", "expertise_level": "전문가",
         "decision_authority": "추천자",
         "preferred_terms": ["카테고리", "활동자료", "배출계수"],
         "pain_points": ["15개 카테고리 중 어디까지 산정할지 기준이 없다",
                         "협력사 데이터를 못 받아 추정치로 채우고 있다"],
         "avoid_terms": []},
        {"is_main": False, "role": "구매팀 담당자", "expertise_level": "입문",
         "decision_authority": "영향자",
         "preferred_terms": ["협력사 요청", "자료 양식"],
         "pain_points": ["협력사에 뭘 어떻게 요청해야 할지 모르겠다"],
         "avoid_terms": ["약어 남발"]},
    ],
    "t4": [
        {"is_main": True, "role": "건설사 설계 담당자", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["자재 물량", "설계 단계 산정", "원단위"],
         "pain_points": ["설계 단계에서 자재 데이터를 어디서 확보할지 모르겠다"],
         "avoid_terms": []},
        {"is_main": False, "role": "발주처 사업관리 담당자", "expertise_level": "입문",
         "decision_authority": "결정자",
         "preferred_terms": ["제도 적용 시점", "제출 서류"],
         "pain_points": ["의무화 시점과 대상 범위부터 확인해야 한다"],
         "avoid_terms": ["기술 용어"]},
    ],
    "t5": [
        {"is_main": True, "role": "품질·인증 담당자", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["유효기간", "재산정 범위", "갱신 심사"],
         "pain_points": ["갱신 때 데이터를 어디까지 다시 만들어야 하는지 불명확하다"],
         "avoid_terms": []},
        {"is_main": False, "role": "제품기획 담당자", "expertise_level": "입문",
         "decision_authority": "영향자",
         "preferred_terms": ["인증 마크", "소요 기간"],
         "pain_points": ["인증이 끊기면 영업 자료를 못 쓴다"],
         "avoid_terms": []},
    ],
    "t6": [
        {"is_main": True, "role": "마케팅·홍보 담당자", "expertise_level": "입문",
         "decision_authority": "추천자",
         "preferred_terms": ["표시·광고", "친환경 문구", "사전 검토"],
         "pain_points": ["어떤 표현이 걸리는지 기준을 모른 채 문구를 쓴다"],
         "avoid_terms": ["법률 조문 인용"]},
        {"is_main": False, "role": "법무 검토 담당자", "expertise_level": "전문가",
         "decision_authority": "결정자",
         "preferred_terms": ["심사지침", "실증자료"],
         "pain_points": ["검토 요청이 몰려 사전 필터가 필요하다"],
         "avoid_terms": []},
    ],
    "t7": [
        {"is_main": True, "role": "화학물질 관리 담당자", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["등록 대상", "톤수 구간", "유해성 자료"],
         "pain_points": ["우리 물질이 이번 구간에 걸리는지 판단이 안 선다",
                         "자료 준비 기간을 못 잡아 일정이 밀린다"],
         "avoid_terms": []},
        {"is_main": False, "role": "수입 담당자", "expertise_level": "입문",
         "decision_authority": "영향자",
         "preferred_terms": ["수입 물량", "신고 의무"],
         "pain_points": ["수입만 하는데도 등록 의무가 있는지 모르겠다"],
         "avoid_terms": []},
    ],
    "t8": [
        {"is_main": True, "role": "포장재 개발 담당자", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["재생원료 비율", "물성 확보", "산정 방식"],
         "pain_points": ["비율을 어떤 기준으로 계산하는지 규정이 제각각이다"],
         "avoid_terms": []},
        {"is_main": False, "role": "지속가능경영팀 매니저", "expertise_level": "실무",
         "decision_authority": "추천자",
         "preferred_terms": ["순환경제", "목표 설정"],
         "pain_points": ["대외 공표 목표와 실제 달성 가능성의 간극이 크다"],
         "avoid_terms": []},
    ],
    "t9": [
        {"is_main": True, "role": "배출권 담당자", "expertise_level": "전문가",
         "decision_authority": "추천자",
         "preferred_terms": ["무상할당", "계획기간", "감축설비 투자"],
         "pain_points": ["할당 축소 폭에 따라 투자 시점 판단이 달라진다"],
         "avoid_terms": []},
        {"is_main": False, "role": "재무·기획 담당자", "expertise_level": "입문",
         "decision_authority": "결정자",
         "preferred_terms": ["비용 영향", "투자 회수"],
         "pain_points": ["제도 변화가 손익에 얼마나 영향을 주는지 숫자로 봐야 한다"],
         "avoid_terms": ["기술 용어"]},
    ],
}

FALLBACK_KEYWORDS = [
    {"keyword": "대응 방법", "intent": "정보형", "funnel_stage": "인지"},
    {"keyword": "컨설팅", "intent": "상업형", "funnel_stage": "전환"},
]

KEYWORDS = {
    "t1": [{"keyword": "cbam 대응", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "내재배출량 산정", "intent": "정보형", "funnel_stage": "고려"},
           {"keyword": "cbam 컨설팅", "intent": "상업형", "funnel_stage": "전환"}],
    "t2": [{"keyword": "esg 공시 대응", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "지속가능경영보고서 검증", "intent": "상업형", "funnel_stage": "고려"},
           {"keyword": "공시 데이터 관리", "intent": "정보형", "funnel_stage": "고려"}],
    "t3": [{"keyword": "스코프3 산정", "intent": "정보형", "funnel_stage": "고려"},
           {"keyword": "온실가스 인벤토리 구축", "intent": "상업형", "funnel_stage": "전환"},
           {"keyword": "공급망 배출량", "intent": "정보형", "funnel_stage": "인지"}],
    "t4": [{"keyword": "건축물 lca", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "건물 전과정평가 비용", "intent": "상업형", "funnel_stage": "고려"},
           {"keyword": "설계단계 탄소배출 산정", "intent": "정보형", "funnel_stage": "고려"}],
    "t5": [{"keyword": "환경성적표지 갱신", "intent": "정보형", "funnel_stage": "고려"},
           {"keyword": "epd 인증 절차", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "epd 인증 대행", "intent": "거래형", "funnel_stage": "전환"}],
    "t6": [{"keyword": "그린워싱 기준", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "친환경 표시광고 심사지침", "intent": "정보형", "funnel_stage": "고려"},
           {"keyword": "그린워싱 사례", "intent": "정보형", "funnel_stage": "인지"}],
    "t7": [{"keyword": "k-reach 등록", "intent": "정보형", "funnel_stage": "고려"},
           {"keyword": "화학물질 등록 대행", "intent": "거래형", "funnel_stage": "전환"},
           {"keyword": "등록 유예기간", "intent": "정보형", "funnel_stage": "인지"}],
    "t8": [{"keyword": "재생원료 의무비율", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "재생원료 인증", "intent": "상업형", "funnel_stage": "고려"},
           {"keyword": "순환경제 대응", "intent": "정보형", "funnel_stage": "인지"}],
    "t9": [{"keyword": "배출권 할당", "intent": "정보형", "funnel_stage": "고려"},
           {"keyword": "무상할당 축소", "intent": "정보형", "funnel_stage": "인지"},
           {"keyword": "감축설비 투자 검토", "intent": "상업형", "funnel_stage": "고려"}],
}

# 어떤 소재든 댈 수 있는 근거. 성격(kind)으로 구분한다.
EVIDENCE_COMMON = [
    {"ev_id": "c1", "kind": "법령", "title": "관련 법률 조문 원문",
     "detail": "국가법령정보센터에서 조문 단위로 인용한다. 개정일 확인 필요.",
     "authority": "높음"},
    {"ev_id": "c2", "kind": "가이드", "title": "소관 부처 공식 안내서",
     "detail": "제도 시행 시점·대상 범위의 1차 출처.", "authority": "높음"},
    {"ev_id": "c3", "kind": "수행실적", "title": "자사 유사 프로젝트 수행 경험",
     "detail": "고객사명 없이 업종·규모 수준으로만 서술한다.", "authority": "중간"},
]

EVIDENCE_BY_TOPIC = {
    "t1": [{"ev_id": "t1a", "kind": "해외기준", "title": "EU 이행규정 본문",
            "detail": "전환기간·본시행 의무 구분의 근거.", "authority": "높음"},
           {"ev_id": "t1b", "kind": "통계", "title": "품목별 수출 물량 통계",
            "detail": "영향 규모를 숫자로 보일 때 쓴다.", "authority": "중간"}],
    "t2": [{"ev_id": "t2a", "kind": "기준", "title": "국내 공시기준 초안",
            "detail": "채널 간 정합성 요구사항의 근거.", "authority": "높음"},
           {"ev_id": "t2b", "kind": "사례", "title": "공시 수치 정정 공시 사례",
            "detail": "실제로 어긋난 지점을 보여준다.", "authority": "중간"}],
    "t3": [{"ev_id": "t3a", "kind": "국제기준", "title": "온실가스 회계 표준 스코프3 장",
            "detail": "카테고리 정의와 산정 우선순위의 근거.", "authority": "높음"},
           {"ev_id": "t3b", "kind": "배출계수", "title": "국가 배출계수 DB",
            "detail": "활동자료 환산 근거.", "authority": "높음"}],
    "t4": [{"ev_id": "t4a", "kind": "기준", "title": "건축물 전과정평가 산정 지침",
            "detail": "설계 단계 산정 범위의 근거.", "authority": "높음"},
           {"ev_id": "t4b", "kind": "DB", "title": "건설자재 환경성 DB",
            "detail": "자재별 원단위 확보처.", "authority": "중간"}],
    "t5": [{"ev_id": "t5a", "kind": "고시", "title": "환경성적표지 운영 고시",
            "detail": "유효기간·갱신 요건의 근거.", "authority": "높음"},
           {"ev_id": "t5b", "kind": "PCR", "title": "해당 제품군 PCR 문서",
            "detail": "재산정 범위 판단의 직접 근거.", "authority": "높음"}],
    "t6": [{"ev_id": "t6a", "kind": "지침", "title": "표시·광고 심사지침",
            "detail": "어떤 문구가 문제되는지의 기준.", "authority": "높음"},
           {"ev_id": "t6b", "kind": "사례", "title": "제재 처분 사례",
            "detail": "실제 판단 경계를 보여준다.", "authority": "중간"}],
    "t7": [{"ev_id": "t7a", "kind": "법령", "title": "화학물질 등록·평가 법률",
            "detail": "등록 대상·유예 구간의 근거.", "authority": "높음"},
           {"ev_id": "t7b", "kind": "고시", "title": "등록대상 기존화학물질 목록",
            "detail": "물질별 해당 여부 확인처.", "authority": "높음"}],
    "t8": [{"ev_id": "t8a", "kind": "법령", "title": "자원순환 관련 법령",
            "detail": "의무 비율 도입 근거 조문.", "authority": "높음"},
           {"ev_id": "t8b", "kind": "해외기준", "title": "해외 포장재 규정",
            "detail": "산정 방식 비교 대상.", "authority": "중간"}],
    "t9": [{"ev_id": "t9a", "kind": "정부발표", "title": "배출권거래제 운영 개선방안",
            "detail": "할당 방식 변경의 1차 출처.", "authority": "높음"},
           {"ev_id": "t9b", "kind": "통계", "title": "배출권 시장 가격 추이",
            "detail": "투자 판단 시점 논의의 근거.", "authority": "중간"}],
}


def load_personas(topic_id: str | None) -> list[dict]:
    """3단계가 뽑는 페르소나. 직접 쓴 소재면 도메인 공통으로 준다."""
    return deepcopy(PERSONAS.get(topic_id or "", FALLBACK_PERSONAS))


def load_keywords(topic_id: str | None) -> list[dict]:
    """4단계가 태깅한 대표 키워드."""
    return deepcopy(KEYWORDS.get(topic_id or "", FALLBACK_KEYWORDS))


def load_evidence(topic_id: str | None) -> list[dict]:
    """7단계 근거 후보. 소재별 근거를 앞에, 공통 근거를 뒤에 둔다."""
    return deepcopy(EVIDENCE_BY_TOPIC.get(topic_id or "", []) + EVIDENCE_COMMON)


def find_topic(topic_id: str | None) -> dict | None:
    for t in TOPICS:
        if t["topic_id"] == topic_id:
            return deepcopy(t)
    return None
