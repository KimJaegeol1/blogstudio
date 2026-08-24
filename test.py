"""통합 테스트.

    python test.py

무엇이 깨졌는지 한 줄로 나온다. 서버를 띄우지 않고 돌며, 프롬프트 호출은
가짜로 바꿔 치므로 API 키도 필요 없다. 로그는 실제 폴더에 쓰고 지운다.

고친 뒤에는 이걸 먼저 돌린다. "돌아가는 것 같다" 와 "돌아간다" 를 가르는
유일한 방법이다.
"""
import json, pathlib, sys, traceback
import atexit
import shutil
from fastapi.testclient import TestClient

OK, BAD = [], []
def check(name, fn):
    try:
        fn(); OK.append(name); print(f"  ✓ {name}")
    except Exception as e:
        BAD.append((name, e)); print(f"  ✗ {name}\n      {type(e).__name__}: {e}")

from backend import config, llm, paths, build
from backend.record import history, feedback, log
from backend.main import app

# 검사에 쓰는 모듈. 흩어 두면 뒤쪽 블록이 앞쪽에서 정의된 이름을 못 본다.
import base64 as _b64
import backend.session as _ses
from backend.external import gemini as _im
from backend.data import skeletons as _sk
from backend import steps as _st
from backend import session as _sess
from backend.steps import channel as _ch, intent as _in, outline as _out, reader as _rd, angle as _ag, type as _ty, title as _tt, evidence as _ev_step
from backend.output import figures as _fg
from backend.data import channels as _cn, skeletons as _sk
from backend.output import render as _r
from backend.external import search as _sr
from backend.output.site import render as _site_r
from backend.output import write as _wr
from backend.steps.outline.payload import payload as _outline_pay

def _md(name, folder=""):
    """프롬프트 원문. 파일이 폴더로 흩어져 이름으로 찾는다.

    밑바탕(_write · _hero · 단계별 _prompt)은 등록부에 없다. 그건 이름이
    아니라 다른 프롬프트 뒤에 깔리는 원문이라 BASE 에 있다. 밑바탕 이름이
    겹칠 수 있어(_prompt.md 가 여럿) 폴더로 좁힌다.
    """
    from backend import prompt as _pr
    key = name.replace(".md", "")
    if key in _pr.REGISTRY:
        return _pr.where(key).read_text(encoding="utf-8")
    f = next((v for v in _pr.BASE.values()
              if v.stem == key and (not folder or v.parent.name == folder)), None)
    assert f, f"모르는 프롬프트: {name}"
    return f.read_text(encoding="utf-8")


def _js(name):
    return (paths.FRONTEND / "js" / name).read_text(encoding="utf-8")


_o = _st           # 예전 이름
_w = _wr

# 실제 폴더에 써 봐야 경로가 맞는지 안다. 그래서 쓰던 로그를 잠시 옮겨 두고
# 테스트가 만든 것만 남긴 뒤 되돌린다.
#
# 되돌리기가 중간에 끊기면 실제 로그가 _test_backup 에 갇힌다. 그 상태에서
# 또 돌리면 _test_backup/choice/choice 처럼 겹쳐 들어가 더 깊이 묻힌다.
# 실제로 그렇게 됐다. 그래서 시작할 때 먼저 꺼내 온다.

_BACKUP = paths.ROOT / "_test_backup"


def _rescue():
    """지난 실행이 갇혀 둔 로그를 꺼내 온다.

    한 줄에 한 건이라 이어 붙이면 그만이다. 겹친 이름이 있어도 줄 단위로
    합치므로 어느 쪽도 사라지지 않는다.
    """
    if not _BACKUP.exists():
        return
    moved = 0
    for f in _BACKUP.rglob("*.jsonl"):
        stream = next((x for x in history.STREAMS if x in f.parts), "response")
        dest = paths.ROOT / stream / f.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as out:
            body = f.read_text(encoding="utf-8")
            if body and not body.endswith("\n"):
                body += "\n"
            out.write(body)
        moved += 1
    shutil.rmtree(_BACKUP, ignore_errors=True)
    if moved:
        print(f"  [test] 지난 실행이 갇혀 둔 로그 {moved}개를 되돌렸습니다")


def _stash():
    _rescue()
    keep = any((paths.ROOT / s).exists() for s in history.STREAMS)
    if keep:
        _BACKUP.mkdir(exist_ok=True)
        for s in history.STREAMS:
            d = paths.ROOT / s
            if d.exists():
                shutil.move(str(d), str(_BACKUP / d.name))
    return keep


def _unstash(keep):
    """테스트가 만든 것을 치우고 원래 있던 것을 되돌린다."""
    for s in history.STREAMS:
        d = paths.ROOT / s
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    # 올린 PDF 도 치운다. 실물 파일이라 두면 다음 실행 때 남의 근거가 섞인다.
    shutil.rmtree(paths.UPLOADS, ignore_errors=True)
    if keep and _BACKUP.exists():
        for d in _BACKUP.iterdir():
            shutil.move(str(d), str(paths.ROOT / d.name))
        _BACKUP.rmdir()


_KEEP = _stash()
atexit.register(_unstash, _KEEP)

FAKE = {
 "reader": {"candidates":[{"role":"수출기업 통관 담당자","expertise_level":"실무",
   "decision_authority":"추천자","pain_points":["기준이 바뀐다"],
   "preferred_terms":["수출신고"],"avoid_terms":["탄소중립 여정"]}]},
 "reader_written": {"expertise_level":"실무","decision_authority":"추천자",
   "pain_points":["양식 맞추기"],"preferred_terms":["활동자료"],"avoid_terms":[]},
 "intent": {"candidates":[{"question":"CBAM 본시행 이후 통관 서류는 무엇이 달라지는가?",
   "search_intent":"informational","sub_questions":["무엇이 새로 요구되는가"],
   "desired_action":"자사 적용 범위를 확인한다"}]},
 "intent_written": {"search_intent":"procedural","sub_questions":["어디부터 보나"],
   "desired_action":"내부 절차를 점검한다"},
 "angle": {"candidates":[{"viewpoint":"공식 의무의 변화를 기준으로 본다",
   "differentiation":"내부 대응보다 달라진 의무를 먼저 짚는다","core_message":"서류부터 맞춘다.",
   "tone":["실무적","차분한","근거중심"]}]},
 "angle_written": {"viewpoint":"직접 쓴 판단 축","differentiation":"사람이 정한 축",
   "tone":["실무적"]},
 "type": {"recommended":"동향형","rationale":"변화 전달","unfit":[]},
 "site_title": {"candidates":[{"title":"CBAM 본격 시행으로 달라지는 통관 서류",
   "title_style":"선언형","used_keywords":[]}]},
 "site_outline": {"candidates":[{"sections":[{"title":"무엇이 확정됐나","image":None},
   {"title":"달라지는 것","image":{"purpose":"차이","form":"전후 비교 도식"}},
   {"title":"확인할 것","image":None}],
   "hero_image":{"purpose":"전환기간 종료가 통관 업무에 미치는 영향을 상징"},
   "rationale":"권장 흐름"}]},
 # 근거 단계는 명제를 나눠 검색·대조까지 한다. 검색 키가 없으면
 # claims 만 돌고 전부 미확인으로 남는다 — 그 경로를 여기서 태운다.
 "claims": {"claims":[
   {"claim":"본격 시행 이후 거래처의 자료 요청이 발생한다",
    "claim_type":"regulation","required_source":"제도를 정한 주체의 원문",
    "searchable":True,"why":"질문의 전제"},
   {"claim":"자료 요청 대응이 선적 일정과 겹칠 수 있다",
    "claim_type":"inference","required_source":"실무 사례",
    "searchable":False,"why":"하위 질문"}]},
 "plan": {"plans":[{"claim_ref":"c01","queries":[
   {"language":"en","source_target":"official_primary",
    "query":"CBAM definitive period supplier emissions data"}]}]},
 "check": {"verdict":"supported","supported_parts":["요청이 발생한다"],
   "unsupported_parts":[],"evidence_spans":[{"quote":"","location":""}],
   "reason":"조항이 뒷받침","limitations":[]},
 "evidence": {"candidates":[{"kind":"규제·법령 원문","title":"신고 항목 규정",
   "claim_to_verify":"신고 항목","detail":"2번","where_to_look":"공식 고시"}]},
 "site_write": {"lead":"전환기간이 끝난다.","sections":[
   {"order":1,"paragraphs":["첫 문단.","둘째 문단."],"figure":None,"cites":[]},
   {"order":2,"paragraphs":["표로 설명."],
    "figure":{"caption":"비교","data":{"columns":["구분","전","후"],
              "rows":[["주기","분기","연간"]]}},"cites":[]},
   {"order":3,"paragraphs":["마무리."],"figure":None,"cites":[]}]},
 # 본문 작성이 대표 이미지를 이어서 만든다. 없으면 자취에 KeyError 가 쌓인다.
 "site_hero": {"prompt":"editorial illustration, no text","alt":"대체 텍스트"},
}
llm.ENABLED = True
# 프롬프트에 무엇이 들어갔는지 본다. 가짜 응답만으로는 "입력이 제대로
# 실렸나" 를 확인할 수 없다.
SEEN = {}


def _fake_generate(n, p, strong=False):
    SEEN[n] = p
    return FAKE[n]


llm.generate = _fake_generate

# 고르는 단계 전부. 레지스트리가 정한다 — 여기 박아 두면 단계를
# 하나 끼울 때마다 테스트 여섯 군데를 같이 고쳐야 한다.
_WALK = [k for k in _st.keys() if k not in ("topic", "approve")]


def walk_to(c, key):
    """그 단계 앞까지 기본값으로 확정해 둔다.

    단계를 하나 끼우면 "reader 부터 시작하는" 검사가 전부 skipped 로
    막힌다. 앞 단계가 무엇인지 검사가 알 필요는 없으므로 여기서 훑는다.
    """
    for k in _WALK:
        if k == key:
            break
        o = c.get(f"/api/draft/{k}").json()
        c.post(f"/api/draft/{k}",
               json={"choice": [o["options"][0]["id"]], "custom": ""})
    return c


def journey(c, custom=None):
    c.get("/api/topics")
    r = c.post("/api/topics/pick", json={"topic_id": None if custom else "t1", "custom": custom or ""})
    assert r.json()["ok"], r.json()
    for k in _WALK:
        o = c.get(f"/api/draft/{k}").json()
        assert o.get("ok"), (k, o)
        pick = ["동향형"] if k == "type" else [o["options"][0]["id"]]
        assert c.post(f"/api/draft/{k}", json={"choice":pick,"custom":""}).json()["ok"], k
    return c

print("── 서버로 띄울 수 있나 ──")

_RUN = (paths.ROOT / "run.py").read_text(encoding="utf-8")
_UNIT = paths.ROOT / "deploy" / "blogstudio.service"

check("포트를 환경변수로 바꿀 수 있다",
      lambda: ('os.environ.get("PORT"' in _RUN
               and 'os.environ.get("HOST"' in _RUN) or 1/0)
check("서버에서는 reload 를 끈다",
      lambda: ("reload=not SERVER" in _RUN) or 1/0)
check("서버에서는 브라우저를 안 연다",
      lambda: ("if not SERVER:" in _RUN) or 1/0)
check("화면이 없으면 서버로 본다",
      lambda: ('os.environ.get("DISPLAY")' in _RUN) or 1/0)
check("키가 없으면 뜰 때 알린다",
      lambda: ("OPENAI_API_KEY 가 없습니다" in _RUN
               and "GEMINI_API_KEY 가 없습니다" in _RUN) or 1/0)
check("systemd 유닛과 올리는 순서가 있다",
      lambda: (_UNIT.exists()
               and (paths.ROOT / "deploy" / "README.md").exists()) or 1/0)
check("유닛에 키를 적어 두지 않았다",
      lambda: ("API_KEY=" not in _UNIT.read_text(encoding="utf-8")) or 1/0)

_ENV = paths.ENV
check(".env 틀이 함께 온다", lambda: _ENV.exists() or 1/0)
check(".env 에 필요한 값이 다 있다",
      lambda: all(k in _ENV.read_text(encoding="utf-8")
                  for k in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_MODEL_STRONG",
                            "GEMINI_API_KEY", "BS_ENV", "PORT")) or 1/0)
check("자리표시를 진짜 키로 치지 않는다",
      lambda: (config.key("__없는키__") == ""
               and config.PLACEHOLDER not in (config.OPENAI_API_KEY,
                                              config.GEMINI_API_KEY)) or 1/0)
check("run.py 가 .env 를 먼저 읽는다",
      lambda: (_RUN.index("from backend import config")
               < _RUN.index('PORT = int(os.environ')) or 1/0)

print("── 경로 ──")
check("paths 가 blogstudio/ 를 가리킨다", lambda: (_ for _ in ()).throw(AssertionError(paths.ROOT))
      if paths.ROOT.name != "blogstudio" else None)
check("로그 세 폴더가 ROOT 아래", lambda: all((paths.ROOT / s).parent == paths.ROOT
                                             for s in history.STREAMS) or 1/0)
check("prompts 가 backend 아래",  lambda: (paths.PROMPTS.parent == paths.BACKEND) or 1/0)
check("log.where 와 paths 일치",  lambda: (log.where("choice") == paths.CHOICE
                                           and log.where("response") == paths.RESPONSE) or 1/0)
check("프롬프트 파일이 읽힌다",     lambda: len(llm.prompt("reader")) > 500 or 1/0)

print("\n── 1단계부터 결과물까지 ──")
c = TestClient(app)
check("한 바퀴 (고르기)", lambda: journey(c))
check("승인 화면", lambda: c.get("/api/draft/approve").json()["ok"] or 1/0)
check("본문 작성", lambda: c.post("/api/draft/write").json()["ok"] or 1/0)
def res():
    r = c.get("/api/draft/result").json()
    assert r["ok"] and len(r["out"]["site"]["html"]) > 500, r
check("결과물 조립", res)

print("\n── 채널과 검색의도 ──")

def _channel_pay():
    """채널 확정값은 네 칸을 다 들고 있어야 한다.

    cta_strength 나 reader_stage 가 비면 그것을 읽는 뒤 단계 규칙이
    KeyError 없이 조용히 죽는다.
    """
    v = c.get("/api/draft").json()["values"]["channel"]
    pay = _ch.payload(_ch.CHANNELS[0])
    assert set(pay) == set(_ch.KEYS), pay
    assert pay["channel"] in _ch.NAMES, pay
    assert v["label"], v
check("채널 확정값이 네 칸을 다 든다", _channel_pay)

check("채널은 프롬프트를 안 쓴다", lambda: (
    not _st.BY_KEY["channel"].uses_llm
    and "channel" not in _st.TIERS) or 1/0)
check("채널은 직접 쓰기를 안 받는다", lambda: (
    _st.meta_of("channel").get("custom") is False) or 1/0)

check("채널 key 는 두 갈래뿐", lambda: (
    _ch.NAMES == ("site", "naver")) or 1/0)

check("독자 입력에 채널이 실린다", lambda: (
    SEEN["reader"]["channel"]["channel"] in _ch.NAMES) or 1/0)
check("각도 입력에 검색의도가 실린다", lambda: (
    SEEN["angle"]["intent"]["question"]) or 1/0)

def _angle_reads_intent():
    """프롬프트가 intent 를 실제로 읽는다.

    예전에는 build_input 이 intent 를 넘기는데 프롬프트에 그 낱말이 한 번도
    안 나왔다 — 같은 소재·독자면 질문이 달라도 비슷한 각도가 나온다.
    검색의도 단계를 만든 이유가 없어지는 자리다.
    """
    md = _md("angle")
    for want in ("intent.question", "sub_questions", "channel.reader_stage",
                 "결정 우선순위"):
        assert want in md, want
check("각도 프롬프트가 검색의도를 읽는다", _angle_reads_intent)

def _viewpoint_is_axis():
    """viewpoint 는 "누구 입장" 이 아니라 "판단 축" 이다.

    독자는 앞 단계에서 정해졌다. 여기서 또 정하면 후보가 화자의 상황만
    바꾼 넷이 된다.
    """
    md = _md("angle")
    assert "판단 축" in md and "reader.role` 을 그대로 옮겨 적지 않는다" in md, md[:0]
    assert "누구 입장에서 쓰는가. reader의 role" not in md
check("viewpoint 가 판단 축으로 정의된다", _viewpoint_is_axis)

def _angle_payload_shape():
    """differentiation 이 확정값에 남는다.

    예전에는 프롬프트가 rationale 을 만들게 해놓고 코드가 버렸다 — 모델에게
    이유를 쓰게 하고 아무도 안 읽는 상태였다.
    """
    p = _ag.payload("축", "논지.", "다른 후보와 이렇게 다르다",
                    ["a", "b", "c", "d"])
    assert set(p) == {"viewpoint", "core_message", "differentiation", "tone"}, p
    assert len(p["tone"]) == _ag.MAX_TONE, p["tone"]
    assert "rationale" not in _md("angle"), "버려지는 값이 남아 있다"
check("각도 확정값에 차이가 남는다", _angle_payload_shape)

check("톤은 1~3개다", lambda: (
    "1~3개" in _md("angle") and "정확히 3개" not in _md("angle")
    and _ag.MAX_TONE == 3) or 1/0)

check("근거 검증 전이라고 적혀 있다", lambda: (
    "근거 검증보다 앞" in _md("angle")
    and "확인된 사실처럼" in _md("angle")) or 1/0)

def _angle_topic_expanded():
    """소재를 제목 한 줄이 아니라 요약·키워드까지 본다."""
    inp = SEEN["angle"]
    assert set(inp["topic"]) == {"headline", "summary", "keywords", "service_name"}
    assert "channel" in inp, sorted(inp)
check("각도가 소재 범위와 채널을 본다", _angle_topic_expanded)

def _angle_offline_by_question():
    """키 없이 돌 때도 질문을 기준으로 만든다.

    예전에는 화자의 상황(당장 할 일 / 결재 설득 / 겪어 본 사람)만 바꿔서
    질문이 달라도 같은 넷이 나왔다.
    """
    d = {"topic": {"label": "소재", "payload": {}},
         "reader": {"payload": {"role": "담당자"}},
         "intent": {"payload": {"question": "무엇부터 확인하나?",
                                "sub_questions": ["범위는 어디까지인가"]}}}
    rows = _ag._offline(d)
    assert any("범위는 어디까지인가" in r["viewpoint"] for r in rows), rows
    assert all(r.get("differentiation") for r in rows), rows
    assert not any("시점" in r["viewpoint"] for r in rows), rows
check("키 없이도 질문 기준으로 후보를 만든다", _angle_offline_by_question)
def _type_reads_intent():
    """유형은 제목 분류기가 아니라 질문에 맞는 형식을 고르는 단계다.

    예전에는 intent 를 넘기는데 프롬프트가 안 봤다. 그러면 제목 낱말로
    유형을 정한다 — "적용" 이 들어가면 케이스형인데 "CBAM 적용 대상은
    무엇인가" 는 정보형이다.
    """
    inp = SEEN["type"]
    assert inp["intent"]["question"], inp
    # 채널 전체가 아니라 독자 단계만. 홈페이지냐 네이버냐가 유형을 정하면 안 된다.
    assert "channel" not in inp and "reader_stage" in inp, sorted(inp)
    # 케이스형이 쓸 만한지 보려면 실제 사례가 있는지 알아야 한다
    assert set(inp["topic"]) == {"headline", "summary", "service_name",
                                "sources"}, inp["topic"]
    md = _md("type")
    assert "intent.question" in md and "판단 순서" in md
    assert "제목에 있는 것" not in md, "제목 낱말 매핑표가 남아 있다"
    assert "expertise_level이 입문이면 비교형" not in md
check("유형이 질문을 보고 정한다", _type_reads_intent)

def _type_validates_output():
    """목록 밖 이름은 버린다. 안 그러면 추천이 조용히 사라진다."""
    assert _ty._unfit([{"article_type": "trend", "reason": "x"},
                       {"article_type": "비교형", "reason": "대상이 하나"}],
                      "정보형") == {"비교형": "대상이 하나"}
    # 추천과 겹치는 것은 뺀다
    assert _ty._unfit([{"article_type": "정보형", "reason": "x"}], "정보형") == {}
    # 전부 부적합이면 통째로 지운다 — 고를 것이 없으면 화면이 막힌다
    assert _ty._unfit([{"article_type": n, "reason": "x"} for n in _ty.NAMES], "") == {}
check("유형 추천·부적합을 코드가 검증한다", _type_validates_output)

check("추천 이유가 확정값에 남는다", lambda: (
    _ty.payload("정보형", "질문이 개념을 묻는다")["type_reason"]
    and _ty.payload("정보형")["type_reason"] == "") or 1/0)

def _type_names_match_skeletons():
    """이름이 어긋나면 뜨자마자 터진다.

    예전에는 "사람이 맞춰 둔 것" 이라고 주석만 있었다. 어긋나면 구조 단계가
    골격을 못 찾고 조용히 일반 구조로 흐른다.
    """
    from backend.data import skeletons as _sk
    assert set(_ty.NAMES) == set(_sk.TYPES), (set(_ty.NAMES) ^ set(_sk.TYPES))
    src = (paths.BACKEND / "steps" / "type" / "__init__.py").read_text(encoding="utf-8")
    assert "raise RuntimeError" in src, "불일치를 코드가 안 막는다"
check("유형 이름과 골격 키가 어긋나면 터진다", _type_names_match_skeletons)

check("유형 메타에 검색의도 목록을 안 싣는다", lambda: all(
    "informational" not in h and "commercial" not in h
    for _, _, h in _ty.ARTICLE_TYPES) or 1/0)

def _intent_enum():
    """목록 밖 표기는 걸러 낸다.

    자유 문자열로 두면 "정보탐색"·"정보 탐색"·"탐색형" 이 섞여 들어와
    화면 표시가 KeyError 로 터지거나 뒤 규칙이 조용히 죽는다.
    """
    v = _in._one({"question": "질문?", "search_intent": "정보 탐색",
                  "sub_questions": ["a", "b", "c", "d", "e"],
                  "desired_action": "확인한다"})
    assert v["search_intent"] == "informational", v
    assert len(v["sub_questions"]) == _in.MAX_SUB, v
check("검색의도는 목록 밖 값을 걸러 낸다", _intent_enum)

def _intent_not_driven_by_enum():
    """의도 종류를 채우려고 질문을 만들지 않는다.

    "후보마다 search_intent 가 달라야 한다" 를 요구했더니 분류 체계가 질문을
    지배했다 — 정보 탐색 단계 독자에게 "무엇을 기준으로 고를까"(commercial)를
    억지로 묻게 되고, 그건 채널 규칙과 정면으로 부딪힌다.
    """
    md = _md("intent")
    assert "`search_intent` 가 서로 달라야 한다" not in md
    assert "완성된 질문을 보고" in md and "의도 종류를 채우려고" in md, md[:0]
    assert "reader_stage` 에 맞지 않는 의도는 후보에서 뺍니다" in md
check("질문을 먼저 만들고 의도를 나중에 분류한다", _intent_not_driven_by_enum)

def _intent_offline_by_stage():
    """키 없이 돌 때도 독자 단계에 맞는 후보만.

    정보 탐색 단계 독자는 아직 "대응 순서" 를 묻지 않는다.
    """
    base = {"topic": {"headline": "소재"}, "reader": {"role": "담당자"}}
    a = _in._offline({}, {**base, "channel": {"reader_stage": "정보 탐색"}})
    b = _in._offline({}, {**base, "channel": {"reader_stage": "대응 준비"}})
    assert [r["search_intent"] for r in a] == ["informational"], a
    assert "procedural" in [r["search_intent"] for r in b], b
    assert all(r.get("rationale") for r in a + b), "이유가 비었다"
check("키 없이도 독자 단계에 맞는 후보만", _intent_offline_by_stage)

def _intent_input_shape():
    """소재를 요약까지 보고, 채널은 필요한 것만, 가짜 키워드는 안 쓴다."""
    inp = SEEN["intent"]
    assert set(inp["topic"]) == {"headline", "summary", "service_name", "keywords"}
    assert set(inp["channel"]) == {"channel", "channel_goal", "reader_stage"}
    assert "keywords" not in inp, "옛 최상위 keywords 가 남았다"
    src = (paths.BACKEND / "steps" / "intent" / "__init__.py").read_text(encoding="utf-8")
    assert "import fake" not in src, "소재에 있는 값을 가짜 데이터로 다시 가져온다"
check("검색의도가 소재 범위를 본다", _intent_input_shape)

check("하위 질문은 없어도 된다", lambda: (
    "0~3개" in _md("intent") and "빈 배열로 둔다" in _md("intent")
    and "1~3개" not in _md("intent")) or 1/0)

check("읽고 나서 할 판단도 된다", lambda: (
    "두 제도의 차이를 구분한다" in _md("intent")
    and "구체적인 판단" in _md("intent")) or 1/0)

def _intent_rationale_shown():
    """만들고 버리던 값을 화면에 쓴다. 확정값에는 안 넣는다."""
    old = llm.generate
    llm.generate = lambda n, p, strong=False: {"candidates": [
        {"question": "무엇이 달라지는가?", "search_intent": "informational",
         "sub_questions": [], "desired_action": "범위를 확인한다",
         "rationale": "이 독자가 먼저 하는 질문이라서"}]}
    try:
        got = _in.make({}, {"reader": {}, "topic": {}, "channel": {}})
    finally:
        llm.generate = old
    assert "이 독자가 먼저 하는 질문이라서" in got[0]["meta"], got[0]["meta"]
    assert "rationale" not in got[0]["payload"], got[0]["payload"]
check("검색의도 이유가 화면에 남는다", _intent_rationale_shown)

check("소재에 있는 제도명은 써도 된다", lambda: (
    "제도명·기관명·표준명은 질문에 써도 된다" in _md("intent")) or 1/0)

def _intent_written_keeps():
    """직접 쓴 질문은 코드가 그대로 넣는다."""
    v = _st.written("intent", "내가 쓴 질문인가?", None)
    assert v["payload"]["question"] == "내가 쓴 질문인가?", v
    assert v["payload"]["sub_questions"] == [], v
check("직접 쓴 질문은 그대로 남는다", _intent_written_keeps)


print("\n── 근거가 구조·제목 앞이다 ──")

def _order_evidence_first():
    """근거 → 구조 → 제목.

    반대 순서였을 때 근거 찾기가 "이미 정한 결론을 뒷받침할 자료 찾기" 가
    됐다. 순서를 되돌리면 이 검사가 막는다.
    """
    k = _st.keys()
    assert k.index("evidence") < k.index("outline") < k.index("title"), k
check("근거 → 구조 → 제목 순이다", _order_evidence_first)

def _evidence_blind_to_title():
    """근거 입력에 제목도 소제목도 없다. 이게 순서를 바꾼 이유 전부다."""
    # 근거 단계의 첫 조각은 claims 다. evidence 프롬프트는 명제를 못 나눴을
    # 때만 도는 되돌림 경로라 평소에는 호출되지 않는다.
    inp = SEEN["claims"]
    assert "title" not in inp and "sections" not in inp, sorted(inp)
    assert inp["question"], inp
check("근거는 제목·소제목을 안 본다", _evidence_blind_to_title)

check("근거 입력에 질문이 실린다", lambda: (
    SEEN["claims"]["question"] and "article_type" in SEEN["claims"]) or 1/0)

def _outline_sees_claims():
    """구조가 명제를 상태째 본다.

    예전에는 confirmed 하나로 접었다. 그러면 "원문과 어긋남" 과 "아직
    못 찾음" 이 같은 값이 되고, claim_id 가 없어 배치를 이을 수도 없다.
    """
    ev = SEEN["site_outline"]["claims"]
    assert isinstance(ev, list) and ev, ev
    assert set(ev[0]) == {"claim_id", "claim", "claim_type", "status",
                          "authority", "limitations", "source_count"}, ev[0]
    assert "confirmed" not in ev[0], ev[0]
    # 소재도 제목 한 줄이 아니라 요약·키워드까지
    t = SEEN["site_outline"]["topic"]
    assert set(t) == {"headline", "summary", "service_name", "keywords"}, t
    assert t["summary"], "소재 요약이 비어 있다"
check("구조가 명제를 상태째 본다", _outline_sees_claims)

check("구조 입력에 검색의도가 실린다", lambda: (
    SEEN["site_outline"]["intent"]["question"]) or 1/0)

def _outline_brief_is_small():
    """전문을 싣지 않는다. 인용문과 URL 은 본문이 확정값에서 다시 읽는다."""
    ev = SEEN["site_outline"]["claims"]
    assert not any("sources" in x or "url" in x for x in ev), ev
check("구조에 근거 전문은 안 싣는다", _outline_brief_is_small)

def _title_sees_structure():
    """제목이 구조를 **내용째** 본다.

    소제목 문자열만 넘기면 구조를 앞에 둔 효과가 절반 사라진다 —
    "달라지는 기준은 검증 가능성이다" 만 봐서는 무엇이 검증되는지,
    그게 확인된 사실인지 모른다.
    """
    inp = SEEN["site_title"]
    secs = inp["sections"]
    assert isinstance(secs, list) and secs, secs
    assert set(secs[0]) == {"title", "objective", "covers", "exclude",
                            "claim_refs"}, secs[0]
    assert inp["intent"]["question"], inp
    assert "question" not in inp, "옛 최상위 question 이 남았다"
    assert set(inp["topic"]) == {"headline", "summary", "service_name"}
    assert "claims" in inp, sorted(inp)
check("제목이 구조를 내용째 본다", _title_sees_structure)

def _title_claims_are_referenced_only():
    """구조가 claim_refs 로 건 명제만 넘긴다."""
    from backend.steps.title import _claims
    d = {"outline": {"payload": {"sections": [
            {"title": "가", "claim_refs": ["c01"]}]}},
         "evidence": {"payload": {"items": [
            {"claim_id": "c01", "claim": "쓴 명제", "status": "partial",
             "authority": "limited", "claim_type": "regulation",
             "sources": [{"limitations": ["수입자 기준"]}]},
            {"claim_id": "c02", "claim": "안 쓴 명제", "status": "supported"}]}}}
    got = _claims(d, [{"title": "가", "claim_refs": ["c01"]}])
    assert [c["claim_id"] for c in got] == ["c01"], got
    assert got[0]["authority"] == "limited" and got[0]["limitations"], got[0]
check("제목은 구조가 쓴 명제만 본다", _title_claims_are_referenced_only)


print("\n── 자취 로그 ──")
rows = history.read()
kinds = [(r.get("kind"), r["step"]) for r in rows]
check("topic generated 있다",  lambda: ("generated","topic") in kinds or 1/0)
check("topic confirmed 있다",  lambda: ("confirmed","topic") in kinds or 1/0)
for k in _WALK:
    check(f"{k} 생성+확정", lambda k=k: (("generated",k) in kinds and ("confirmed",k) in kinds) or 1/0)
check("write 기록",            lambda: any(r.get("kind")=="written" for r in rows) or 1/0)
# 이 시점엔 아직 평가를 남기지 않았으므로 feedback/ 은 없을 수 있다.
# "행이 있는 갈래는 오늘 파일 한 개" 만 본다.
check("파일이 실제로 있다",      lambda: (
    {"choice", "response"} <= {x for x, n in history.counts().items() if n}
    and all(len(list((paths.ROOT / x).glob("*.jsonl"))) == 1
            for x, n in history.counts().items() if n)) or 1/0)
check("모든 줄이 JSON 이다",     lambda: all(json.loads(l) for x in history.STREAMS
                                          for f in (paths.ROOT / x).glob("*.jsonl")
                                          for l in f.read_text(encoding="utf-8").splitlines() if l.strip()))

print("\n── 직접 쓰기 ──")
c2 = TestClient(app)
def written_path():
    c2.get("/api/topics")
    c2.post("/api/topics/pick", json={"topic_id":None,"custom":"LCA란 무엇인가"})
    c2.get("/api/draft/reader")
    assert c2.post("/api/draft/reader", json={"choice":[],"custom":"구매 담당자"}).json()["ok"]
check("소재·독자 직접 쓰기", written_path)
check("reader_written 기록", lambda: any(r["step"]=="reader_written" for r in history.read()) or 1/0)
def topic_written():
    r = [x for x in history.read() if x.get("kind")=="confirmed" and x["step"]=="topic"][-1]
    assert r["written"] == "LCA란 무엇인가" and len(r["offered"]) == 9, r
check("직접 쓴 소재가 목록과 함께 남음", topic_written)

print("\n── 구조 왕복 ──")
def roundtrip():
    c3 = TestClient(app); journey(c3)
    import backend.session as S
    d = [v["draft"] for v in S._sessions.values() if v["draft"].get("outline")][-1]
    pay = d["outline"]["payload"]
    txt = "\n".join(
        [x["title"] + (f"\n  이미지: {x['image']['form']} — {x['image']['purpose']}" if x["image"] else "")
         for x in pay["sections"]])
    r = c3.post("/api/draft/outline", json={"choice":[],"custom":txt})
    assert r.json()["ok"], r.json()
    d2 = [v["draft"] for v in S._sessions.values() if v["draft"].get("outline")][-1]
    got = d2["outline"]["payload"]["sections"]
    assert [x["title"] for x in got] == [x["title"] for x in pay["sections"]], got
    assert sum(1 for x in got if x["image"]) == sum(1 for x in pay["sections"] if x["image"])
check("복사 → 붙이기 → 이미지 보존", roundtrip)

print("\n── 표현 블록 ──")

def _art(sections):
    return {"topic_id":"t1","topic":{"label":"소재","detail":"","payload":{}},
            "title":{"payload":{"title":"제목","used_keywords":[]}},
            "outline":{"payload":{"sections":[],"hero_image":None}},
            "write":{"lead":"도입.","sources":[],"unverified":[],
                     "dropped_figures":[],"sections":sections}}

FIG = {"type":"figure","component":"대조표","caption":"비교",
       "takeaway":"해석 문장입니다.",
       "data":{"columns":["가","나"],
               "rows":[{"criterion":"ㄱ","cells":["1","2"]},
                       {"criterion":"ㄴ","cells":["3","4"]}]}}
ALL = _art([{"heading":"섹션","blocks":[
    {"type":"para","text":"문단."},
    {"type":"list","items":[{"title":"제목1","body":"설명1"},{"title":"제목2","body":"설명2"}]},
    {"type":"check","items":["확인했는가","연결되는가"]},
    {"type":"callout","label":"핵심","text":"핵심 한 문장."},
    FIG,
    {"type":"없는타입","text":"버려져야 한다"}]}])
def as_channel(d, name):
    """그 채널로 확정된 드래프트. 한 드래프트는 한 채널이라 둘을 보려면
    같은 본문으로 두 번 만든다."""
    return {**d, "channel": {"label": name, "payload": {"channel": name}}}


def _render(d, name):
    return _r.build(as_channel(d, name))[name]


NAV, SITE = _render(ALL, "naver")["html"], _render(ALL, "site")["html"]

check("문단 · 목록 · 체크 · 강조 · 도식이 다 그려진다",
      lambda: all(x in SITE for x in ("post-list","post-check","post-callout",
                                      "post-takeaway","fig-cmp")) or 1/0)
check("모르는 블록 타입은 버린다", lambda: ("버려져야" not in SITE and "버려져야" not in NAV) or 1/0)

import re as _re
NAVER_OK = {"p","br","strong","b","em","i","u","s","a","ul","ol","li","blockquote"}
check("네이버가 안전 태그만 쓴다",
      lambda: (set(_re.findall(r"<(\w+)", NAV)) <= NAVER_OK) or 1/0)
check("네이버에 목록·강조가 그대로 간다",
      lambda: all(t in NAV for t in ("<ol ", "<blockquote ")) or 1/0)
check("체크 문항에 □ 가 글자로 들어간다", lambda: "□ 확인했는가" in NAV or 1/0)
check("도식은 네이버에서 자리표시로 빠진다",
      lambda: ("[도식 1 삽입]" in NAV and "<table" not in NAV) or 1/0)
check("takeaway 가 네이버에 텍스트로 남는다", lambda: "해석 문장입니다." in NAV or 1/0)
check("takeaway 가 <figure> 밖에 있다",
      lambda: (SITE.index("</figure>") < SITE.index("해석 문장입니다.")) or 1/0)

OLD = _art([{"heading":"옛","paragraphs":["옛 문단."],
             "figure":{"component":"항목카드","caption":"옛 도식",
                       "data":{"cards":[{"title":"가","body":"ㄱ"},{"title":"나","body":"ㄴ"}]}}}])
O = _render(OLD, "site")
check("옛 스키마도 그대로 그려진다",
      lambda: ("옛 문단." in O["html"] and "fig-cards" in O["html"]) or 1/0)

MIX = _art([{"heading":"새","blocks":[FIG]},
            {"heading":"옛","paragraphs":["ㅁ"],
             "figure":{"component":"항목카드","caption":"둘째",
                       "data":{"cards":[{"title":"가","body":"ㄱ"},{"title":"나","body":"ㄴ"}]}}}])
M = _render(MIX, "naver")["html"]
check("새·옛이 섞여도 도식 번호가 이어진다",
      lambda: ("[도식 1 삽입]" in M and "[도식 2 삽입]" in M) or 1/0)

check("목록 제목과 설명이 줄로 끊긴다",
      lambda: ("</strong><br>" in NAV and "</strong><br>" in SITE) or 1/0)
check("체크 문항의 □ 가 두 갈래 모두 글자로 들어간다",
      lambda: ("□ 확인했는가</p>" in NAV and "<li>□ 확인했는가</li>" in SITE) or 1/0)
check("본문 CSS 가 ::before 로 내용을 그리지 않는다",
      lambda: ("::before" not in _site_r.BODY_CSS) or 1/0)
check("네이버 도식 안내에 작업 지시가 없다",
      lambda: ("홈페이지 탭" not in NAV and "넣으세요" not in NAV) or 1/0)

check("체크리스트 별칭이 사라졌다",
      lambda: (__import__("backend.output.figures", fromlist=["x"]).component_of("체크리스트") is None) or 1/0)

print("\n── 응답 원문이 자취에 남나 ──")

def _texted(texts):
    """원문을 실제로 parse 에 태워 LAST 가 채워지게 한다."""
    def g(name, payload, strong=False):
        t = texts(name)
        llm.LAST[name] = t[:llm.RAW_MAX]
        return llm.parse(t)
    return g

_RAWTXT = {
 "reader": '{"candidates":[{"role":"담당자","expertise_level":"실무",'
           '"decision_authority":"추천자","pain_points":["a"],"preferred_terms":["b"],'
           '"avoid_terms":[]},{"role":"","expertise_level":"실무",'
           '"decision_authority":"추천자","pain_points":[],"preferred_terms":[],'
           '"avoid_terms":[]}]}',
 "claims": '{"claims":[{"claim":"명제 하나입니다","claim_type":"regulation",'
           '"required_source":"원문","searchable":true,"why":"근거"}]}',
 "plan": '{"plans":[]}',
 "intent": '{"candidates":[{"question":"질문인가?",'
           '"search_intent":"informational","sub_questions":[],'
           '"desired_action":"확인한다"}]}',
 "angle": '{"candidates":[{"viewpoint":"v","core_message":"m.",'
           '"differentiation":"d","tone":["실무적"]}]}',
 "type": '{"recommended":"동향형","rationale":"r","unfit":[]}',
 "site_title": '{"candidates":[{"title":"제목","title_style":"x","used_keywords":[]}]}',
 "site_outline": '{"candidates":[{"sections":[{"title":"가","objective":"o","covers":["c"],'
            '"exclude":[],"image":null}],"hero_image":{"purpose":"p"},"rationale":"r"}]}',
 "evidence": '{"candidates":[{"kind":"규제","title":"e","claim_to_verify":"c",'
             '"detail":"1","where_to_look":"원문"}]}',
 "site_write": '{"lead":"도입.","sections":[{"order":1,"cites":[],"blocks":['
          '{"type":"para","text":"문단입니다."},'
          '{"type":"list","items":[{"title":"하나뿐","body":""}]}]}]}',
 "site_hero": '{"prompt":"editorial illustration, no text","alt":"대체"}',
}

def _raw_run():
    old = llm.generate
    llm.generate = _texted(lambda n: _RAWTXT[n])
    _im.ENABLED = True
    _im.draw = lambda p: b"\x89PNG"
    c = TestClient(app)
    c.get("/api/topics"); c.post("/api/topics/pick", json={"topic_id": "t1"})
    for k in _WALK:
        o = c.get(f"/api/draft/{k}").json()["options"]
        c.post(f"/api/draft/{k}",
               json={"choice": (["동향형"] if k == "type" else [o[0]["id"]]), "custom": ""})
    c.post("/api/draft/write")
    llm.generate = old
    return c

_RC = _raw_run()

def raw_on_rows():
    """이 세션 것만 본다. 다른 검사는 가짜 generate 를 쓰므로 원문이 없다."""
    sids = {r["sid"] for r in history.read() if r["step"] == "write"}
    rows = [r for r in history.read()
            if r.get("kind") in ("generated", "written")
            and r["step"] != "topic" and r["raw"] != ""]
    steps = {r["step"] for r in rows}
    # 원문은 프롬프트를 부른 단계에만 붙는다. 채널은 후보를 코드가 만든다.
    want = {k for k in _WALK if _st.uses_llm(k)} | {"write", "hero"}
    # 근거는 자기 이름으로 프롬프트를 부르지 않는다. 조각들(claims·plan·
    # check)이 각자 이름으로 남기므로 원문도 그쪽 행에 붙는다.
    want = (want - {"evidence"}) | {"claims"}

    assert want <= steps, sorted(want - steps)
check("생성·본문 행마다 원문이 붙는다", raw_on_rows)

def dropped_visible():
    g = [r for r in history.read()
         if r.get("kind") == "generated" and r["step"] == "reader"][-1]
    assert len(g["options"]) == 1, g["options"]
    assert len(json.loads(g["raw"])["candidates"]) == 2, "원문에 버려진 후보가 없다"
check("버려진 후보가 원문에는 남아 있다", dropped_visible)

def dropped_block():
    w = [r for r in history.read()
         if r.get("kind") == "written" and r["step"] == "write"][-1]
    kept = [b["type"] for b in w["output"]["sections"][0]["blocks"]]
    orig = [b["type"] for b in json.loads(w["raw"])["sections"][0]["blocks"]]
    assert kept == ["para"] and orig == ["para", "list"], (kept, orig)
check("버려진 블록이 원문에는 남아 있다", dropped_block)

def parse_fail_raw():
    old = llm.generate
    llm.generate = _texted(lambda n: "이건 JSON 이 아닙니다")
    c = TestClient(app)
    c.get("/api/topics"); c.post("/api/topics/pick", json={"topic_id": "t1"})
    walk_to(c, "reader")
    r = c.get("/api/draft/reader").json()
    llm.generate = old
    assert r["ok"] is False, r
    f = [x for x in history.read() if x.get("kind") == "failed" and x["step"] == "reader"][-1]
    assert f["raw"] == "이건 JSON 이 아닙니다", f
check("파싱이 깨져도 원문이 남는다", parse_fail_raw)

check("원문 길이에 상한이 있다", lambda: (llm.RAW_MAX == 20000) or 1/0)
check("소재는 원문이 없다 (시트에서 온다)",
      lambda: all(not r.get("raw") for r in history.read()
                  if r.get("kind") == "generated" and r["step"] == "topic") or 1/0)

print("\n── 화면용 조각이 결과물에 안 섞이나 ──")

check("Edit.clean 이 data-ui 를 걷어낸다",
      lambda: ("querySelectorAll('[data-ui]')" in _js("edit.js")) or 1/0)
check("도식 저장 줄에 data-ui 표시가 있다",
      lambda: _js("pages/result.js").count("dataset.ui = '1'") >= 2 or 1/0)
check("저장 버튼 마크업이 결과물에 안 들어간다",
      lambda: ("fig-save" not in _js("edit.js")) or 1/0)
check("코드 보기에서 돌아오면 저장 버튼을 다시 붙인다",
      lambda: ("cells(prev); shots();" in _js("pages/result.js")) or 1/0)
check("다시 붙일 때 남은 것을 먼저 걷어낸다",
      lambda: ("querySelectorAll('.fig-save').forEach" in _js("pages/result.js")) or 1/0)
check("내려받는 HTML 은 그대로 열 수 있는 완성본이다",
      lambda: all(x in _js("pages/result.js")
                  for x in ("<!DOCTYPE html>", 'charset="utf-8"',
                            "pretendard", "여기서부터")) or 1/0)

print("\n── 이미지 품질 ──")

check("도식을 정해진 폭으로 다시 그려 찍는다",
      lambda: ("function framed(" in _js("shot.js")
               and "windowWidth: w" in _js("shot.js")) or 1/0)
check("도식에 여백을 두른다",
      lambda: ("padding:' + PAD + 'px" in _js("shot.js")) or 1/0)

def _capture_from_backend():
    """캡처 폭을 화면에 박아 두지 않는다.

    네이버는 휴대폰 폭이라 좁고 글자가 크다. 그 값이 화면에도 서버에도
    있으면 둘을 맞춰야 하고, 안 맞으면 조용히 다른 그림이 나간다.
    """
    from backend.data import channels as _cn, skeletons as _sk
    assert _cn.capture("naver")["width"] < _cn.capture("site")["width"]
    assert "Shot.setStyle(out.capture)" in _js("pages/result.js")
    assert "capture" in _r.build({}), _r.build({}).keys()
check("캡처 폭은 백엔드가 정한다", _capture_from_backend)
check("찍은 뒤 임시 요소를 치운다",
      lambda: _js("shot.js").count("box.remove()") >= 2 or 1/0)
check("정사각은 가운데를 남긴다",
      lambda: ("(img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2"
               in _js("shot.js")) or 1/0)
check("대표 이미지에 16:9 · 1:1 저장이 둘 다 있다",
      lambda: all(x in _js("pages/result.js")
                  for x in ('id="hero-dl"', 'id="hero-sq"')) or 1/0)
check("파일 이름에 제목이 들어간다",
      lambda: ("-대표-16x9" in _js("pages/result.js")
               and "-대표-1x1" in _js("pages/result.js")) or 1/0)
check("naver hero 는 1:1 이고 가운데를 지킨다", lambda: (
    "1:1 square composition" in _md("naver_hero")
    and "가운데 80%" in _md("naver_hero")
    and "16:9" not in _md("naver_hero")) or 1/0)
check("site hero 가 16:9 를 요구한다",
      lambda: ("16:9 wide horizontal composition" in _md("site_hero")) or 1/0)
check("site hero 가 작아져도 읽히라고 한다",
      lambda: ("작아져도 무엇을 다루는 글인지" in _md("site_hero")) or 1/0)

print("\n── 결과물 내려받기 ──")

check("UI 에 내려받기 helper 가 있다",
      lambda: ("function download(" in _js("ui.js")
               and "function safeName(" in _js("ui.js")) or 1/0)
check("HTML 과 텍스트 저장 버튼이 있다",
      lambda: all(x in _js("pages/result.js")
                  for x in ('id="s-dl"', 'id="n-dl"', 'id="n-html"')) or 1/0)
check("네이버 완성본도 코드로 받는다",
      lambda: ("function naverFile(" in _js("pages/result.js")
               and "-네이버" in _js("pages/result.js")) or 1/0)
check("네이버 파일에 제목 · 본문 · 태그가 다 있다",
      lambda: all(x in _js("pages/result.js")
                  for x in ("제목 칸", "본문 칸", "태그 칸")) or 1/0)
def _inline_from_backend():
    from backend.data import brand as _br
    """드래그 복사에서 살아남게 인라인 서식을 붙인다. **백엔드가 붙인다.**

    화면에서 태그 종류만 보고 덧칠하면 소제목·리드·도식 자리를 구별하지
    못한다. 실제로 강조 박스가 브랜드 색 대신 회색(#ddd)으로 나갔다.
    """
    js = _js("pages/result.js")
    assert "function inlined(" in js
    assert "el.style.borderLeft" not in js, "화면이 스타일을 덧칠한다"
    code = "\n".join(l.split("*")[0] if l.strip().startswith("*") else l
                     for l in js.splitlines())
    assert "el.style" not in code, "화면이 스타일을 덧칠한다"
    # 백엔드가 브랜드 값으로 붙인다
    assert _br.COLORS["accent"] in NAV, "네이버 결과물에 브랜드 색이 없다"
    assert 'style="margin:32px' in NAV, "소제목 여백이 본문과 같다"
check("드래그 복사에서 살아남게 인라인 서식을 입힌다", _inline_from_backend)

def _naver_rhythm():
    """읽는 리듬이 자리마다 안 어긋난다.

    본문에 line-height 를 안 주면 에디터 기본(1.5~1.6)이 먹어서 **글에서
    제일 많은 자리만 빽빽해진다.** 리드·목록·강조는 다 1.8~1.9 인데
    본문만 빠져 있었다.
    """
    from backend.data import brand as _br2
    S = _br2.NAVER
    for k in ("para", "lead", "item", "callout_body"):
        assert "line-height" in S[k], f"{k} 에 line-height 가 없다"
    # 소제목 위 여백이 문단 사이보다 훨씬 커야 섹션이 갈려 보인다
    assert S["heading"].startswith("margin:32px") and "0 18px" in S["para"]
check("네이버 본문 리듬이 자리마다 맞다", _naver_rhythm)

def _callout_label_survives():
    """라벨과 본문이 각각 <p> 다.

    display:block 에 기대면 에디터가 그것을 지웠을 때 라벨과 본문이
    "실무 포인트여러 채널에..." 로 붙는다.
    """
    from backend.data import brand as _br3
    assert "display:block" not in _br3.NAVER["callout_label"], "display 에 기댄다"
    src = (paths.BACKEND / "output" / "naver" / "render.py").read_text(encoding="utf-8")
    assert 'callout_label"]}">{_e(b["label"])}</p>' in src, "라벨이 <p> 가 아니다"
    assert "callout_body" in src, "본문이 별도 <p> 가 아니다"
check("강조 박스 라벨이 본문과 안 붙는다", _callout_label_survives)

def _slot_stays_dashed():
    """그림 자리는 점선이다.

    실선은 "완성된 정보 박스" 로 보인다. 여기는 아직 비어 있고 사람이
    채워야 하는 자리다. 그림을 넣으면 상자째 사라지는 것과도 맞다.
    """
    from backend.data import brand as _br4
    slot = _br4.NAVER["slot"]
    assert "dashed" in slot and _br4.COLORS["surface"] in slot, slot
    assert "#FAFBFC" not in slot, "brand 에 없는 색을 박았다"
check("그림 자리는 점선으로 둔다", _slot_stays_dashed)
check("네이버 파일에 화면용 조각이 안 들어간다",
      lambda: ("box.querySelectorAll('[data-ui]')" in _js("pages/result.js")) or 1/0)
check("고친 내용이 반영되도록 sync 를 먼저 부른다",
      lambda: _js("pages/result.js").count("sync();") >= 4 or 1/0)
check("HTML 에는 BOM 을 붙이지 않는다",
      lambda: ("mime === 'text/plain' ? \"\\ufeff\" + text : text" in _js("ui.js")) or 1/0)

print("\n── 소제목·본문 규칙이 프롬프트에 있나 ──")

check("소제목 꼴을 섞으라는 규칙이 있다",
      lambda: ("이어지는 두 소제목을 같은 꼴로 쓰지 않는다" in _md("_prompt", "outline")) or 1/0)
check("강조 박스는 섹션 끝",
      lambda: ("callout` 은 섹션 끝에 둡니다" in _md("_write")) or 1/0)
check("체크 문항은 하나만 묻는다",
      lambda: ("한 문항에 하나만 묻습니다" in _md("_write")) or 1/0)
check("같은 낱말 되풀이 금지",
      lambda: ("같은 낱말을 글 전체에서 되풀이하지 않습니다" in _md("_write")) or 1/0)
check("목록 title 문법 통일",
      lambda: ("title` 의 문법도 맞춥니다" in _md("_write")) or 1/0)

print("\n── 대표 이미지 ──")
_PNG = _b64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

def _hero_client():
    _im.ENABLED = True
    _im.draw = lambda p: _PNG
    old = llm.generate
    def gen(n, p, strong=False):
        if n == "hero":
            return {"prompt": "editorial illustration, no text, not a photograph",
                    "alt": "대체 텍스트"}
        return old(n, p, strong)
    llm.generate = gen
    c = TestClient(app)
    c.get("/api/topics"); c.post("/api/topics/pick", json={"topic_id": "t1"})
    for k in _WALK:
        o = c.get(f"/api/draft/{k}").json()["options"]
        c.post(f"/api/draft/{k}",
               json={"choice": (["동향형"] if k == "type" else [o[0]["id"]]), "custom": ""})
    return c

_HC = _hero_client()

def made():
    r = _HC.post("/api/draft/hero").json()
    assert r["ok"] and r["hero"]["file"].endswith(".png"), r
    assert r["hero"]["bytes"] == len(_PNG), r
check("대표 이미지를 만들어 저장한다", made)

check("파일을 내려받을 수 있다",
      lambda: (_HC.get("/api/draft/hero.png").headers.get("content-type") == "image/png")
              or 1/0)
check("hero.png 가 단계 이름으로 안 잡힌다",
      lambda: (_HC.get("/api/draft/hero.png").status_code == 200) or 1/0)

_DREW = []

def auto_on_write():
    _im.draw = lambda p: (_DREW.append(p), _PNG)[1]
    c = TestClient(app)
    c.get("/api/topics"); c.post("/api/topics/pick", json={"topic_id": "t1"})
    for k in _WALK:
        o = c.get(f"/api/draft/{k}").json()["options"]
        c.post(f"/api/draft/{k}",
               json={"choice": (["동향형"] if k == "type" else [o[0]["id"]]), "custom": ""})
    n0 = len(_DREW)
    assert c.post("/api/draft/write").json()["ok"]
    assert len(_DREW) == n0 + 1, "본문을 만들어도 이미지가 안 생겼다"
    # 본문을 다시 만들어도 이미지는 그대로
    c.post("/api/draft/write")
    assert len(_DREW) == n0 + 1, "본문을 다시 만들 때 이미지도 다시 만들었다"
    # 버튼으로는 다시 만든다
    c.post("/api/draft/hero")
    assert len(_DREW) == n0 + 2, "다시 만들기 버튼이 안 먹는다"
check("본문을 만들면 대표 이미지가 따라온다", auto_on_write)

def image_fail_ok():
    _im.draw = lambda p: (_ for _ in ()).throw(_im.ImagenError("HTTP 429 quota exceeded"))
    c = TestClient(app)
    c.get("/api/topics"); c.post("/api/topics/pick", json={"topic_id": "t1"})
    for k in _WALK:
        o = c.get(f"/api/draft/{k}").json()["options"]
        c.post(f"/api/draft/{k}",
               json={"choice": (["동향형"] if k == "type" else [o[0]["id"]]), "custom": ""})
    assert c.post("/api/draft/write").json()["ok"], "이미지 실패가 본문을 막았다"
    r = c.get("/api/draft/result").json()
    assert r["ok"] and r["hero"] is None, r
    assert "429" in r["hero_error"], r["hero_error"]
    assert "HERO_SLOT" in r["out"]["site"]["html"], "자리표시로 안 돌아갔다"
    _im.draw = lambda p: _PNG
check("이미지가 실패해도 본문은 나가고 이유가 남는다", image_fail_ok)

def in_output():
    _HC.post("/api/draft/write")
    r = _HC.get("/api/draft/result").json()
    assert r.get("ok"), r
    out = r["out"]
    # 한 드래프트는 한 채널이다. 이 세션은 홈페이지로 돌았다.
    assert out["channel"] == "site" and out["naver"] is None, out["channel"]
    assert "post-hero" in out["site"]["html"], "홈페이지에 img 가 없다"
    kinds = [x.get("kind") for x in out["checklist"]]
    assert "이미지 확인" in kinds and "이미지 없음" not in kinds, kinds
check("고른 채널 결과물과 점검표에 반영된다", in_output)

def hero_trail():
    rows = [r for r in history.read()
            if r["step"] == "hero" and r.get("kind") == "written"]
    assert rows, "hero written 행이 없다"
    assert rows[-1]["output"]["prompt"], rows[-1]
check("자취에 남는다", hero_trail)

def no_plan():
    c = TestClient(app)
    c.get("/api/topics"); c.post("/api/topics/pick", json={"topic_id": "t1"})
    r = c.post("/api/draft/hero").json()
    assert r["ok"] is False and "계획" in r["detail"], r
check("계획이 없으면 이유를 준다", no_plan)

def boom():
    def bad(p): raise _im.ImagenError("HTTP 429 quota exceeded")
    _im.draw = bad
    r = _HC.post("/api/draft/hero").json()
    _im.draw = lambda p: _PNG
    assert r["ok"] is False and "429" in r["detail"], r
    assert any(x.get("kind") == "failed" and x["step"] == "hero" for x in history.read())
check("실패하면 이유가 화면과 자취에 남는다", boom)

def parse_shape():
    got = {"candidates": [{"content": {"parts": [
        {"text": "설명"},
        {"inlineData": {"mimeType": "image/png",
                        "data": _b64.b64encode(_PNG).decode()}}]}}]}
    assert _im._bytes(got) == _PNG
check("응답에서 자리가 아니라 inlineData 로 찾는다", parse_shape)

def blocked():
    got = {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}
    try:
        _im._bytes(got)
    except _im.ImagenError as e:
        assert "SAFETY" in str(e), e
        return
    raise AssertionError("막힌 응답이 통과했다")
check("이미지 없는 응답은 이유와 함께 실패한다", blocked)

print("\n── 근거 라벨 ──")

def _ev(url=None):
    return {"id": "x", "title": "t", "summary": "s",
            "payload": _ev_step.payload("기사", "t", url=url) if url
                       else _ev_step.payload("규제", "t")}

check("확인된 것과 확인 필요를 갈라 센다",
      lambda: _st.many_label("evidence", [_ev("http://a")] * 2 + [_ev()] * 3)
              == "확인된 출처 2건 · 확인 필요 3건"
              or (_ for _ in ()).throw(AssertionError(
                  _st.many_label("evidence", [_ev("http://a")] * 2 + [_ev()] * 3))))
check("한쪽만 있으면 그것만 적는다",
      lambda: (_st.many_label("evidence", [_ev("http://a")] * 2) == "확인된 출처 2건"
               and _st.many_label("evidence", [_ev()] * 5) == "확인 필요 5건") or 1/0)
check("다른 단계는 그대로 N건",
      lambda: _st.many_label("outline", [_ev()] * 3) == "3건" or 1/0)
check("직접 쓴 근거는 확인 필요로",
      lambda: _st.written("evidence", "가\n나")["label"] == "확인 필요 2건"
              or (_ for _ in ()).throw(AssertionError(
                  _st.written("evidence", "가\n나")["label"])))
check("근거 5건 이라는 말이 안 나온다",
      lambda: ("근거" not in _st.many_label("evidence", [_ev()] * 5)) or 1/0)

print("\n── 유형별 본문 규칙 ──")

def all_types_have_blocks():
    bad = [n for n, t in _sk.TYPES.items()
           if not (t.get("blocks", {}).get("center")
                   and t["blocks"].get("prefer") and t["blocks"].get("avoid"))]
    assert not bad, bad
check("여섯 유형 모두 center · prefer · avoid 가 있다", all_types_have_blocks)

def only_own_type():
    g = _sk.for_write("정보형")
    flat = json.dumps(g, ensure_ascii=False)
    assert "체크리스트가 글의 중심" not in flat, "다른 유형 규칙이 섞였다"
    assert "실행 순서가 글의 중심이 되는 것" in flat, g
check("해당 유형 규칙만 실린다", only_own_type)

def not_in_prompt():
    md = _md("_write")
    for phrase in ("체크리스트가 글의 중심이다", "실행 순서는 순서열이 기본이다"):
        assert phrase not in md, phrase
    assert "type_guide.blocks" in md, "write.md 가 blocks 를 안 본다"
check("유형 규칙을 write.md 에 복사하지 않았다", not_in_prompt)

def reaches_write():
    d = {"topic":{"label":"x","payload":{}},"title":{"payload":{"title":"t"}},
         "reader":{"payload":{}},"angle":{"payload":{}},
         "type":{"payload":{"article_type":"체크리스트형"}},
         "evidence":{"payload":{"items":[]}},
         "outline":{"payload": _outline_pay(["가"])}}
    g = _wr.build_input(d)["type_guide"]
    assert g["blocks"]["center"].startswith("우리는 준비되어"), g["blocks"]
check("본문 작성 입력에 들어간다", reaches_write)

print("\n── 제목이 유형과 어긋나면 ──")

def _titles(atype, titles):
    llm.generate = lambda n, p, strong=False: {"candidates": [
        {"title": t, "title_style": "x", "used_keywords": []} for t in titles]}
    d = {"topic": {"label": "x", "payload": {}},
         "reader": {"payload": _rd.payload("r")},
         "angle": {"payload": _ag.payload("v", "m", ["a"])},
         "type": {"payload": _ty.payload(atype)}}
    return _st.options("title", d, refresh=True)

def drop_info():
    got = _titles("정보형", ["DPP 도입 대응 방법", "디지털 제품여권이란 무엇인가",
                             "DPP 준비 단계 정리", "제품 정보 체계는 어떻게 구성되나"])
    ts = [x["title"] for x in got]
    assert len(ts) == 2 and "대응 방법" not in " ".join(ts), ts
check("정보형에서 실행 어휘 제목을 버린다", drop_info)

def drop_guide():
    got = _titles("가이드형", ["CBAM이란 무엇인가", "CBAM 신고 준비 5단계"])
    assert [x["title"] for x in got] == ["CBAM 신고 준비 5단계"], got
check("가이드형에서 개념 제목을 버린다", drop_guide)

def all_bad():
    got = _titles("정보형", ["DPP 대응 방법", "DPP 대응 전략", "DPP 준비 단계"])
    assert len(got) == 3, got
    assert all("안 맞는 표현" in x["meta"] for x in got), [x["meta"] for x in got]
check("전부 어긋나면 지우지 않고 표시한다", all_bad)

def untouched():
    got = _titles("동향형", ["CBAM 대응 방법", "무엇이 달라지나"])
    assert len(got) == 2, got
check("목록에 없는 유형은 건드리지 않는다", untouched)

check("id 가 다시 매겨진다",
      lambda: [x["id"] for x in _titles("정보형",
               ["DPP 대응 방법", "DPP란 무엇인가", "DPP 준비 단계", "DPP 구성 요소"])]
              == ["t0", "t1"] or 1/0)

print("\n── 섹션 범위가 6단계에서 9단계로 ──")

def _draft(secs):
    return {"topic":{"label":"x","payload":{}},"title":{"payload":{"title":"제목"}},
            "reader":{"payload":{}},"angle":{"payload":{}},
            "type":{"payload":{"article_type":"동향형"}},
            "evidence":{"payload":{"items":[]}},
            "outline":{"payload": _outline_pay(secs)}}

FULL = [{"title":"가","objective":"결론 한 줄","covers":["ㄱ","ㄴ"],
         "exclude":["ㄷ"],"image":None},
        {"title":"나","objective":"둘째 결론","covers":["ㄹ"],"exclude":[],
         "image":{"purpose":"p","form":"대조표"}}]

def passes():
    got = _wr.build_input(_draft(FULL))["sections"]
    assert got[0]["objective"] == "결론 한 줄", got[0]
    assert got[0]["covers"] == ["ㄱ","ㄴ"], got[0]
    assert got[0]["exclude"] == ["ㄷ"], got[0]
check("objective · covers · exclude 가 넘어간다", passes)

check("빈 exclude 는 키째 빠진다",
      lambda: ("exclude" not in _wr.build_input(_draft(FULL))["sections"][1]) or 1/0)

def handwritten():
    """직접 쓴 구조에는 설계 의도가 없다. 빈 키는 빼서 보낸다.

    claim_refs 는 빈 배열이라도 늘 보낸다 — 본문 코드가 "배치가 없는
    섹션" 과 "배치가 빈 섹션" 을 같게 다뤄야 해서다.
    """
    got = _wr.build_input(_draft(["가", "나"]))["sections"]
    assert set(got[0]) == {"order", "heading", "figure", "claim_refs"}, got[0]
    assert got[0]["claim_refs"] == [], got[0]
check("직접 쓴 구조에는 설계 의도가 안 붙는다", handwritten)

def _written_refs():
    """직접 쓸 때도 근거를 이을 수 있다. 다만 강요하지 않는다."""
    _, _, pay = _out.parse.read("소제목 하나\n근거: c01, c02\n소제목 둘")
    assert pay["sections"][0]["claim_refs"] == ["c01", "c02"], pay["sections"][0]
    # 안 적으면 빈 배열. 자동으로 붙이거나 제목 비슷하다고 잇지 않는다.
    assert pay["sections"][1]["claim_refs"] == [], pay["sections"][1]
check("직접 쓴 구조에도 근거를 이을 수 있다", _written_refs)

def _refs_are_contract():
    """구조가 정한 배치를 본문이 못 벗어난다.

    claim_refs 를 참고로만 두면 본문이 다시 배치하고 구조 단계가 한 판단이
    사라진다. 프롬프트로 막고 코드가 한 번 더 막는다.
    """
    old = dict(_wr._CID)
    _wr._CID.update({"s0": "c01", "s1": "c02"})
    try:
        plan = [{"order": 1, "heading": "h", "figure": None, "claim_refs": ["c01"]}]
        got = {"lead": "리드", "sections": [
            {"order": 1, "cites": ["s0", "s1"],
             "blocks": [{"type": "para", "text": "문단입니다"}]}]}
        res = _wr.check(got, plan, {"s0", "s1"})
        assert res["sections"][0]["cites"] == ["s0"], res["sections"][0]
        # 배치가 없는 섹션(직접 쓴 구조)은 막지 않는다. 막으면 인용이 사라진다.
        plan2 = [{"order": 1, "heading": "h", "figure": None, "claim_refs": []}]
        assert _wr.check(got, plan2, {"s0", "s1"})["sections"][0]["cites"] == ["s0", "s1"]
    finally:
        _wr._CID.clear(); _wr._CID.update(old)
check("배치를 벗어난 인용은 걸러진다", _refs_are_contract)

def _media_is_naver_only():
    """사진·자료 화면은 네이버만. 코드가 비운다.

    프롬프트에 "쓰지 마라" 를 적어 두어도 안 지키는 날이 있다. 모양은
    채널과 상관없이 같게 두고(제목의 meta·tags 와 같은 원칙) 채널에 안
    맞는 것만 코드가 비운다.
    """
    from backend.steps.outline.payload import payload as _op
    secs = [{"title": "가", "media": {"type": "photo", "purpose": "회의 사진"}},
            {"title": "나", "media": {"type": "장식", "purpose": "예쁜 그림"}}]
    nav = _op(secs, media=True)["sections"]
    site = _op(secs, media=False)["sections"]
    assert nav[0]["media"]["type"] == "photo", nav[0]
    assert nav[1]["media"] is None, "목록 밖 type 이 통과했다"
    assert all(x["media"] is None for x in site), site
    # 필드는 늘 있다. 읽는 쪽이 채널을 알 필요가 없게.
    assert "media" in site[0] and "media" in nav[0]
check("사진·자료는 네이버만 채운다", _media_is_naver_only)

def _media_counted_apart():
    """도식·대표 이미지·준비할 자료를 따로 센다.

    만드는 주체가 다르다 — 도식은 코드, 대표 이미지는 생성 모델, 사진은
    사람이다. 합쳐 세면 파일 몇 장을 약속하는 것처럼 보인다.
    """
    from backend.steps.outline.payload import label as _ol
    assert _ol(3, 1, 1, 2) == "3개 부분 · 도식 1개 · 대표 이미지 1장 · 준비할 자료 2건"
    assert _ol(3, 0, 0, 0) == "3개 부분"
check("준비할 자료를 따로 센다", _media_counted_apart)

def _media_reaches_output():
    """네이버 결과물에 자리표시가 뜨고 확인 목록이 알린다.

    안 알리면 자리표시만 남은 채 발행된다.
    """
    from backend.output import common as _cm, checklist as _ck
    d = {"outline": {"payload": {"sections": [
            {"title": "가", "media": {"type": "capture", "purpose": "공식 안내 화면"}},
            {"title": "나", "media": None}]}}}
    assert _cm.media_of(d) == {1: {"type": "capture", "purpose": "공식 안내 화면"}}
    out = []
    _ck._media(out, d, "naver")
    assert out and "1건" in out[0]["text"] and "자료 화면" in out[0]["note"], out
check("준비할 자료를 결과물과 확인 목록이 안다", _media_reaches_output)

def _media_written():
    """직접 쓸 때도 자리를 적을 수 있다."""
    _, _, pay = _out.parse.read("가\n캡처: 공식 안내 화면\n나\n사진: 검토 업무")
    assert pay["sections"][0]["media"]["type"] == "capture", pay["sections"][0]
    assert pay["sections"][1]["media"]["type"] == "photo", pay["sections"][1]
check("직접 쓴 구조에도 자료 자리를 적을 수 있다", _media_written)

def _topic_summary_flows():
    """소재 요약이 다섯 단계에 다 흐른다.

    소재 payload 는 topic_title · topic_summary 로 오는데 단계들이
    headline · summary 를 읽고 있었다. **다섯 단계 전부에서 요약이 빈
    문자열**이었고 아무 오류도 안 났다 — 소재를 넓힌 작업이 통째로 무효였다.
    """
    from backend.data import fake as _fk
    d = {"topic": {"label": "x", "payload": _fk.load_topics("normal")[0]},
         "reader": {"payload": {}}, "intent": {"payload": {}},
         "angle": {"payload": {}}, "type": {"payload": {}},
         "outline": {"payload": {"sections": []}}, "evidence": {"payload": {}},
         "channel": {"payload": {"channel": "naver"}}}
    for name, mod in (("intent", _in), ("angle", _ag), ("type", _ty),
                      ("outline", _out), ("title", _tt)):
        t = mod.build_input(d)["topic"]
        assert t["summary"], f"{name} 에 소재 요약이 안 간다"
        assert t["headline"], f"{name} 에 소재 제목이 안 간다"
check("소재 요약이 모든 단계에 흐른다", _topic_summary_flows)

def _summary_reaches_evidence():
    """근거 단계도 소재 요약을 본다.

    명제를 뽑는 자리라 소재가 실제로 무엇을 다루는지 제일 필요하다.
    제목 한 줄만 보면 "이 글이 성립하려면 참이어야 하는 것" 을 소재 범위
    밖에서 찾게 된다.
    """
    from backend.data import fake as _fk
    from backend.steps.evidence import claims as _cl2, plan as _pl2
    d = {"topic": {"label": "x", "payload": _fk.load_topics("normal")[0]},
         "intent": {"payload": {"question": "q", "sub_questions": []}},
         "angle": {"payload": {}}, "type": {"payload": {}},
         "reader": {"payload": {}}}
    assert _cl2.build_input(d)["topic"]["summary"], "claims 에 요약이 안 간다"
    assert _pl2.build_input(d, [])["topic"]["summary"], "plan 에 요약이 안 간다"
check("근거 단계도 소재 요약을 본다", _summary_reaches_evidence)

def _flat_structure_flagged():
    """평면적인 구조를 발행 전에 알린다.

    구조 카드에도 표시되지만 사람이 안 보고 넘어갔을 수 있다. 막지는
    않는다 — 이미 고른 뒤라 되돌릴 수 없고, 어디를 볼지 알려 주는 것까지다.
    """
    from backend.output import checklist as _ck3
    bad = {"outline": {"payload": {"sections": [
        {"title": "가", "claim_refs": ["c01", "c02"]},
        {"title": "나", "claim_refs": ["c01", "c02", "c03"]},
        {"title": "그래서", "claim_refs": ["c01", "c02", "c03", "c04"]}]}}}
    out = []
    _ck3._structure(out, bad)
    kinds = [x["kind"] for x in out]
    assert "근거 배치" in kinds and "마지막 섹션" in kinds, out

    ok = {"outline": {"payload": {"sections": [
        {"title": "가", "claim_refs": ["c01"]},
        {"title": "나", "claim_refs": ["c02"]},
        {"title": "결론", "claim_refs": []}]}}}
    out2 = []
    _ck3._structure(out2, ok)
    assert out2 == [], out2
check("평면적인 구조를 발행 전에 알린다", _flat_structure_flagged)

def _media_purpose_is_content():
    """media.purpose 가 그림의 존재 이유로 끝나지 않는다.

    "~를 구체화한다" 로 적으면 준비하는 사람이 **무슨 파일을 찾아야 할지
    모른다.** 실제로 그렇게 나왔다.
    """
    from backend.steps.outline.payload import payload as _op
    for bad in ("공시 데이터 연결 방식을 구체화한다",
                "이 섹션의 내용을 시각적으로 보조한다."):
        got = _op([{"title": "가", "media": {"type": "capture", "purpose": bad}}])
        assert got["sections"][0]["media"] is None, bad
    ok = "같은 지표가 어느 시스템에서 왔는지 한 화면에서 확인되는 모습"
    assert _op([{"title": "가", "media": {"type": "capture", "purpose": ok}}]
               )["sections"][0]["media"], ok
    assert "구체화한다" in _md("naver_outline"), "왜 안 되는지 프롬프트에 없다"
check("자료 목적이 전달 내용으로 적힌다", _media_purpose_is_content)

def _tree_stays_side_by_side():
    """캡처할 때 구조도를 세로로 쌓지 않는다.

    항목카드는 한 줄로 세우는 것이 맞지만, 구조도를 그러면 **가지를 잇는
    가로선이 붕 뜨고** 상하위 관계가 목록처럼 보인다. 그 규칙은 캡처 폭이
    680 이던 때 만든 것이고, 지금 구조도는 900 으로 찍는다.
    """
    from backend.data import brand as _br6
    css = _br6.NAVER_FIGURE_CSS
    assert ".fig-cards{grid-template-columns:1fr" in css, "카드는 세워야 한다"
    assert "fig-branch{grid-template-columns:1fr" not in css, "구조도가 세로로 쌓인다"
check("캡처에서 구조도가 나란히 남는다", _tree_stays_side_by_side)

def _one_visual_per_section():
    """같은 것을 두 번 보여주지 않는다.

    실제로 media 와 illustration 이 "요청 문서에서 범위를 확인한다" 를
    나눠 가졌다. 표현만 다르고 독자는 같은 말을 두 번 본다.
    """
    from backend.steps.outline.payload import payload as _op
    rows = _op([
        {"title": "가", "media": {"type": "capture", "purpose": "요청 양식 화면"},
         "illustration": {"purpose": "요청 문서를 검토하는 상황"}},
        {"title": "나", "illustration": {"purpose": "여러 부서 자료가 모이는 상황"}}],
        media=True)["sections"]
    assert rows[0]["media"] and not rows[0]["illustration"], "둘 다 남았다"
    assert rows[1]["illustration"], rows[1]
    assert "`media` 와 같은 것을 보여주지 않습니다" in _md("naver_outline")
check("한 섹션에 같은 것을 두 번 안 보인다", _one_visual_per_section)

def _illust_generation():
    """본문 그림을 실제로 만든다.

    대표 이미지와 달리 **여러 장이고 없어도 글이 나간다.** 그래서 하나가
    실패해도 나머지는 쓰고, 이미 만든 것은 다시 안 만든다 — 나눠 부를
    때마다 새로 그리면 사람이 저장해 둔 것과 화면의 것이 달라진다.
    """
    from backend.output import illust as _il
    from backend.external import gemini as _gm
    old_gen, old_draw, old_en = llm.generate, _gm.draw, _gm.ENABLED
    calls = []
    _gm.ENABLED = True
    _gm.draw = lambda p: (calls.append(p), b"\x89PNG" + b"\0" * 900)[1]
    llm.generate = lambda n, p, strong=False: {
        "prompt": "wide illustration, no text", "alt": "설명"}
    try:
        d = {"_sid": "iltest", "channel": {"payload": {"channel": "naver"}},
             "title": {"payload": {"title": "t"}},
             "topic": {"label": "소재", "payload": {}},
             "outline": {"payload": {"sections": [
                {"title": "가", "role": "context", "objective": "o",
                 "illustration": {"purpose": "여러 부서 자료가 모이는 상황"}},
                {"title": "나", "role": "criteria", "objective": "o",
                 "illustration": {"purpose": "요청 범위를 좁히는 상황"}}]}}}
        got = _il.make(d, "iltest")
        assert sorted(got["made"]) == ["1", "2"] and not got["failed"], got
        # 섹션 번호로 잇는다. 본문 자리표시와 같은 번호여야 한다.
        assert got["made"]["1"]["file"].endswith("-s1.png"), got["made"]["1"]
        assert "no text" in calls[0], calls[0]

        n = len(calls)
        _il.make(d, "iltest")
        assert len(calls) == n, "이미 만든 것을 다시 그린다"

        # 하나가 실패해도 나머지는 산다
        once = iter([{"prompt": "ok", "alt": "a"}])
        def flaky(name, p, strong=False):
            try:
                return next(once)
            except StopIteration:
                raise llm.LLMError("모델 실패")
        llm.generate = flaky
        d2 = {**d, "illust": {}, "_sid": "iltest2"}
        r = _il.make(d2, "iltest2")
        assert sorted(r["made"]) == ["1"] and sorted(r["failed"]) == ["2"], r
    finally:
        llm.generate, _gm.draw, _gm.ENABLED = old_gen, old_draw, old_en
check("본문 그림을 만들고 일부 실패를 견딘다", _illust_generation)

def _illust_prompt_bans_text():
    """그림에 글자를 넣지 않는다. 도식을 마크업으로 그리는 것과 같은 이유다."""
    # 밑바탕까지 합친 것을 본다. 규칙이 _illust.md 에 있다.
    from backend import prompt as _pr7
    md = _pr7.build("naver_illust")
    assert "no text" in md and "한글을 제대로 못" in md, md[:0]
    assert "도표·차트·표를 그리지 않습니다" in md, "생성 모델에 표를 시킨다"
    assert "16:9" in md, "본문 그림은 가로다"
check("본문 그림 프롬프트가 글자를 막는다", _illust_prompt_bans_text)

def _illust_reaches_screen():
    """만든 그림을 화면에서 받을 수 있다."""
    assert "illustShop(out.illust)" in _js("pages/result.js")
    assert "API.illust()" in _js("pages/result.js")
    assert "illust:" in _js("api.js")
    # 계획이 없으면 빈 dict — 화면이 패널을 안 그린다
    assert _render(ALL, "naver") is not None
    from backend.output import illust as _il2
    assert _il2.plans({"outline": {"payload": {"sections": []}}}) == {}
check("만든 본문 그림을 화면에서 받는다", _illust_reaches_screen)

def _result_can_reload():
    """결과물 화면을 다시 받을 수 있다.

    본문 그림을 만들고 나면 화면이 그걸 받아야 하는데, **처음 한 번만
    받으면 만든 그림이 계속 "아직 없음" 으로 남는다.** 실제로 파일은
    만들어졌는데 화면에 안 떴다.
    """
    js = _js("pages/result.js")
    assert "function load()" in js, "다시 받을 수 없다"
    assert "return load();" in js, "만든 뒤 다시 안 받는다"
    # 버튼은 render 안에서 묶는다 — 다시 그리면 새로 묶여야 한다
    assert js.index("illustWire()") < js.index("function illustWire")
check("결과물 화면을 다시 받는다", _result_can_reload)

def _no_text_forced():
    """그림에 글자가 들어가지 않게 코드가 막는다.

    프롬프트에 규칙을 적어 뒀지만 **모델이 지시문에 안 넣으면 그만이다** —
    실제로 "Existing reporting work" 가 철자까지 깨진 채 박혀 나왔다.
    한글이든 영문이든 그림 안 글자는 고칠 방법이 없다.
    """
    from backend.external.gemini import with_no_text as _nt
    got = _nt("a person at a desk reviewing documents")
    assert "no text" in got and "no letters" in got, got
    assert "blank with no writing" in got, got
    # 이미 있으면 두 번 안 붙인다
    once = _nt("isometric scene, no text, wide")
    assert once.count("no text") == 1, once
    src = (paths.BACKEND / "external" / "gemini.py").read_text(encoding="utf-8")
    assert "with_no_text(prompt)" in src, "draw 가 안 쓴다"
check("그림에 글자가 못 들어간다", _no_text_forced)

def _illustration_is_narrow():
    """본문 그림은 조건을 좁혀 둔다.

    아무 데나 열면 장식 이미지가 남발된다. 도식과 겹치면 그 섹션만
    무거워지고, 그림이 도식을 설명하는 꼴이 된다.
    """
    from backend.steps.outline.payload import payload as _op
    p3 = _op([{"title": "가", "image": {"purpose": "p", "form": "대조표"},
               "illustration": {"purpose": "겹치면 버려진다"}},
              {"title": "나", "illustration": {"purpose": "여러 부서 자료가 모이는 상황"}},
              {"title": "다", "illustration": {"purpose": "상황을 시각화한다"}}],
             media=True)
    secs = p3["sections"]
    assert secs[0]["illustration"] is None, "도식과 겹쳤는데 남았다"
    assert secs[1]["illustration"]["purpose"], secs[1]
    assert secs[2]["illustration"] is None, "메타 문장이 통과했다"
    # 홈페이지는 안 쓴다. media 와 같은 원칙이다.
    assert _op([{"title": "가", "illustration": {"purpose": "상황"}}],
               media=False)["sections"][0]["illustration"] is None
    md = _md("naver_outline")
    assert "도식이 있는 섹션에는 넣지 않습니다" in md and "한두 곳" in md
check("본문 그림은 도식과 겹치지 않는다", _illustration_is_narrow)

def _illust_role_apart():
    """도식이 하는 일을 그림이 또 하지 않는다.

    실제로 그림과 도식이 둘 다 "무엇이 달라졌나" 를 설명했다. 같은 섹션이
    아니어도 **역할이 겹치면 정보 밀도가 떨어진다.**

        도식        제도가 어떻게 갈리는가
        본문 그림    사람이 처한 상황
        자료 화면    실제 자료가 그렇게 생겼다는 것
    """
    md = _md("naver_outline")
    assert "도식이 하는 일을 그림이 또 하지 않습니다" in md
    assert "그림이 제도 비교를 하려 들면 그건 도식이 할 일입니다" in md
check("본문 그림과 도식의 역할이 갈린다", _illust_role_apart)

def _illustration_counted_apart():
    """도식·대표 이미지·본문 그림·준비할 자료를 따로 센다."""
    from backend.steps.outline.payload import label as _ol
    got = _ol(3, 1, 1, 2, 1)
    assert "도식 1개" in got and "본문 그림 1장" in got and "준비할 자료 2건" in got, got
    from backend.output import checklist as _ck8
    out = []
    _ck8._media(out, {"outline": {"payload": {"sections": [
        {"title": "가", "illustration": {"purpose": "상황"}}]}}}, "naver")
    assert out and out[0]["kind"] == "본문 그림", out
check("본문 그림을 따로 센다", _illustration_counted_apart)

def _media_not_invented():
    """media 를 적극 검토로 바꾼 만큼 지어내는 것도 막아야 한다.

    "하나 이상 검토" 만 적어 두면 없는 행사·회의를 있었던 것처럼 적는다.
    """
    md = _md("naver_outline")
    assert "있었던 것처럼 적지 않습니다" in md, md[:0]
    assert "장면의 종류" in md and "확인할 자료의 종류" in md
check("없는 자료를 있었던 것처럼 적지 않는다", _media_not_invented)

def _skeleton_has_no_sections():
    """유형 골격이 소제목 목록을 안 준다.

    섹션 다섯 개가 제목과 covers 까지 적힌 채로 실리면 그건 참고자료가
    아니라 채우기 틀이다. 실제로 후보들이 전부 그 흐름으로 수렴했고,
    허용된 변화가 "어디를 합치고 나눌까" 뿐이었다.
    """
    g = _sk.for_outline("비교형")
    assert set(g) == {"purpose", "must_have", "moves", "avoid", "image",
                      "blocks", "need"}, sorted(g)
    # need 는 **이 유형·채널이 담아야 할 최소치**다. 채우기 틀이 아니라
    # "몇 가지를 담을 것인가" 다 — 근거가 있는데 일찍 끝나는 것을 막는다.
    assert set(g["need"]) == {"sections", "covers", "claims", "chars"}, g["need"]
    assert "sections" not in g and "flow" not in g and "common" not in g
    # moves 는 화살표 한 줄이 아니라 조각이다
    assert isinstance(g["moves"], list) and len(g["moves"]) > 1, g["moves"]
    md = _md("_prompt", "outline")
    assert "순서가 아니라 후보다" in md and "common.rules" not in md
check("유형 골격이 채우기 틀이 아니다", _skeleton_has_no_sections)

check("후보는 전략이 달라야 한다", lambda: (
    "두 가지 이상이 실제로 달라야" in _md("_prompt", "outline")
    and "다른 후보가 아닙니다" in _md("_prompt", "outline")) or 1/0)

def _claim_overlap_marked():
    """같은 명제를 여러 섹션이 맡으면 표시한다.

    소제목만 다르고 같은 설명이 반복되는 자리다. 지우지는 않는다 — 앞이
    사실을, 뒤가 그 적용을 다루는 것은 정당하다.
    """
    from backend.steps.outline.payload import overlap as _ov, payload as _op
    p = _op([{"title": "가", "claim_refs": ["c01", "c02"]},
             {"title": "나", "claim_refs": ["c01", "c02", "c03"]},
             {"title": "결론", "claim_refs": []}])
    assert _ov(p) == ["c01", "c02"], _ov(p)
    assert _ov(_op([{"title": "가", "claim_refs": ["c01"]}])) == []
    assert "결론 섹션은 `claim_refs` 를 비웁니다" in _md("_prompt", "outline")
check("겹친 근거 배치를 표시한다", _claim_overlap_marked)

check("네이버는 media 를 기본으로 검토한다", lambda: (
    "하나 이상 검토합니다" in _md("naver_outline")
    and "안 쓰는 쪽이 언제나 안전해서" in _md("naver_outline")) or 1/0)

def _card_classes_dont_collide():
    """구조 카드 클래스가 레이아웃과 안 부딪힌다.

    .sec-h 는 레이아웃의 섹션 헤더다. 카드가 그 이름을 쓰면 대표 이미지
    줄이 헤더 스타일을 뒤집어쓴다 — 한 번 데인 자리인데 되살아나 있었다.
    """
    js = _js("shape.js")
    for bad in ("'sec-i'", "'sec-h'", '"sec-m"'):
        assert bad not in js, f"레이아웃 클래스와 부딪힌다: {bad}"
    css = (paths.ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    for want in (".osec-i", ".osec-h", ".osec-m"):
        assert want in css, f"CSS 에 {want} 가 없다"
check("구조 카드 클래스가 레이아웃과 안 부딪힌다", _card_classes_dont_collide)

def _role_breaks_monotony():
    """섹션마다 역할이 있고, 같은 역할이 연달아 셋이면 표시한다.

    논리가 이어지는 것과 읽는 리듬이 살아 있는 것은 다르다. 실제로 섹션
    셋이 전부 "설명 → 목록 → 정리" 로 나온 글이 있었다.
    """
    from backend.steps.outline.payload import (payload as _op, role_repeat as _rr,
                                               ROLES as _ROLES)
    p3 = _op([{"title": "가", "role": "structure"}, {"title": "나", "role": "structure"},
              {"title": "다", "role": "structure"}])
    assert _rr(p3) == ["structure"], _rr(p3)
    # 떨어져 있는 반복은 막지 않는다 — 상황·비교·상황 은 정당하다
    p2 = _op([{"title": "가", "role": "context"}, {"title": "나", "role": "comparison"},
              {"title": "다", "role": "context"}])
    assert _rr(p2) == [], _rr(p2)
    # 목록 밖 값은 버린다
    assert _op([{"title": "가", "role": "없는것"}])["sections"][0]["role"] == ""
    assert "role" in _md("_prompt", "outline") and len(_ROLES) == 7
check("섹션 역할이 같은 리듬을 막는다", _role_breaks_monotony)

def _flat_run_counted():
    """섹션이 끝나는 모양을 코드가 센다.

    프롬프트에 "list 다음에 바로 list 를 놓지 않습니다" 가 있었지만 그건
    **한 섹션 안의 규칙**이라 섹션을 건너뛴 반복은 아무도 안 봤다.
    """
    same = [{"blocks": [{"type": "para"}, {"type": "list"}]}] * 3
    assert _wr.flat_run(same) == ["list"], _wr.flat_run(same)
    mixed = [{"blocks": [{"type": "figure"}]}, {"blocks": [{"type": "list"}]},
             {"blocks": [{"type": "figure"}]}]
    assert _wr.flat_run(mixed) == [], _wr.flat_run(mixed)
    # 마지막 블록을 본다 — 섹션을 다 읽고 넘어갈 때 남는 인상이 그것이다
    assert _wr.shape_of({"blocks": [{"type": "list"}, {"type": "para"}]}) == "list"
check("섹션 맺음 반복을 코드가 센다", _flat_run_counted)

def _rhythm_told():
    """평평한 리듬과 도식 부족을 발행 전에 알린다. 막지는 않는다."""
    from backend.output import checklist as _ck7
    out = []
    _ck7._rhythm(out, {"write": {"sections":
        [{"blocks": [{"type": "para"}, {"type": "list"}]}] * 3}})
    kinds = [x["kind"] for x in out]
    assert "읽는 리듬" in kinds and "도식이 적다" in kinds, out
    out2 = []
    _ck7._rhythm(out2, {"write": {"sections": [
        {"blocks": [{"type": "figure"}]}, {"blocks": [{"type": "list"}]},
        {"blocks": [{"type": "figure"}]}]}})
    assert out2 == [], out2
check("평평한 리듬을 발행 전에 알린다", _rhythm_told)

def _vague_action_caught():
    """무엇을 하라고만 하고 무엇을 보라고는 안 한 문장을 잡는다.

    **"확인합니다" 로 끝나는 문장은 아무것도 안 알려 준다.** 독자는 이미
    확인해야 한다는 걸 알고 있고, 무엇을 어떤 기준으로 보는지를 모른다.
    실제 네이버 글이 그런 문장으로 채워져 나왔다 — 정보 구체성 4/10.
    """
    bad = ["원천 데이터를 확인합니다.",
           "담당 부서를 정해 관리해야 합니다.",
           "채널과 지표를 구분합니다."]
    ok = ["그 수치가 어느 시스템에서 추출됐고, 보고기간과 조직경계가 무엇인지 확인합니다.",
          "산정 담당과 승인 담당을 나누고, 어느 자료까지 누가 책임지는지 정합니다.",
          "표시 단위와 대상 기간을 먼저 봅니다."]
    for t in bad:
        assert _wr.vague(t), t
    for t in ok:
        assert not _wr.vague(t), t

    # **사실을 설명하는 문장은 안 본다.** 무엇을 하라는 말이 아니므로
    # 짧아도 된다. 행동을 권하는 문장에만 붙는 규칙이다.
    assert not _wr.vague("전환기간에는 분기별 보고가 적용되고 본격 시행부터는 연간 신고로 바뀝니다.")
    # 이음말은 안 잡는다 — 잡으면 잡음이 는다
    assert not _wr.vague("다시 확인합니다.")

    # 문단·목록·체크·강조·도식 해석을 다 본다
    rows = _wr.vague_rows([{"heading": "h", "blocks": [
        {"type": "para", "text": "원천 데이터를 확인합니다."},
        {"type": "list", "items": [{"title": "채널과 지표", "body": "구분합니다."}]},
        {"type": "callout", "text": "담당 부서를 정해 관리해야 합니다."}]}])
    assert len(rows) == 3, rows
    assert _md("_write").count("원천 데이터를 확인합니다") == 1, "프롬프트에 예시가 없다"
check("무엇을 볼지 안 적은 문장을 잡는다", _vague_action_caught)

def _specificity_told():
    """구체 기준이 모자란 문장을 발행 전에 알린다. 막지는 않는다."""
    from backend.output import checklist as _ck10
    out = []
    _ck10._specificity(out, {"write": {"sections": [
        {"heading": "무엇부터 볼까", "blocks": [
            {"type": "para", "text": "원천 데이터를 확인합니다."}]}]}})
    assert out and out[0]["kind"] == "구체 기준 부족", out
    out2 = []
    _ck10._specificity(out2, {"write": {"sections": [
        {"heading": "h", "blocks": [
            {"type": "para",
             "text": "그 수치가 어느 시스템에서 왔고 보고기간이 무엇인지 확인합니다."}]}]}})
    assert out2 == [], out2
check("구체 기준 부족을 발행 전에 알린다", _specificity_told)

def _loose_nouns_caught():
    """무엇인지 안 풀고 넘어간 말을 잡는다.

    **"요청 형식과 맞는지 확인합니다" 는 형식이 뭔지 안 알려 준다.**
    `vague()` 는 이걸 통과시킨다 — `자료`·`형식` 이 표시로 잡히기 때문이다.
    표시는 있는데 **그 표시가 가리키는 것이 안 풀린** 경우다.
    """
    assert _wr.loose("거래처가 어느 의무 구간에 있는지, 우리 자료가 요청 형식과 맞는지 두 가지입니다.")
    assert _wr.loose("현재 상태를 점검해야 합니다.")
    # 나열이 있으면 푼 것이다 — 항목을 늘어놓는 것이 곧 무엇인지 적는 것
    assert not _wr.loose("요청 양식에 CN 코드, 설비 정보, 보고기간이 포함되는지 확인합니다.")
    assert not _wr.loose("제출 형식은 CN 코드, 설비명, 보고기간을 포함합니다.")
    assert not _wr.loose("자료 상태를 다음 셋으로 나눕니다: 확보 · 부족 · 없음")
    # 구체 문장은 안 걸린다
    assert not _wr.loose("어느 설비에서 어느 보고기간에 얼마를 생산했는지 확인합니다.")

    # 두 검사가 겹치면 vague 가 먼저다 — 표시조차 없는 쪽이 더 나쁘다
    rows = _wr.vague_rows([{"heading": "h", "blocks": [
        {"type": "para",
         "text": "거래처가 어느 의무 구간에 있는지, 우리 자료가 요청 형식과 맞는지 두 가지입니다."}]}])
    assert rows and rows[0]["why"] == "무엇인지 안 풀었음", rows
    assert "추상 명사를 쓰면" in _md("_write")
    assert "목록은 완료 조건까지 씁니다" in _md("_write")
check("무엇인지 안 푼 말을 잡는다", _loose_nouns_caught)

def _references_show_pages():
    """참고자료에 어느 쪽을 봤는지 적는다.

    문서명만 있으면 읽는 사람이 그 문서 어디를 보라는 것인지 알 수 없다.
    대조가 인용마다 남긴 `location` 에서 쪽을 뽑는다.
    """
    from backend.output import common as _cm3
    w = {"sections": [{"cites": ["s0", "s1"]}], "sources": [
        {"id": "s0", "ref_title": "EU CBAM 대응 가이드", "file": "abc", "url": "",
         "evidence_spans": [{"quote": "q", "location": "[4쪽]"},
                            {"quote": "q2", "location": "[2쪽]"}]},
        {"id": "s1", "ref_title": "웹 문서", "url": "https://x/a",
         "evidence_spans": [{"quote": "q", "location": "CBAM 개요"}]}]}
    got = _cm3.references(w)
    assert got[0]["pages"] == ["2", "4"], got[0]
    # 웹 원문은 절 제목이라 쪽이 아니다
    assert "pages" not in got[1], got[1]
    # 두 렌더러가 다 보인다
    for f in ("naver", "site"):
        src = (paths.BACKEND / "output" / f / "render.py").read_text(encoding="utf-8")
        assert 's.get("pages")' in src, f
check("참고자료에 본 쪽이 적힌다", _references_show_pages)

def _reference_titles_tidy():
    """참고자료 제목을 다듬는다.

    검색 결과 제목을 그대로 쓰면 **잘린 티가 난다.** 실제로 말줄임표가
    붙고 공백이 겹친 채 나갔다 — 자동 생성 결과라는 인상을 준다.
    """
    from backend.output import common as _cm4
    assert _cm4._tidy("European Commission sets conditions for authorized ...") \
        == "European Commission sets conditions for authorized"
    assert _cm4._tidy("DEHSt  -  CBAM Certificates") == "DEHSt - CBAM Certificates"
    assert _cm4._tidy("CBAM 대응 가이드…") == "CBAM 대응 가이드"
    # 멀쩡한 제목은 안 건드린다
    assert _cm4._tidy("정상 제목") == "정상 제목"
    # **잘린 뒤를 만들어 내지 않는다** — 없는 제목을 지어내는 것이 더 나쁘다
    got = _cm4._tidy("Regulation on carbon border ...")
    assert "..." not in got and len(got) < len("Regulation on carbon border ...")
check("참고자료 제목이 깔끔하다", _reference_titles_tidy)

def _reference_shows_org():
    """참고자료에 기관명이 앞에 온다.

    문서 제목만 있으면 **그것이 공식 자료인지 민간 해설인지 구분되지
    않는다.** `official_primary` 같은 내부 이름을 그대로 내보내면 사람에게
    아무 뜻이 없다.
    """
    from backend.output import common as _cm5
    w = {"sections": [{"cites": ["s0", "s1", "s2"]}], "sources": [
        {"id": "s0", "ref_title": "CBAM Certificates",
         "url": "https://www.dehst.de/EN/cbam", "source": "official_primary"},
        {"id": "s1", "ref_title": "Carbon Border Adjustment Mechanism",
         "url": "https://taxation-customs.ec.europa.eu/cbam"},
        {"id": "s2", "ref_title": "EY note", "url": "https://taxnews.ey.com/x"}]}
    got = _cm5.references(w)
    assert got[0]["source"] == "DEHSt", got[0]
    assert got[1]["source"] == "European Commission", got[1]
    # 모르는 곳은 도메인 — 어디서 왔는지는 알 수 있다
    assert got[2]["source"] == "taxnews.ey.com", got[2]
    # 내부 이름이 안 나간다
    assert not any("official_primary" in str(r) for r in got), got
check("참고자료에 기관명이 나온다", _reference_shows_org)

def _compare_axis_checked():
    """대조표 한 행의 칸이 같은 축인가.

    왼쪽이 주체 이름인데 오른쪽이 해야 할 행동이면 **나란히 놓아도 견준
    것이 아니다.** 실제로 이렇게 났다.

        자격 범위   보고 신고자 기준   거래 조건별 적용 확인

    행끼리 같은 말을 하는지는 코드가 못 가른다 — 낱말 겹침으로는 정상인
    표가 더 높게 나온다. 그건 프롬프트가 막는다.
    """
    bad = _fg.flaws("대조표", {"columns": ["전환기간", "본격 시행"], "rows": [
        {"criterion": "신고 주기", "cells": ["분기별 보고", "연간 신고"]},
        {"criterion": "자격 범위", "cells": ["보고 신고자 기준", "거래 조건별 적용 확인"]}]})
    assert bad and "같은 축이 아닙니다" in bad[0], bad

    ok = _fg.flaws("대조표", {"columns": ["전환기간", "본격 시행"], "rows": [
        {"criterion": "신고 주기", "cells": ["분기별 CBAM 보고", "연간 CBAM 신고"]},
        {"criterion": "업무 주체", "cells": ["보고 신고자", "승인된 CBAM 신고인"]},
        {"criterion": "금전 의무", "cells": ["인증서 없음", "내재배출량만큼 인증서 구매"]}]})
    assert ok == [], ok
    md = _md("_write")
    assert "행마다 다른 것을 재야 합니다" in md
    assert "한 행의 칸은 같은 축이어야 합니다" in md
check("대조표 행의 축이 맞는다", _compare_axis_checked)

def _figure_not_ahead():
    """도식이 본문에 없는 기준을 들지 않는다.

    본문이 셋을 짚는데 도식에 다섯이 들어가면 **읽는 사람은 나머지 둘을
    어디서 확인해야 할지 모른다.** 도식과 본문이 따로 움직인다.
    """
    sec = {"heading": "가", "blocks": [
        {"type": "para", "text": "신고 주기와 업무 주체가 달라집니다."},
        {"type": "figure", "component": "대조표", "caption": "c", "takeaway": "t",
         "data": {"columns": ["전환기간", "본격 시행"], "rows": [
             {"criterion": "신고 주기", "cells": ["분기", "연간"]},
             {"criterion": "업무 주체", "cells": ["보고", "승인"]},
             {"criterion": "일정 관리", "cells": ["-", "-"]},
             {"criterion": "자격 범위", "cells": ["-", "-"]}]}}]}
    assert _wr.figure_ahead(sec) == ["일정 관리", "자격 범위"], _wr.figure_ahead(sec)

    ok = {"heading": "나", "blocks": [
        {"type": "para", "text": "상류 활동과 하류 활동으로 나눠 봅니다."},
        {"type": "figure", "component": "구조도", "caption": "c", "takeaway": "t",
         "data": {"root": {"label": "보고기업", "children": [
             {"label": "상류 활동"}, {"label": "하류 활동"}]}}}]}
    assert _wr.figure_ahead(ok) == [], _wr.figure_ahead(ok)
    assert "도식은 본문이 다루는 것만 담습니다" in _md("_write")
check("도식이 본문보다 앞서지 않는다", _figure_not_ahead)

def _blurry_source_caught():
    """출처를 뭉뚱그린 문장을 잡는다.

    `관련 보도에서` 는 어디를 봐야 하는지 안 알려 준다. **출처를 흐리게
    적는 것은 없는 근거를 있는 것처럼 보이게 한다.**
    """
    assert _wr.blurry("관련 보도에서 설명한 승인 자격의 범위는 물량에 따라 달라집니다.")
    assert _wr.blurry("업계에서는 준비가 미흡하다고 봅니다.")
    assert not _wr.blurry("공식 안내는 신고 주체를 승인된 신고인으로 설명합니다.")
    rows = _wr.vague_rows([{"heading": "h", "blocks": [
        {"type": "para", "text": "관련 보도에서 설명한 자격 범위는 물량에 따라 달라집니다."}]}])
    assert rows and rows[0]["why"] == "출처를 뭉뚱그림", rows
    assert "출처를 뭉뚱그리지 않습니다" in _md("_write")
check("출처를 뭉뚱그린 문장을 잡는다", _blurry_source_caught)

def _figure_question_reframed():
    """도식을 "굳이 필요한가" 로 묻지 않는다.

    판단 순서가 마지막이라 이미 만든 섹션에 나중에 붙이게 되고, 그러면
    안 넣는 쪽으로 기운다. media 가 전부 null 이던 것과 같은 편향이다.
    """
    md = _md("_prompt", "outline")
    assert "머릿속에 그림을 그려야 하는가" in md
    assert "수를 채우지는 않습니다" in md, "하한을 강제하면 없는 도식을 만든다"
check("도식을 묻는 방식을 바꿨다", _figure_question_reframed)

def _dupe_marked_not_dropped():
    """근거 배치가 같은 후보는 표시만 한다.

    지웠다가 후보가 하나만 남으면 화면이 막힌다. 제목 단계가 유형 어긋난
    후보를 지우지 않고 표시만 하는 것과 같다.
    """
    same = {"sections": [{"title": "가", "claim_refs": ["c01"]}]}
    old = llm.generate
    llm.generate = lambda n, p, strong=False: {"candidates": [
        same, {"sections": [{"title": "다르게 쓴 소제목", "claim_refs": ["c01"]}]}]}
    try:
        got = _out.make({}, {"article_type": "정보형", "channel": "site",
                             "claims": [{"claim_id": "c01"}]})
    finally:
        llm.generate = old
    assert len(got) == 2, got
    assert "근거 배치가 같음" in got[1]["title"], got[1]["title"]
    assert "근거 배치가 같음" not in got[0]["title"], got[0]["title"]
def _flow_comes_from_evidence():
    """설명 흐름은 근거가 정한다.

    **같은 소재라도 질문이 다르면 흐름이 달라야 한다.** 책임을 물으면 주체
    중심, 준비 자료를 물으면 데이터 흐름, 적용 대상을 물으면 기준·예외다.
    그런데 유형 골격이 앞에 있으면 무엇을 물어도 비슷하게 접힌다.
    """
    from backend.steps.outline import evidence_shape as _es
    actor = _es([{"claim": "법적 신고 주체는 승인된 신고인이다", "why": "역할 구분"},
                 {"claim": "제조기업은 자료를 제공하는 역할이다", "why": "책임 범위"}])
    assert actor[0] == "주체·책임", actor
    rule = _es([{"claim": "적용 대상은 코드로 판정한다", "why": "대상 기준"},
                {"claim": "50톤 미만은 면제된다", "why": "예외 조건"}])
    assert rule[0] == "기준·예외", rule
    change = _es([{"claim": "전환기간이 종료되고 본격 시행이 시작된다", "why": "시점 변경"}])
    assert change[0] == "변화·시점", change
    assert _es([]) == []

    md = _md("_prompt", "outline")
    assert "흐름은 근거가 정합니다" in md
    assert '"개념 설명 → 목록 → 먼저 확인할 것" 으로 만들지 않습니다' in md
check("설명 흐름을 근거가 정한다", _flow_comes_from_evidence)

def _same_flow_flagged():
    """후보끼리 설명 흐름이 같으면 표시한다.

    근거 배치가 달라도 `상황 → 기준 → 정리` 가 되풀이되면 독자가 이해하는
    경로는 같다. 지우지는 않는다 — 그 흐름이 맞는 소재도 있다.
    """
    from backend.steps.outline.payload import (payload as _op4, flow as _fl,
                                               signature as _sg)
    a = _op4([{"title": "가", "role": "context", "claim_refs": ["c01"]},
              {"title": "나", "role": "criteria", "claim_refs": ["c02"]}])
    b = _op4([{"title": "다", "role": "context", "claim_refs": ["c02"]},
              {"title": "라", "role": "criteria", "claim_refs": ["c01"]}])
    assert _sg(a) != _sg(b), "근거 배치는 다르다"
    assert _fl(a) == _fl(b), "설명 흐름은 같다"
    src = (paths.BACKEND / "steps" / "outline" / "__init__.py").read_text(encoding="utf-8")
    assert "설명 흐름이 같음" in src
check("설명 흐름이 같은 후보를 표시한다", _same_flow_flagged)

check("근거 배치가 같은 후보는 표시만 한다", _dupe_marked_not_dropped)

def junk():
    pay = _outline_pay([{"title":"가","covers":"문자열","exclude":[None,"",123," ㄱ "],
                       "objective":"  결론  "}])
    x = pay["sections"][0]
    assert x["covers"] == [] and x["exclude"] == ["ㄱ"] and x["objective"] == "결론", x
check("이상한 값은 걸러낸다", junk)

def in_card():
    from backend import llm
    from backend import steps as _op
    llm.ENABLED = True
    llm.generate = lambda n, p, strong=False: {"candidates":[{"sections":FULL,
        "hero_image":{"purpose":"대표"},"rationale":"권장"}]}
    d = {"topic":{"label":"x","payload":{}},
         "reader":{"payload":_rd.payload("r")},
         "angle":{"payload":_ag.payload("v","m",["a"])},
         "title":{"payload":_tt.payload("t","선언형")},
         "type":{"payload":_ty.payload("동향형")}}
    o = _op.options("outline", d, refresh=True)[0]
    assert o["payload"]["sections"][0]["objective"] == "결론 한 줄", o["payload"]
check("6단계 후보 payload 에 남는다", in_card)

print("\n── 구조 카드 라벨 ──")

check("도식과 대표 이미지를 따로 센다",
      lambda: _out.label(4, 2, 1) == "4개 부분 · 도식 2개 · 대표 이미지 1장"
              or (_ for _ in ()).throw(AssertionError(_out.label(4, 2, 1))))
check("없는 것은 적지 않는다",
      lambda: (_out.label(4, 0, 0) == "4개 부분"
               and _out.label(4, 2, 0) == "4개 부분 · 도식 2개"
               and _out.label(4, 0, 1) == "4개 부분 · 대표 이미지 1장") or 1/0)
check("도식과 이미지를 합쳐 세지 않는다",
      lambda: ("이미지 3장" not in _out.label(4, 2, 1)) or 1/0)

print("\n── 유형 골격과 도식이 어긋나지 않나 ──")

def forms_ok():
    bad = [(n, f) for n, t in _sk.TYPES.items()
           for f in t["image"]["forms"] if not _fg.component_of(f)]
    assert not bad, bad
check("골격의 form 이 전부 그려진다", forms_ok)

def outline_forms():
    md = _md("_prompt", "outline")
    seg = md[md.index("| 순서열"):md.index("### 도식이 아닌 것")]
    missing = [n for n in _fg.NAMES if n not in seg]
    assert not missing, missing
    for dead in ("핵심 변화 3가지", "체크 항목", "영역별 점검판"):
        assert dead not in seg, dead
check("outline.md 예시에 죽은 이름이 없다", outline_forms)

print("\n── 본문 블록 검증 ──")

PLAN = [{"order":1,"heading":"가","figure":None},
        {"order":2,"heading":"나","figure":{"purpose":"p","form":"대조표"}}]
CMP = {"columns":["가","나"],
       "rows":[{"criterion":"ㄱ","cells":["1","2"]},{"criterion":"ㄴ","cells":["3","4"]}]}

def _run(secs, plan=None):
    return _w.check({"lead":"도입.","sections":secs}, plan or PLAN, set())

def ok_blocks():
    r = _run([{"order":1,"blocks":[
                 {"type":"para","text":"문단."},
                 {"type":"list","items":[{"title":"ㄱ","body":"1"},{"title":"ㄴ","body":"2"}]}]},
              {"order":2,"blocks":[
                 {"type":"para","text":"문단."},
                 {"type":"figure","caption":"비교","takeaway":"해석.","data":CMP}]}])
    t = [b["type"] for b in r["sections"][1]["blocks"]]
    assert t == ["para","figure"], t
    assert r["sections"][1]["blocks"][1]["takeaway"] == "해석.", r
    assert r["dropped_figures"] == [], r
check("블록이 순서대로 통과한다", ok_blocks)

def no_para():
    try:
        _run([{"order":1,"blocks":[{"type":"check","items":["ㄱ","ㄴ","ㄷ"]}]},
              {"order":2,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"c","data":CMP}]}])
    except llm.LLMError:
        return
    raise AssertionError("문단 없는 섹션이 통과했다")
check("문단 없는 섹션은 실패로 올린다", no_para)

def plan_only():
    r = _run([{"order":1,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"c","data":CMP}]},
              {"order":2,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"c","data":CMP}]}])
    assert [b["type"] for b in r["sections"][0]["blocks"]] == ["para"], r["sections"][0]
check("계획 없는 자리의 도식은 버린다", plan_only)

def one_fig():
    r = _run([{"order":1,"blocks":[{"type":"para","text":"ㅁ"}]},
              {"order":2,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"첫째","data":CMP},
                                   {"type":"figure","caption":"둘째","data":CMP}]}])
    figs = [b for b in r["sections"][1]["blocks"] if b["type"]=="figure"]
    assert len(figs) == 1 and figs[0]["caption"] == "첫째", figs
check("한 섹션에 도식은 하나만", one_fig)

def fig_dropped():
    r = _run([{"order":1,"blocks":[{"type":"para","text":"ㅁ"}]},
              {"order":2,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"c","data":{"rows":[]}}]}])
    assert r["dropped_figures"] == [2], r["dropped_figures"]
check("못 쓸 도식은 버리고 점검표에 남긴다", fig_dropped)

def thin():
    r = _run([{"order":1,"blocks":[
                 {"type":"para","text":"ㅁ"},
                 {"type":"list","items":[{"title":"하나만","body":""}]},
                 {"type":"check","items":["둘","뿐"]},
                 {"type":"모르는것","text":"x"}]},
              {"order":2,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"c","data":CMP}]}])
    assert [b["type"] for b in r["sections"][0]["blocks"]] == ["para"], r["sections"][0]
check("항목이 모자란 목록·체크와 모르는 타입은 버린다", thin)

def label():
    r = _run([{"order":1,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"callout","label":"이상한라벨","text":"한 문장."}]},
              {"order":2,"blocks":[{"type":"para","text":"ㅁ"},
                                   {"type":"figure","caption":"c","data":CMP}]}])
    c = [b for b in r["sections"][0]["blocks"] if b["type"]=="callout"][0]
    assert c["label"] == "핵심", c
check("강조 박스 라벨이 목록 밖이면 핵심으로", label)

def legacy():
    r = _run([{"order":1,"paragraphs":["옛 문단."]},
              {"order":2,"paragraphs":["옛 문단."],
               "figure":{"caption":"c","data":CMP}}])
    assert r["sections"][0]["paragraphs"] == ["옛 문단."], r
    assert r["sections"][1]["figure"]["component"] == "대조표", r
check("옛 형식도 아직 통과한다", legacy)

print("\n── 오류 경로 ──")
check("없는 단계",     lambda: c.get("/api/draft/zzz").json()["reason"] == "unknown_step" or 1/0)
check("빈 입력",       lambda: c.post("/api/draft/title", json={"choice":[],"custom":""}).json()["reason"]=="empty" or 1/0)
check("4단계 직접쓰기 차단", lambda: c.post("/api/draft/type", json={"choice":[],"custom":"심층형"}).json()["reason"]=="empty" or 1/0)
check("세션 없이 결과물", lambda: TestClient(app).get("/api/draft/result").json()["reason"]=="no_topic" or 1/0)

print("\n── 진단 ──")
h = c.get("/api/health").json()
check("코드 지문 있다",    lambda: len(h["code"]) == 8 or 1/0)
check("프롬프트 지문 있다", lambda: len(h["content"]) == 8 or 1/0)
# 윈도우 경로는 C:\... 라 "/" 로 시작하지 않는다. OS 를 가정하지 않는다.
check("log_dirs 절대경로",
      lambda: all(pathlib.Path(v).is_absolute() for v in h["log_dirs"].values()) or 1/0)
check("hooks 다 걸림",     lambda: all(v > 0 for v in h["hooks"].values()) or 1/0)
check("log_rows 셈",       lambda: sum(h["log_rows"].values()) == len(history.read()) or 1/0)


def _raises_missing():
    from backend import prompt as _pr
    try:
        _pr.where("없는프롬프트")
        return False
    except _pr.MissingPrompt:
        return True


print("\n── 근거 PDF 올리기 ──")
# 앞 검사들이 드래프트를 어디까지 진행시켜 뒀는지에 기대지 않는다.
# 세션을 새로 열어 한 바퀴 돌려 두고 시작한다. 앞 검사들이 갈아끼운
# 가짜 응답이 남아 있으므로 되돌려 놓는다.
llm.generate = _fake_generate
cu = TestClient(app)
journey(cu)

from backend.steps.evidence import upload as _up, pick as _pk
from backend.steps.payload import is_confirmed as _confirmed


def _pdfp(pages):
    """글자 층이 있는 여러 쪽 PDF. 외부 라이브러리 없이 만든다."""
    n = len(pages)
    kids = " ".join(f"{3+i} 0 R" for i in range(n))
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{kids}] /Count {n} >>"]
    for i in range(n):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 {3+n+n} 0 R >> >> "
                    f"/Contents {3+n+i} 0 R >>")
    for lines in pages:
        objs.append((None, "".join(
            f"BT /F1 11 Tf 50 {760-j*16} Td ({l}) Tj ET\n"
            for j, l in enumerate(lines))))
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        if isinstance(o, tuple):
            b = o[1].encode("latin-1")
            out += (f"{i} 0 obj\n<< /Length {len(b)} >>\nstream\n".encode()
                    + b + b"\nendstream\nendobj\n")
        else:
            out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\n"
            f"startxref\n{x}\n%%EOF").encode()
    return bytes(out)


def _pdf(lines):
    return _pdfp([lines] if lines else [])


_PDFBYTES = _pdf(["CBAM Implementing Regulation",
                  "Importers must submit quarterly reports.",
                  "Suppliers shall provide emission data per product."])

# 긴 규정. 표지·목차·전문이 앞을 다 채우고 실제 조항은 뒤에 있다.
# 앞에서부터 자르면 인용할 조항이 하나도 안 들어가는 모양이다.
_LONG = _pdfp(
    [["COMMISSION IMPLEMENTING REGULATION (EU) 2025/xxxx"],
     ["TABLE OF CONTENTS"] + [f"Article {i} ... page {i+3}" for i in range(1, 20)]]
    + [[f"Whereas ({i}) recital text on background and context."] * 6
       for i in range(1, 23)]
    + [["Article 12", "Reporting obligations of declarants",
        "1. Quarterly report within one month of quarter end."],
       ["Article 13", "Information to be obtained from operators",
        "(a) installation id (b) production route"]]
    + [[f"Annex II Table {i}: default values by CN code"] * 6
       for i in range(1, 31)]
    + [["Article 40", "Verification requirements",
        "1. Reports verified by an accredited verifier."]])


def _post_doc(name, blob=None):
    # b"" 은 거짓이라 or 로 기본값을 주면 빈 파일 검사가 통째로 죽는다.
    body = _PDFBYTES if blob is None else blob
    return cu.post("/api/draft/upload",
                  files={"file": (name, body, "application/pdf")}).json()


_DOC = _post_doc("CBAM 규정.pdf")
check("PDF 를 받는다", lambda: (_DOC["ok"] and _DOC["doc"]["pages"] == 1) or 1/0)
check("글자를 뽑는다", lambda: (_DOC["doc"]["chars"] > 50
                              and "quarterly" in _DOC["doc"]["preview"]) or 1/0)
check("발췌를 목록에 싣지 않는다", lambda: ("excerpt" not in _DOC["doc"]) or 1/0)

check("PDF 아닌 확장자는 거절", lambda:
      (_post_doc("메모.txt")["reason"] == "upload_failed") or 1/0)
check("확장자만 PDF 인 것도 거절", lambda:
      (_post_doc("가짜.pdf", b"NOT A PDF")["reason"] == "upload_failed") or 1/0)
check("빈 파일 거절", lambda:
      (_post_doc("빈.pdf", b"")["reason"] == "upload_failed") or 1/0)
check("글자 없는 PDF 는 이유를 알려 준다", lambda:
      ("스캔" in _post_doc("스캔.pdf", _pdf([]))["detail"]) or 1/0)

def _escape():
    r = _post_doc("../../탈출.pdf")
    assert r["ok"], r
    assert ".." not in r["doc"]["name"], r["doc"]["name"]
    assert r["doc"]["id"] in [f.stem for f in paths.UPLOADS.rglob("*.pdf")]
    assert not list(paths.UPLOADS.parent.glob("탈출*")), "폴더 밖에 썼다"
    cu.delete(f"/api/draft/upload/{r['doc']['id']}")
check("경로 탈출을 막는다", _escape)

_EVOPTS = cu.get("/api/draft/evidence").json()["options"]

def _no_auto_confirmed_cards():
    """기사·문서를 카드로 따로 내지 않는다.

    예전에는 URL 이나 파일이 있다는 것만으로 "출처 확인됨" 을 달았다.
    확인된 것은 **주소가 존재한다는 사실**뿐인데 그게 그대로 참고자료로
    나갔다. 이제 둘 다 명제 안의 출처로 들어가 대조를 거친다.
    """
    ids = [o["id"] for o in _EVOPTS]
    assert not any(i.startswith(("doc:", "src:")) for i in ids), ids
    assert all(o["id"].startswith("claim:") for o in _EVOPTS), ids
    assert not any("출처 확인됨" in o["meta"] for o in _EVOPTS), _EVOPTS
check("기사·문서를 자동으로 확인 처리하지 않는다", _no_auto_confirmed_cards)
check("올린 문서를 프롬프트가 안다", lambda:
      (SEEN["claims"]["documents"]
       and SEEN["claims"]["documents"][0]["title"]) or 1/0)

check("올린 문서는 확인된 출처다", lambda:
      (_confirmed({"file": "abc"}) and _confirmed({"url": "https://x"})
       and not _confirmed({"title": "확인 대상"})) or 1/0)

def _label_and_split():
    """라벨과 본문 가르기가 같은 판단을 쓰는가.

    예전에는 라벨이 url 만 보고 본문은 url·file 을 봐서, 올린 PDF 가
    인용은 되는데 라벨에는 "확인 필요" 로 세어졌다.
    """
    picked = [{"payload": {"url": "https://a", "title": "기사"}},
              {"payload": {"file": "f1", "title": "문서"}},
              {"payload": {"title": "확인 대상"}}]
    lab = _st.many_label("evidence", picked)
    assert lab == "확인된 출처 2건 · 확인 필요 1건", lab
    conf, unconf = _wr._split({"evidence": {"payload": {
        "items": [p["payload"] for p in picked]}}})
    assert (len(conf), len(unconf)) == (2, 1), (conf, unconf)
check("라벨과 본문 가르기가 같은 판단을 쓴다", _label_and_split)

def _reaches_prompt():
    """검증한 명제가 본문 프롬프트까지 간다. URL 은 빼고 인용만."""
    ok = [o["id"] for o in _EVOPTS if o["payload"].get("status") in ("supported", "partial")]
    cu.post("/api/draft/evidence", json={"choice": ok or [_EVOPTS[0]["id"]], "custom": ""})
    cu.post("/api/draft/write")
    conf = SEEN["site_write"]["sources_confirmed"]
    assert all("url" not in s for s in conf), conf
check("검증한 명제가 본문 프롬프트까지 간다", _reaches_prompt)

def _deleted():
    docs = cu.get("/api/draft/upload").json()["docs"]
    for d in docs:
        assert cu.delete(f"/api/draft/upload/{d['id']}").json()["ok"]
    assert cu.delete("/api/draft/upload/없는것").json()["reason"] == "no_doc"
    assert not cu.get("/api/draft/upload").json()["docs"]
check("지우면 파일도 목록도 사라진다", _deleted)

def _pick_long():
    """긴 문서는 쪽을 골라서 넘긴다.

    앞에서부터 6000자를 자르면 표지·목차·전문만 담기고 인용할 조항이
    하나도 안 들어간다. 실제로 58쪽 규정에서 조항 세 개가 14,812자
    지점부터 시작해 전부 잘려 나갔다.
    """
    FAKE["evidence_pick"] = {"pages": [25, 26, 57], "why": "의무와 요건 조항"}
    r = _post_doc("긴 규정.pdf", _LONG)
    assert r["ok"], r
    d = r["doc"]
    assert d["picked"], d
    assert [s["page"] for s in d["segments"]] == [25, 26, 57], d["segments"]
    assert "Article 12" in d["segments"][0]["head"], d["segments"][0]
    doc = _up.docs(list(_ses._sessions.values())[-1]["draft"])
    ex = next(x for x in doc if x["id"] == d["id"])["excerpt"]
    for want in ("Reporting obligations", "Information to be obtained",
                 "Verification requirements"):
        assert want in ex, want
    for junk in ("TABLE OF CONTENTS", "Whereas"):
        assert junk not in ex, junk
check("긴 문서는 쓸 쪽만 골라 넘긴다", _pick_long)

def _pick_blind_to_title():
    """쪽 고르기도 제목·소제목을 안 본다.

    근거가 구조 앞으로 오면서 그 신호가 사라졌다. 질문으로 갈아탔는데,
    입력이 비면 표지·목차 쪽을 고르게 되므로 실려 있는지 본다.
    """
    inp = SEEN["evidence_pick"]
    assert "title" not in inp and "sections" not in inp, sorted(inp)
    assert inp["question"] and "article_type" in inp, inp
check("쪽 고르기는 질문을 본다", _pick_blind_to_title)

# ── 글자 수 상한 ──────────────────────────────────────────────
#
# 자르지 않고 거절한다. 잘라 넘기면 실패가 문서 탓인지 신호 탓인지
# 구별이 안 되고, 잘린 문서가 카드에 "출처 확인됨" 으로 뜬다.

_HUGE = _pdfp([[f"Annex Table {i}: " + "x" * 900] * 4 for i in range(1, 400)])
# 글자 총량은 한도 안인데 쪽이 많은 것. 쪽 목록만으로 프롬프트가 터진다.
_MANY = _pdfp([[f"Article {i} heading " + "y" * 380] for i in range(1, 260)])

def _too_long():
    r = _post_doc("부속서 통합본.pdf", _HUGE)
    assert r["reason"] == "upload_failed", r
    assert "문서가 깁니다" in r["detail"] and "나눠 올리" in r["detail"], r
check("긴 문서는 자르지 않고 거절한다", _too_long)

def _too_many_pages():
    r = _post_doc("쪽 많은 고시.pdf", _MANY)
    assert r["reason"] == "upload_failed", r
    assert "쪽이 많습니다" in r["detail"], r
check("쪽 목록이 크면 거절한다", _too_many_pages)

check("상한은 글자 수로 잰다", lambda: (
    _up.MAX_CHARS == 400_000 and _up.MAX_LIST == 60_000
    and _up.list_chars(["a" * 1000, "b" * 50, ""]) == _up.PEEK + 50) or 1/0)

def _reject_logged():
    """거절이 안 남으면 상한을 조정할 근거가 없다."""
    row = [r for r in history.read()
           if r.get("kind") == "rejected"][-1]
    assert row["name"] and row["bytes"] > 0 and "쪽이 많습니다" in row["reason"], row
check("거절도 자취에 남는다", _reject_logged)

# ── 올린 파일 추적 ────────────────────────────────────────────

def _upload_logged():
    """파일은 id 로만 저장된다. 원래 이름이 남는 곳은 이 행뿐이다."""
    row = [r for r in history.read() if r.get("kind") == "uploaded"][-1]
    for k in ("doc", "name", "sha", "pages", "chars"):
        assert row.get(k), (k, row)
    assert row["stream"] == "choice", row
check("올린 파일이 이름과 함께 남는다", _upload_logged)

def _doc_trace():
    """문서 하나가 지나온 자취가 doc 으로 묶인다.

    "이 파일을 넣었더니 모델이 이 쪽들을 골랐다" 가 조인 없이 읽혀야 한다.
    """
    up = [r for r in history.read()
          if r.get("kind") == "uploaded" and r.get("picked")][-1]
    got = cu.get(f"/api/logs?doc={up['doc']}&order=asc").json()
    kinds = [r["kind"] for r in got["rows"]]
    assert "uploaded" in kinds and "generated" in kinds, got["rows"]
    gen = next(r for r in got["rows"] if r["kind"] == "generated")
    assert gen["step"] == "evidence_pick" and gen["n"], gen
check("문서 하나의 자취가 doc 으로 묶인다", _doc_trace)

def _same_file_same_sha():
    """id 는 올릴 때마다 새로 난다. 같은 문서인지는 내용 지문으로 안다."""
    a = _post_doc("같은 것 1.pdf")["doc"]
    b = _post_doc("같은 것 2.pdf")["doc"]
    assert a["id"] != b["id"] and a["sha"] == b["sha"], (a, b)
check("같은 파일은 지문이 같다", _same_file_same_sha)

check("고른 쪽 번호가 발췌에 박힌다", lambda: (
    "[25쪽]" in next(x["excerpt"] for x in
                     _up.docs(list(_ses._sessions.values())[-1]["draft"])
                     if x.get("picked"))) or 1/0)

def _short_no_call():
    """한도 안에 들어가는 문서는 물어보지 않는다."""
    SEEN.pop("evidence_pick", None)
    r = _post_doc("짧은 안내.pdf")
    assert r["ok"] and not r["doc"]["picked"], r
    assert not r["doc"]["truncated"], r
    assert "evidence_pick" not in SEEN, "짧은 문서에 호출이 들었다"
check("짧은 문서는 호출하지 않는다", _short_no_call)

def _junk_pages():
    """범위 밖·중복·문자가 섞여 와도 버린다."""
    FAKE["evidence_pick"] = {"pages": [999, -3, "x", 25, 25, 26], "why": "섞임"}
    d = _post_doc("잡음.pdf", _LONG)["doc"]
    assert [s["page"] for s in d["segments"]] == [25, 26], d["segments"]
check("엉뚱한 쪽 번호를 버린다", _junk_pages)

def _pick_fails():
    """못 골라도 막지 않는다. 앞부분으로 떨어지되 이유를 남긴다."""
    old = llm.generate

    def boom(n, p, strong=False):
        if n == "evidence_pick":
            raise llm.LLMError("evidence_pick: JSON 이 아니다")
        return old(n, p, strong)
    llm.generate = boom
    try:
        d = _post_doc("실패.pdf", _LONG)["doc"]
    finally:
        llm.generate = old
    assert not d["picked"] and d["truncated"], d
    assert d["pick_error"], d
    # 앞부분에 걸린 쪽을 구간으로 남기면 7단계가 표지를 "이 문서가 다루는 것"
    # 으로 읽는다.
    assert d["segments"] == [], d["segments"]
    assert any(r.get("kind") == "failed" and r["step"] == "evidence_pick"
               for r in history.read()), "실패가 자취에 없다"
check("못 골라도 막지 않고 이유를 남긴다", _pick_fails)

def _empty_pick():
    FAKE["evidence_pick"] = {"pages": [], "why": ""}
    d = _post_doc("빈선택.pdf", _LONG)["doc"]
    assert not d["picked"] and d["pick_error"], d
check("쓸 쪽이 없다는 답도 받는다", _empty_pick)

check("무거운 값은 목록에 안 실린다", lambda: all(
    "pages_text" not in d and "excerpt" not in d
    for d in cu.get("/api/draft/upload").json()["docs"]) or 1/0)

def _merge_all():
    """근거는 고른 것과 쓴 것이 함께 담긴다.

    예전에는 직접 쓴 값이 이겨서 고른 것이 통째로 사라졌다. PDF 를 올려
    고른 다음 근거를 한 줄 더 적으면 문서 쪽이 없어졌다.
    """
    FAKE["evidence_pick"] = {"pages": [25, 26], "why": "의무 조항"}
    cu.post("/api/draft/upload",
            files={"file": ("규정.pdf", _LONG, "application/pdf")})
    opts = cu.get("/api/draft/evidence").json()["options"]
    ids = [o["id"] for o in opts]
    src, doc = ids[0], ids[1]

    r = cu.post("/api/draft/evidence", json={
        "choice": [src, doc], "custom": "관세청 안내 페이지\n거래처 제출 양식"}).json()
    assert r["ok"], r
    v = cu.get("/api/draft").json()["values"]["evidence"]
    pay = _ses._sessions[[k for k, x in _ses._sessions.items()
                          if x["draft"].get("evidence")][-1]]["draft"]["evidence"]
    items = pay["payload"]["items"]
    # 고른 것 둘 + 쓴 것 둘 + **올린 문서 전부.** 파일을 올리는 행위가
    # 이미 "이걸 근거로 쓰겠다" 는 선택이라, 카드로 또 고르게 하지 않는다.
    assert sum(1 for i in items if i.get("claim_id")) == 2, items
    assert sum(1 for i in items if i.get("kind") == "직접") == 2, items
    # **문서는 확정값에 안 담긴다.** 문서는 명제가 아니라 명제의 출처다 —
    # plan 이 걸고 check 가 대조해서 그 명제의 sources 에 이미 들어가 있다.
    assert not any(i.get("claim_to_verify") for i in items), items
    assert pay["written"] and len(pay["choice_ids"]) == 2, pay
def _verified_claims_survive():
    """확정할 때 검증된 명제가 사라지지 않는다.

    **"안 고름 = 버림" 이 이 단계엔 안 맞는다.** 화면이 "확인됨 · 공식
    근거 · 출처 3건" 이라고 표시해 놓고 다음을 누르면 사라지는 것은 앞뒤가
    안 맞는다. 실제로 supported 3건 + partial 1건을 검증해 놓고 구조가
    받은 claims 가 빈 배열이었다.
    """
    d = {"_opts": {"evidence": {"items": [
        {"id": "claim:c01", "title": "확인됨",
         "payload": {"claim_id": "c01", "status": "supported", "claim_type": "regulation"}},
        {"id": "claim:c02", "title": "일부",
         "payload": {"claim_id": "c02", "status": "partial", "claim_type": "regulation"}},
        {"id": "claim:c03", "title": "미확인",
         "payload": {"claim_id": "c03", "status": "unverified", "claim_type": "regulation"}}]}}}
    got = _sess._auto_claims(d, "evidence", [])
    assert [c["claim_id"] for c in got] == ["c01", "c02"], got
    # 고른 것이 있으면 그 뜻을 따른다
    assert _sess._auto_claims(d, "evidence", [{"x": 1}]) == []
    # 문서는 명제가 아니다. 이미 그 명제의 sources 에 들어가 있다.
    src = (paths.BACKEND / "session.py").read_text(encoding="utf-8")
    assert "_doc_items" not in src, "문서를 명제로 바꾼다"
    assert "claim_to_verify" not in src, "문서 제목이 명제가 된다"
check("검증된 명제가 확정에서 사라지지 않는다", _verified_claims_survive)

def _partial_sends_confirmed_only():
    """partial 은 확인된 부분만 넘긴다.

    명제 전문을 주면 구조가 전체를 확인된 사실로 읽는다. 실제로 "모든
    수입에 신고 의무" 가 확인된 것처럼 흘러갔다 — 원문은 50톤 미만 면제를
    함께 말하고 있었다.
    """
    d = {"evidence": {"payload": {"items": [
        {"claim_id": "c02", "claim": "모든 수입에 신고 의무", "status": "partial",
         "claim_type": "regulation", "sources": [
             {"supported_parts": ["2026년부터 연간 신고 의무가 있다"],
              "unsupported_parts": ["예외 없이 모든 수입에 적용된다"],
              "limitations": ["50톤 미만은 면제"]}]}]}}}
    row = _out.brief(d)[0]
    assert row["confirmed_parts"] == ["2026년부터 연간 신고 의무가 있다"], row
    assert row["unconfirmed_parts"], row
    assert "confirmed_parts` 만 확인된 것이다" in _md("_prompt", "outline")
    # supported 에는 안 붙는다 — 명제 전체가 확인된 것이다
    d["evidence"]["payload"]["items"][0]["status"] = "supported"
    assert "confirmed_parts" not in _out.brief(d)[0]
check("partial 은 확인된 부분만 넘긴다", _partial_sends_confirmed_only)

def _warn_before_choosing():
    """근거가 없다는 것을 구조를 고르기 전에 알린다.

    결과물을 만든 뒤에 알면 늦다. 사람이 구조를 고를 때 무엇을 감수하는지
    알아야 한다.
    """
    base = {"outline": {"payload": {"sections": []}}, "type": {"payload": {}},
            "reader": {"payload": {}}, "angle": {"payload": {}},
            "intent": {"payload": {}}, "topic": {"label": "t", "payload": {}},
            "title": {"payload": {}}, "channel": {"payload": {"channel": "naver"}}}
    none = _sess.warn_of({**base, "evidence": {"payload": {"items": []}}}, "outline")
    assert "근거가 하나도 없습니다" in none, none
    some = _sess.warn_of({**base, "evidence": {"payload": {"items": [
        {"claim_id": "c01", "status": "unverified", "claim_type": "regulation",
         "sources": []}]}}}, "outline")
    assert "확인 필요 1건" in some, some
    ok = _sess.warn_of({**base, "evidence": {"payload": {"items": [
        {"claim_id": "c01", "status": "supported", "claim_type": "regulation",
         "sources": []}]}}}, "outline")
    assert ok == "", ok
    assert _sess.warn_of(base, "reader") == "", "앞 단계에는 안 붙는다"
    assert "D.warn" in _js("pages/step.js"), "화면이 안 보여 준다"
check("근거 없음을 구조 고르기 전에 알린다", _warn_before_choosing)

check("근거는 고른 것과 쓴 것을 함께 담는다", _merge_all)

def _merge_trail():
    row = [r for r in history.read()
           if r.get("kind") == "confirmed" and r["step"] == "evidence"][-1]
    assert row["chosen"] and row["written"], row
check("자취에 고른 것과 쓴 것이 같이 남는다", _merge_trail)

def _single_still_either():
    """하나만 고르는 단계는 그대로 둘 중 하나다."""
    c2 = TestClient(app)
    c2.post("/api/topics/pick", json={"topic_id": "t1"})
    walk_to(c2, "reader")
    o = c2.get("/api/draft/reader").json()["options"][0]["id"]
    c2.post("/api/draft/reader", json={"choice": [o], "custom": "내가 쓴 독자"})
    v = c2.get("/api/draft").json()["values"]["reader"]
    assert v["label"] == "내가 쓴 독자", v
check("하나만 고르는 단계는 여전히 둘 중 하나", _single_still_either)

check("쓴 것만 있어도 담긴다", lambda: (lambda r: r["ok"])(
    cu.post("/api/draft/evidence",
            json={"choice": [], "custom": "직접 쓴 근거 하나"}).json()) or 1/0)
def _refusal_reasons_split():
    """왜 못 넘어가는지 갈라서 알린다.

    `empty` 하나로 뭉개면 사람이 무엇을 해야 할지 모른다. **PDF 를 올려
    두고 막혔을 때 "빈 입력" 이라고 말한 것**이 실제 사고였다.
    """
    # 검증된 명제가 있으면 아무것도 안 골라도 넘어간다
    d = {"_opts": {"evidence": {"items": [
        {"id": "claim:c01", "title": "확인됨",
         "payload": {"claim_id": "c01", "status": "supported",
                     "claim_type": "regulation"}}]}}}
    assert _sess._auto_claims(d, "evidence", []), "확인된 명제가 안 담긴다"

    # 고를 것도 쓸 것도 없는 새 세션에서는 거절하고, 사유를 준다
    c2 = TestClient(app)
    c2.get("/api/topics"); c2.post("/api/topics/pick", json={"topic_id": "t1"})
    for k in ("channel", "reader", "intent", "angle", "type"):
        o = c2.get(f"/api/draft/{k}").json()
        c2.post(f"/api/draft/{k}", json={"choice": [o["options"][0]["id"]], "custom": ""})
    c2.get("/api/draft/evidence")
    bad = c2.post("/api/draft/evidence", json={"choice": [], "custom": ""}).json()
    # 검증된 명제가 있으면 안 고르고도 넘어간다. 없으면 사유를 준다.
    assert bad["ok"] or bad["reason"] == "no_sources", bad
    # 화면이 사유별 문구를 든다
    assert "no_sources" in _js("ui.js") and "err.reason" in _js("api.js")
check("못 넘어가는 이유를 갈라 준다", _refusal_reasons_split)

def _repeated_headers_dropped():
    """쪽마다 되풀이되는 줄은 쪽 이름으로 안 쓴다.

    9쪽짜리 가이드를 올렸더니 근거 구간 목록이 이렇게 나왔다.

        4쪽  EU CBAM 본격 시행 대응 가이드 | 2026.08.06 기준
        5쪽  EU CBAM 본격 시행 대응 가이드 | 2026.08.06 기준

    쪽마다 같은 문구라 **어느 쪽에 무엇이 있는지 알 수 없다.** 한 쪽만
    봐서는 머리글인지 못 가리므로 문서 전체에서 센다.
    """
    from backend.steps.evidence import upload as _up2
    heads = ["제품별 배출량 산정", "증빙 자료 구성", "통관 자료 구분",
             "검증기관 선정", "신고 일정", "자주 묻는 질문"]
    pages = [f"EU CBAM 대응 가이드 | 2026.08.06 기준\n{i}\n{t}\n본문." 
             for i, t in enumerate(heads, 1)]
    skip = _up2.headers(pages)
    assert any("가이드" in x for x in skip), skip
    for i, t in enumerate(pages):
        assert _up2.head(t, skip=skip) == heads[i], (i, _up2.head(t, skip=skip))
    # 쪽 번호와 기준일만 있는 줄도 안 쓴다
    assert _up2._noise("12") and _up2._noise("2026.08.06 기준") and _up2._noise("- 4 -")
    assert not _up2._noise("제품별 배출량 산정 범위")
check("반복 머리글을 쪽 이름으로 안 쓴다", _repeated_headers_dropped)

def _mock_is_visible():
    """개발용 견본인지 화면이 안다.

    키가 안 읽히는데 t1a·c1 같은 가짜 후보가 뜨면 **잘 돌고 있는 줄
    안다.** 지우지는 않는다 — 키 없이 화면 흐름을 보려고 둔 것이다.
    """
    assert cu.get("/api/health").json()["mode"] in ("real", "mock")
    assert "mock" in cu.get("/api/draft/channel").json()
    assert "D.mock" in _js("pages/step.js"), "화면이 안 알린다"
check("개발용 견본을 화면이 알린다", _mock_is_visible)

def _upload_feedback_survives():
    """올린 뒤 화면을 다시 그려도 결과 문구가 남는다.

    올리면 화면 전체를 다시 받는데(문서가 후보에도 영향을 준다), 그때
    상자가 새로 만들어지면서 **파일도 메시지도 사라진다.** 사람은 아무
    일도 안 일어난 줄 안다.
    """
    js = _js("ui.js")
    assert "upSaid" in js, "다시 그린 뒤 알릴 자리가 없다"
    assert "esc(upSaid)" in js, "다시 그릴 때 안 싣는다"
    # 한 개만 올려도 알린다. done > 1 이면 한 개일 때 아무 말이 없다.
    assert "(done ? done + '개를 올렸습니다'" in js, "한 개를 올리면 조용하다"
    # 다시 그리다 터지면 화면이 멈춘다
    assert ".catch(function (e) { UI.fail(UI.why(e)); });" in _js("pages/step.js")
check("올린 뒤 결과가 화면에 남는다", _upload_feedback_survives)

def _upload_shows_progress():
    """올리는 동안 상자가 진행 상태를 보인다.

    PDF 하나에 30초 넘게 걸린다 — 글자를 뽑고 어느 쪽을 쓸지 모델이 고른다.
    그동안 아래쪽 한 줄뿐이면 **스크롤 밖일 때 아무 일도 안 일어나는 것처럼
    보인다.** 사람은 올라가고 있는지 알 수 없다.
    """
    js = _js("ui.js")
    assert "up-work" in js and "function working(" in js, "진행 표시가 없다"
    assert "working(true," in js and "working(false)" in js, "켜고 끄지 않는다"
    # 여러 개면 몇 번째인지 보인다
    assert "' / ' + total" in js, "몇 번째인지 안 보인다"
    css = (paths.ROOT / "frontend" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".up-spin" in css and "up-turn" in css, "돌아가는 표시가 없다"
check("올리는 동안 진행이 보인다", _upload_shows_progress)

def _wrong_article_dropped():
    """가져온 글이 그 기사가 아니면 버린다.

    뉴스 주소는 기사가 내려가면 다른 기사로 넘어간다. 실제로
    "CBAM 신고 의무, 무엇이 달라지나" 를 가져왔더니 치약 기사가 왔다.
    대조가 걸러 주긴 하지만, 우연히 관련 있는 글이면 그대로 붙는다.
    """
    from backend.steps.evidence import _is_same
    assert _is_same("CBAM 신고 의무, 무엇이 달라지나",
                    "CBAM 신고 의무가 무엇이 달라지나 살펴본다. 전환기간이 끝나고")
    assert not _is_same("CBAM 신고 의무, 무엇이 달라지나",
                        "케이엠제약이 틀니 세정제 제형을 개발해 특허를 출원했다.")
    # 사이트가 제목을 줄이거나 말머리를 붙여도 통과해야 한다
    assert _is_same("EU CBAM 본시행 앞두고 국내 수출기업 준비 미흡",
                    "[단독] EU CBAM 본시행을 앞두고 국내 수출기업의 준비가 미흡하다")
    assert not _is_same("제목", "")
check("엉뚱한 기사를 근거로 안 쓴다", _wrong_article_dropped)

def _stale_article_told():
    """기사 주소가 낡은 것을 발행 전에 알린다.

    코드가 걸러 내지만 **소재를 고른 근거였던 기사가 사라졌다**는 뜻이다.
    """
    from backend.output import checklist as _ck9
    out = []
    _ck9._stale_articles(out, {"evidence": {"payload": {"items": [
        {"status": "wrong_page", "title": "기사"}]}}})
    assert out and out[0]["kind"] == "기사 주소가 낡음", out
    out2 = []
    _ck9._stale_articles(out2, {"evidence": {"payload": {"items": [
        {"status": "fetched"}]}}})
    assert out2 == [], out2
check("낡은 기사 주소를 발행 전에 알린다", _stale_article_told)

check("upload 플래그가 화면에 나간다", lambda: (
    _st.meta_of("evidence").get("upload") is True
    and "upload" not in _st.meta_of("reader")) or 1/0)

print("\n── 단계 폴더 규칙 ──")
_STEPDIR = paths.BACKEND / "steps"
_STEPDIRS = {k: v for k, v in _st.DIR_OF.items()}

def _no_cross_import():
    """단계 폴더가 다른 단계 폴더를 import 하지 않는다.

    앞 단계 값은 항상 드래프트 dict 에서 키로 읽는다. 이걸 어기면 순서를
    바꿀 때 import 가 꼬이고 "이 폴더만 보면 된다" 가 성립하지 않는다.
    """
    bad = []
    for me, mydir in _STEPDIRS.items():
        for f in mydir.rglob("*.py"):
            src = f.read_text(encoding="utf-8")
            for other in _STEPDIRS:
                if other == me:
                    continue
                # 같은 층이면 ..other, 다른 층이면 ...층.other 로 온다.
                for form in (f"from ..{other}", f"import ..{other}",
                             f".{other} import", f"steps.{other}"):
                    if form in src:
                        bad.append(f"{me} → {other} ({f.name})")
    assert not bad, bad
check("단계끼리 import 하지 않는다", _no_cross_import)

def _no_local_sanitizer():
    """정제 헬퍼를 폴더마다 다시 정의하지 않는다.

    _s 하나가 여섯 폴더에 복사되면 자르는 길이가 달라지거나 한쪽만 고쳐지고,
    그런 어긋남은 예외 없이 조용히 지나간다.
    """
    bad = []
    for f in _STEPDIR.rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        for name in ("def _s(", "def _texts(", "def _lines(", "def _enum("):
            if name in src:
                bad.append(f"{f.relative_to(paths.BACKEND)} : {name}")
    assert not bad, bad
check("정제 헬퍼를 복제하지 않았다", _no_local_sanitizer)

def _all_registered():
    """LLM 을 쓰는 단계는 부를 이름이 등록돼 있어야 한다.

    채널마다 다른 것을 요구하는 단계는 이름이 {채널}_{key} 라 key 로 찾으면
    없다. 그 단계가 실제로 부르는 이름으로 본다.
    """
    from backend import prompt as _pr
    names = set(_pr.names())
    for key in _st.TIERS:
        st = _st.BY_KEY[key]
        for ch in (_cn.NAMES if st.by_channel else ("site",)):
            assert st.prompt_of(ch) in names, (key, ch, st.prompt_of(ch))
check("프롬프트가 전부 등록됐다", _all_registered)

check("등록된 프롬프트 파일이 다 있다", lambda: all(
    __import__("backend.prompt", fromlist=["x"]).where(n).exists()
    for n in __import__("backend.prompt", fromlist=["x"]).names()) or 1/0)
check("밑바탕 파일도 다 있다", lambda: all(
    f.exists() for f in
    __import__("backend.prompt", fromlist=["x"]).BASE.values()) or 1/0)
check("모르는 프롬프트는 그 자리에서 터진다", lambda: (_ for _ in ()).throw(
    AssertionError("안 터졌다")) if not _raises_missing() else None)
check("순서는 order() 한 곳이 정한다", lambda: (
    [s["no"] for s in _st.meta()] == list(range(1, len(_st.meta()) + 1))
    and [s["key"] for s in _st.meta()] == _st.keys()) or 1/0)
def _order_by_channel():
    """채널 목록을 따로 선언한다.

    지금 둘이 같아도 같은 리스트 객체를 가리키면, 한쪽에 단계를 끼울 때
    다른 쪽까지 바뀐다. 나중에 네이버에만 사진 준비 단계를 넣게 되면
    그 사고가 난다.
    """
    assert _st.SITE_ORDER is not _st.NAVER_ORDER, "같은 객체를 공유한다"
    nav = _st.keys({"channel": {"payload": {"channel": "naver"}}})
    assert nav == _st.keys({"channel": {"payload": {"channel": "site"}}})
    # 채널 전에는 미리보기로 보인다 — 빈 목록이면 남은 단계가 둘로 보인다
    assert _st.keys() == nav, _st.keys()
    assert len({s.key for s in _st.ALL}) == len(_st.ALL), "등록부에 중복이 있다"
check("채널별 순서를 따로 선언한다", _order_by_channel)
check("BY_KEY 는 순서와 무관하다", lambda: (
    set(_st.BY_KEY) == {s.key for s in _st.ALL}) or 1/0)
check("상위 등급은 outline 뿐", lambda: (
    {k for k, v in _st.TIERS.items() if v == "strong"} == {"outline"}) or 1/0)

print("\n── 근거 판정 규칙 ──")

from backend.steps.evidence import policy as _po, claims as _cl

def _span_normalized():
    """정규화하고 대조한다. 안 하면 정상 인용도 걸린다.

    pypdf 는 하이픈 분철을 남기고, 웹 본문에는 유니코드 따옴표가 섞이고,
    모델이 인용을 옮기며 공백을 흘린다.
    """
    src = "The declarant shall submit a quarterly re-\nport within one month."
    assert _po.span_ok("quarterly report  within one month", src)
    assert not _po.span_ok("annual report within one month", src)
    assert not _po.span_ok("report", src), "짧은 인용은 우연히 맞는다"
check("인용 대조는 정규화한 뒤에 한다", _span_normalized)

def _status_by_code():
    """supported 는 모델이 쓰지 않는다. 인용이 원문에 있을 때만 코드가 준다."""
    src = "quarterly report within one month"
    ok = {"verdict": "supported", "evidence_spans": [{"quote": src}]}
    fake = {"verdict": "supported", "evidence_spans": [{"quote": "지어낸 문장입니다"}]}
    assert _po.status_of(ok, src)[0] == "supported"
    assert _po.status_of(fake, src)[0] == "invalid_check", "지어낸 인용이 통과했다"
    assert _po.status_of({"verdict": "partial", "evidence_spans": [{"quote": src}]}, src)[0] == "partial"
    assert _po.status_of({"verdict": "contradicted"}, src)[0] == "contradicted"
    assert _po.status_of(ok, "")[0] == "unverified", "원문이 없으면 미확인"
check("지어낸 인용은 supported 가 되지 않는다", _status_by_code)

check("반박이 뒷받침을 이긴다", lambda: (
    _po.best(["supported", "contradicted"]) == "contradicted"
    and _po.best(["partial", "supported"]) == "supported"
    and _po.best([]) == "unverified") or 1/0)

def _selectable_one_place():
    """고를 수 있는가와 인용할 수 있는가는 다르다."""
    inf = {"status": "unverified", "claim_type": "inference"}
    fact = {"status": "unverified", "claim_type": "fact"}
    assert _po.selectable(inf) and not _po.citable(inf), "추론에 출처가 붙는다"
    assert not _po.selectable(fact)
    assert _po.selectable({"status": "partial", "claim_type": "fact"})
    assert not _po.selectable({"status": "contradicted", "claim_type": "fact"})
check("추론은 골라도 인용은 못 한다", _selectable_one_place)

def _limits_leave_a_trace():
    """상한에 걸린 것을 버리지 않는다. 조용히 사라지면 왜 없는지 모른다."""
    rows = [{"claim_id": f"c{i}", "searchable": True, "reason_code": ""}
            for i in range(_po.MAX_CLAIMS + 2)]
    rows.append({"claim_id": "x", "searchable": False, "reason_code": ""})
    live, rest = _cl.to_check(rows)
    assert len(live) == _po.MAX_CLAIMS, len(live)
    assert len(rest) == 3, rest
    assert {r["reason_code"] for r in rest} == {"check_limit_exceeded", "not_searchable"}
check("상한에 걸린 것도 사유와 함께 남는다", _limits_leave_a_trace)

check("검색이 없으면 조용히 넘어가지 않는다", lambda: (
    not _sr.ENABLED or 1) and ("TAVILY_API_KEY 가 없다" in
    __import__("inspect").getsource(_sr._post)) or 1/0)


def _pipeline_end_to_end():
    """네 조각이 이어져 상태가 붙는가. 지어낸 인용이 통과하지 않는가.

    검색과 대조를 가짜로 두고 명제 하나를 태운다. 진짜 인용과 지어낸 인용을
    차례로 주고 상태가 갈리는지 본다 — 여기가 이 단계 설계의 전부다.
    """
    from backend.steps.evidence import search as _se
    from backend.steps import evidence as _ev
    old_gen, old_en = llm.generate, _se.api.ENABLED
    old_s, old_f = _se.api.search, _se.api.fetch

    SRC = ("Article 13. The reporting declarant shall obtain from the operator "
           "the information necessary to determine embedded emissions.")
    FK = {
      "claims": {"claims": [
        {"claim": "수입자가 공급자에게 배출량 정보를 요구할 수 있다",
         "claim_type": "regulation", "required_source": "제도 원문",
         "searchable": True, "why": "질문의 전제"},
        {"claim": "대응이 선적 일정 조율을 늘릴 수 있다", "claim_type": "inference",
         "required_source": "실무 사례", "searchable": False, "why": "실무 영향"}]},
      "plan": {"plans": [{"claim_ref": "c01", "queries": [
        {"language": "en", "source_target": "official_primary",
         "query": "CBAM importer supplier emissions"}]}]},
    }
    real = {"verdict": "supported", "supported_parts": ["요구할 수 있다"],
            "unsupported_parts": [], "reason": "조항", "limitations": ["수입자 기준"],
            "evidence_spans": [{"quote": "The reporting declarant shall obtain from the operator",
                                "location": "Article 13"}]}
    fake = {"verdict": "supported", "supported_parts": [], "unsupported_parts": [],
            "reason": "", "limitations": [],
            "evidence_spans": [{"quote": "원문에 없는 지어낸 문장입니다", "location": "x"}]}

    def run(check_out):
        _se.api.ENABLED = True
        _se.api.search = lambda q, lang="ko": [
            {"title": "EU Regulation", "url": "https://eur-lex.europa.eu/x",
             "snippet": "s", "score": 0.9, "language": lang}]
        _se.api.fetch = lambda u: SRC
        llm.generate = lambda n, p, strong=False: (
            check_out if n == "check" else FK[n])
        d = {"_sid": "pl", "topic": {"label": "CBAM", "payload": {}},
             "intent": {"payload": {"question": "무엇부터 확인하나?", "sub_questions": []}},
             "angle": {"payload": {"core_message": "m"}},
             "type": {"payload": {"article_type": "가이드형"}},
             "reader": {"payload": {"role": "담당자"}}}
        return _ev.verified(d, _ev.build_input(d), "pl")

    try:
        rows = run(real)
        c1 = next(c for c in rows if c["claim_id"] == "c01")
        assert c1["status"] == "supported", c1
        # 실제로 걸린 곳이 EUR-Lex 이므로 규정 명제의 자격이 충분하다
        assert c1["authority"] == "sufficient", c1["authority"]
        assert c1["sources"][0]["actual_target"] == "official_primary", c1["sources"][0]
        assert c1["sources"][0]["evidence_spans"], c1["sources"][0]
        c2 = next(c for c in rows if c["claim_id"] == "c02")
        assert c2["status"] == "unverified" and c2["reason_code"] == "not_searchable", c2

        # 같은 명제·같은 본문이므로 캐시가 앞의 판정을 준다. 여기서는
        # 지어낸 인용을 어떻게 다루는지 보려는 것이라 비우고 들어간다.
        from backend.steps.evidence import check as _ck2
        _ck2._SEEN.clear(); _ck2._KEYS.clear()
        bad = next(c for c in run(fake) if c["claim_id"] == "c01")
        assert bad["status"] == "invalid_check", bad["status"]
        assert bad["sources"][0]["retried"] == _po.MAX_RETRY, bad["sources"][0]
        assert not _po.selectable(bad), "지어낸 인용을 고를 수 있다"
    finally:
        llm.generate, _se.api.ENABLED = old_gen, old_en
        _se.api.search, _se.api.fetch = old_s, old_f
check("명제 → 검색 → 대조까지 이어진다", _pipeline_end_to_end)

def _plan_by_id_not_index():
    """claim_ref 를 인덱스로 맞추지 않는다.

    여섯을 주면 다섯만 돌려주는 일이 있다. 인덱스로 짝을 지으면 그때부터
    조용히 밀린 명제에 엉뚱한 질의가 붙는다.
    """
    from backend.steps.evidence import plan as _pl
    old = llm.generate
    llm.generate = lambda n, p, strong=False: {"plans": [
        {"claim_ref": "c99", "queries": [{"language": "ko",
         "source_target": "secondary", "query": "없는 명제"}]},
        {"claim_ref": "c01", "queries": [{"language": "ko",
         "source_target": "official_primary", "query": "있는 명제"}]}]}
    try:
        got = _pl.make({"topic": {"label": "x", "payload": {}},
                        "intent": {"payload": {}}},
                       [{"claim_id": "c01", "claim": "a", "claim_type": "fact",
                         "required_source": ""}])
    finally:
        llm.generate = old
    assert set(got["queries"]) == {"c01"}, got
check("모르는 claim_id 는 붙이지 않는다", _plan_by_id_not_index)

def _claims_feed_body():
    """검증된 명제가 본문 프롬프트까지 간다. 상태와 인용을 달고."""
    from backend.output import write as _w
    d = {"evidence": {"payload": {"items": [
        {"claim_id": "c01", "claim": "확인된 명제", "claim_type": "regulation",
         "status": "supported", "sources": [{"status": "supported",
            "title": "원문", "url": "https://x/y",
            "evidence_spans": [{"quote": "원문의 대목"}],
            "unsupported_parts": [], "limitations": ["범위 주의"]}]},
        {"claim_id": "c02", "claim": "추론 명제", "claim_type": "inference",
         "status": "unverified", "required_source": "사례", "sources": []}]}}}
    conf, unconf = _w._split(d)
    assert len(conf) == 1 and conf[0]["quotes"] == ["원문의 대목"], conf
    assert conf[0]["limitations"] == ["범위 주의"], conf
    assert len(unconf) == 1 and unconf[0]["status"] == "unverified", unconf
check("검증된 명제가 인용과 함께 본문으로 간다", _claims_feed_body)

def _refs_are_sources():
    """참고자료에 명제가 아니라 원문이 실린다.

    명제를 실으면 "우리가 한 말" 이 출처로 나간다. 같은 원문이 여러 명제를
    뒷받침하는 일이 흔해서 겹치는 것도 걷어낸다.
    """
    from backend.output import common as _cm
    w = {"sections": [{"cites": ["s0", "s1", "s2"]}], "sources": [
        {"id": "s0", "kind": "명제", "title": "명제 문장이다",
         "ref_title": "EU 이행규정", "url": "https://x/y", "source": "official_primary"},
        {"id": "s1", "kind": "명제", "title": "다른 명제다",
         "ref_title": "EU 이행규정", "url": "https://x/y", "source": "official_primary"},
        {"id": "s2", "title": "기사 제목", "url": "https://news/1", "source": "매체"}]}
    refs = _cm.references(w)
    assert [r["title"] for r in refs] == ["EU 이행규정", "기사 제목"], refs
check("참고자료에는 명제가 아니라 원문이 실린다", _refs_are_sources)

def _compare_two_shapes():
    """모델이 columns 를 두 가지 모양으로 보낸다. 칸 수로 가른다.

        A. 비교 대상만    columns=[스코프1,2,3]      cells 3개
        B. 기준 이름까지  columns=[판단결과,중요도,조건,기록]  cells 3개

    A 에서 columns[0] 을 기준 이름으로 쓰면 **스코프1 자료가 통째로
    사라지고 나머지가 한 칸씩 밀린다.** B 에서 안 쓰면 이름이 하나
    남아돌아 표가 밀린다. **실제로 둘 다 겪었다.**
    """
    a = _fg._compare({"columns": ["스코프1", "스코프2", "스코프3"], "rows": [
        {"criterion": "기업과의 관계", "cells": ["소유·통제", "구매 에너지", "가치사슬"]}]})
    assert a["head"] == "구분", a["head"]
    assert a["columns"] == ["스코프1", "스코프2", "스코프3"], a["columns"]
    assert a["rows"][0]["cells"] == ["소유·통제", "구매 에너지", "가치사슬"], a["rows"][0]

    b = _fg._compare({"columns": ["판단 결과", "배출 중요도", "데이터 조건", "남길 기록"],
                      "rows": [{"criterion": "우선 산정",
                                "cells": ["큼", "확보 가능", "출처와 범위"]}]})
    assert b["head"] == "판단 결과", b["head"]
    assert len(b["columns"]) == len(b["rows"][0]["cells"]) == 3, b
check("대조표가 두 가지 입력 모양을 가른다", _compare_two_shapes)

def _compare_columns_align():
    """대조표 헤더 칸과 본문 칸이 맞는다.

    실제 결과물에서 어긋났다 — 열 이름 넷을 주고 criterion 까지 다섯 칸이
    되어 표가 한 칸 밀렸다. 원인이 둘이었다.

    ① 칸을 len(cols) 로 맞춘 뒤 cols 를 잘라서, 열이 다섯이면 헤더 넷에
       본문 다섯 칸이 붙었다.
    ② 렌더가 criterion 앞에 빈 <th> 를 뒀는데, 모델은 그 자리 이름을
       columns[0] 에 넣어 보낸다.
    """
    import re as _re2
    d = {"columns": ["판단 결과", "배출 중요도", "데이터 조건", "남길 기록"],
         "rows": [{"criterion": "우선 산정",
                   "cells": ["큼", "현재 확보 가능", "자료 출처와 산정 범위"]}]}
    built = _fg._compare(d)
    assert built["head"] == "판단 결과", built
    assert built["columns"] == ["배출 중요도", "데이터 조건", "남길 기록"], built

    h = _fg.html(_fg.figure("대조표", "x", d))
    head = h.split("</thead>")[0]
    body = h.split("</thead>")[1].split("</tr>")[0]
    assert len(_re2.findall(r"<th>", head)) == 4, head
    assert 1 + len(_re2.findall(r"<td>", body)) == 4, body

    # 열이 넘쳐도 안 밀린다
    over = _fg._compare({"columns": ["기준", "A", "B", "C", "D", "E"],
                         "rows": [{"criterion": "x", "cells": ["1", "2", "3", "4", "5"]}]})
    assert len(over["columns"]) == len(over["rows"][0]["cells"]), over
    assert len(over["columns"]) <= _fg.MAX_COLS - 1, over
check("대조표 열과 칸이 어긋나지 않는다", _compare_columns_align)

def _role_reaches_body():
    """섹션 역할이 본문 프롬프트까지 간다.

    "role 이 어울리는 맺음을 알려 준다" 고 적어 두고 **정작 값을 안 넘기고
    있었다.** 프롬프트가 없는 값을 읽으려 한 셈이다.
    """
    d = {"outline": {"payload": {"sections": [
            {"title": "가", "role": "comparison", "claim_refs": ["c01"]}]}},
         "type": {"payload": {}}, "reader": {"payload": {}},
         "angle": {"payload": {}}, "intent": {"payload": {}},
         "topic": {"label": "t", "payload": {}}, "title": {"payload": {}},
         "evidence": {"payload": {}}, "channel": {"payload": {"channel": "naver"}}}
    assert _wr.build_input(d)["sections"][0]["role"] == "comparison"
    assert "role" in _md("_write"), "본문 프롬프트가 role 을 안 설명한다"
check("섹션 역할이 본문까지 간다", _role_reaches_body)

def _same_document_once():
    """같은 문서의 PDF 와 안내 페이지를 둘로 세지 않는다.

    실제 참고자료에 이렇게 나왔다.
        Corporate Value Chain (Scope 3) Accounting and ...
        Corporate Value Chain (Scope 3) Standard
    """
    from backend.output import common as _cm2
    w = {"sections": [{"cites": ["s0", "s1", "s2"]}], "sources": [
        {"id": "s0", "ref_title": "Corporate Value Chain (Scope 3) Accounting and ...",
         "url": "https://ghgprotocol.org/sites/x.pdf"},
        {"id": "s1", "ref_title": "Corporate Value Chain (Scope 3) Standard",
         "url": "https://ghgprotocol.org/corporate-value-chain"},
        {"id": "s2", "ref_title": "Product Carbon Footprint (PCF)",
         "url": "https://normative.io/insight/pcf"}]}
    got = _cm2.references(w)
    assert len(got) == 2, [r["title"] for r in got]
    # 도메인이 다르면 다른 문서다 — 같은 제목의 다른 기관 자료를 접으면 안 된다
    w2 = {"sections": [{"cites": ["a", "b"]}], "sources": [
        {"id": "a", "ref_title": "같은 제목", "url": "https://one.org/x"},
        {"id": "b", "ref_title": "같은 제목", "url": "https://two.org/x"}]}
    assert len(_cm2.references(w2)) == 2
check("같은 문서를 참고자료에 두 번 안 싣는다", _same_document_once)

def _refs_only_cited():
    from backend.output import common as _cm
    """본문이 안 쓴 것은 참고자료가 아니다.

    sources 는 프롬프트에 넘긴 목록이라 안 쓴 것도 들어 있다. 그것까지
    실으면 읽어 보지도 않은 자료가 출처로 나간다.
    """
    w = {"sections": [{"cites": ["s0"]}, {"cites": []}], "sources": [
        {"id": "s0", "ref_title": "쓴 원문", "url": "https://a"},
        {"id": "s1", "ref_title": "안 쓴 원문", "url": "https://b"}]}
    assert [r["title"] for r in _cm.references(w)] == ["쓴 원문"], _cm.references(w)
    # 아무것도 안 썼으면 참고자료도 없다
    assert _cm.references({"sections": [{"cites": []}],
                           "sources": [{"id": "s0", "title": "x"}]}) == []
check("참고자료는 실제로 인용한 것만", _refs_only_cited)

check("두 렌더러가 같은 참고자료를 본다", lambda: (
    "C.references(w)" in (paths.BACKEND / "output" / "site" / "render.py").read_text(encoding="utf-8")
    and "C.references(w)" in (paths.BACKEND / "output" / "naver" / "render.py").read_text(encoding="utf-8")) or 1/0)

def _body_prompt_reads_status():
    """본문 규칙이 상태를 읽는다. 안 읽으면 검증한 것이 본문에 안 반영된다."""
    md = _md("_write")
    for want in ("`partial`", "unsupported_parts", "limitations",
                 "contradicted", "출처를 달지 않습니다"):
        assert want in md, want
check("본문 규칙이 명제 상태를 읽는다", _body_prompt_reads_status)

def _card_shows_quotes():
    """카드를 펼치면 원문의 어느 대목이 근거인지 보인다.

    겉면의 "확인됨 · 출처 2건" 만으로는 왜 확인됐다는 건지 알 수 없고,
    지어낸 인용이 걸린 경우도 눈에 안 띈다.
    """
    js = _js("shape.js")
    assert "evidence: { detail: claimDetail" in js, "근거 단계가 안 걸렸다"
    for want in ("evidence_spans", "unsupported_parts", "limitations", "cl-q"):
        assert want in js, want
check("명제 카드가 인용을 펼친다", _card_shows_quotes)

def _check_logs_success():
    """대조 결과를 성공도 남긴다.

    실패만 남기면 "이 명제를 이 원문과 대조했더니 이렇게 나왔다" 가 어디에도
    없어서 대조 프롬프트를 고칠 근거가 사라진다. invalid_check 가 얼마나
    자주 나는지도 이 기록으로만 안다.
    """
    from backend.steps.evidence import check as _chk
    src = "The declarant shall obtain the information from the operator."
    old = llm.generate
    llm.generate = lambda n, p, strong=False: {
        "verdict": "supported", "supported_parts": [], "unsupported_parts": [],
        "reason": "조항", "limitations": [],
        "evidence_spans": [{"quote": "shall obtain the information", "location": "13"}]}
    try:
        _chk.one({"claim_id": "c01", "claim": "명제", "claim_type": "regulation"},
                 {"title": "원문", "url": "https://x", "text": src}, "logtest")
    finally:
        llm.generate = old
    rows = [r for r in history.read()
            if r.get("sid") == "logtest" and r["step"] == "check"]
    assert rows and rows[-1]["kind"] == "generated", rows
    o = rows[-1]["options"][0]
    assert o["payload"]["status"] == "supported" and "supported → supported" in o["meta"], o
def _check_cache_survives_rewording():
    """같은 명제를 같은 본문에 두 번 대조하지 않는다.

    PDF 를 올리면 명제를 다시 만드는데, 표현이 조금 흔들린다 —
    "전환기간에는 CBAM 대상..." 이 "CBAM 전환기간에는 대상..." 이 된다.
    그때마다 다시 대조하면 **검증이 통째로 두 번 돈다.** 실제로 4분이
    걸렸고 검색 14회 · 대조 20회였다.
    """
    from backend.steps.evidence import check as _ck
    old_gen, old_en, old_seen = llm.generate, llm.ENABLED, dict(_ck._SEEN)
    n = [0]
    def fake(name, inp, strong=False):
        n[0] += 1
        return {"verdict": "supported", "supported_parts": ["x"],
                "unsupported_parts": [],
                "evidence_spans": [{"quote": "Article 13 shall obtain", "location": "13"}],
                "reason": "r", "limitations": []}
    llm.generate, llm.ENABLED = fake, True
    _ck._SEEN.clear(); _ck._KEYS.clear()
    SRC = "Article 13 shall obtain from the operator the information necessary."
    src = lambda: [{"url": "https://x/a", "title": "T", "status": "fetched", "text": SRC,
                    "requested_target": "official_primary",
                    "actual_target": "official_primary"}]
    row = lambda cid, t: [{"claim_id": cid, "claim": t, "claim_type": "regulation",
                           "status": "unverified", "reason_code": "", "sources": []}]
    # **짧은 명제도 잡아야 한다.** 낱말 하나 차이가 크게 나온다 —
    # "적용되었다" 와 "적용된다" 만 달라도 네 낱말짜리면 0.75 다.
    R = "regulation"
    assert _ck.same_claim({"claim": "전환기간에는 보고 의무가 적용되었다", "claim_type": R},
                          {"claim": "전환기간에는 보고 의무가 적용된다", "claim_type": R})
    assert not _ck.same_claim(
        {"claim": "본격 시행에서는 인증서를 제출해야 한다", "claim_type": R},
        {"claim": "전환기간에는 보고 의무가 적용된다", "claim_type": R})

    try:
        a = row("c01", "전환기간에는 CBAM 대상 수입품의 정보를 보고하는 의무가 적용되었다.")
        _ck.run(a, {"c01": src()}, "t")
        assert n[0] == 1 and a[0]["status"] == "supported", (n[0], a[0])

        # 표현만 바뀐 같은 명제 → 다시 안 묻는다
        b = row("c01", "CBAM 전환기간에는 대상 수입품의 정보를 보고하는 의무가 적용된다.")
        _ck.run(b, {"c01": src()}, "t")
        assert n[0] == 1, "표현이 바뀌었다고 다시 대조한다"
        assert b[0]["sources"][0]["cached"] and b[0]["status"] == "supported"

        # 다른 명제 → 새로 대조한다
        c = row("c02", "본격 시행에서는 인증서를 구매해 제출해야 한다.")
        _ck.run(c, {"c02": src()}, "t")
        assert n[0] == 2, "다른 명제를 캐시로 때운다"

        # 본문이 바뀌면 다시 대조한다 — 주소가 같아도 글이 바뀔 수 있다.
        # (인용이 원문에 없으니 재시도가 한 번 더 돈다)
        was = n[0]
        d = row("c01", "전환기간에는 CBAM 대상 수입품의 정보를 보고하는 의무가 적용되었다.")
        other = src(); other[0]["text"] = "완전히 다른 원문이라 겹치는 낱말이 없다."
        _ck.run(d, {"c01": other}, "t")
        assert n[0] > was, "본문이 바뀌었는데 옛 판정을 쓴다"
        assert not d[0]["sources"][0].get("cached")

        # 다른 드래프트의 판정을 물고 오지 않는다
        was = n[0]
        e = row("c01", "전환기간에는 CBAM 대상 수입품의 정보를 보고하는 의무가 적용되었다.")
        _ck.run(e, {"c01": src()}, "다른드래프트")
        assert n[0] > was, "남의 드래프트 판정을 쓴다"
    finally:
        llm.generate, llm.ENABLED = old_gen, old_en
        _ck._SEEN.clear(); _ck._SEEN.update(old_seen); _ck._KEYS.clear()
check("표현이 바뀐 명제를 다시 대조하지 않는다", _check_cache_survives_rewording)

def _cache_skips_failures():
    """실패한 판정은 담지 않는다. 다음번엔 될 수도 있다."""
    from backend.steps.evidence import check as _ck
    assert set(_ck.REUSABLE) == {"supported", "partial", "contradicted", "unverified"}
    for bad in ("check_limit_exceeded", "invalid_check", "fetch_failed"):
        assert bad not in _ck.REUSABLE, bad
    # 판정기가 바뀌면 옛 결과를 안 쓴다
    assert isinstance(_ck.VERSION, int)
check("실패한 판정은 캐시하지 않는다", _cache_skips_failures)

check("대조는 성공도 자취에 남는다", _check_logs_success)

def _actual_not_requested():
    """원한 성격과 걸린 성격을 나눠 든다.

    공식 원문을 노린 질의에서 언론 기사가 나오는 일이 흔하다. 예전에는 그
    기사에도 official_primary 가 붙어서 우선순위 정렬이 무의미했다.
    """
    from backend.data import sources as _sc
    assert _sc.classify("https://eur-lex.europa.eu/x") == "official_primary"
    assert _sc.classify("https://taxation-customs.ec.europa.eu/y") == "official_primary"
    assert _sc.classify("https://www.law.go.kr/z") == "domestic_official"
    # 모르는 곳을 공식으로 올리지 않는다
    assert _sc.classify("https://www.impacton.net/news/1") == "secondary"
    assert _sc.classify("무효한주소") == "secondary"
    # 하위 도메인 흉내를 못 낸다
    assert _sc.classify("https://europa.eu.evil.com/x") == "secondary"
    # 정렬은 actual 로 한다
    a = {"actual_target": "secondary", "score": 0.99}
    b = {"actual_target": "official_primary", "score": 0.1}
    assert sorted([a, b], key=_po.rank)[0] is b
check("실제로 걸린 출처를 도메인으로 가른다", _actual_not_requested)

def _authority_axis():
    """의미 대응과 출처 자격은 다른 축이다.

    하나로 접으면(규정은 공식 원문 아니면 미확인) 공식 원문을 못 찾은 날
    본문이 아무것도 단정 못 하고 근거 없는 글이 나온다. 상태는 살리고
    표현 강도만 낮춘다.
    """
    assert _po.authority_of("regulation", ["official_primary"]) == "sufficient"
    assert _po.authority_of("regulation", ["secondary"]) == "insufficient"
    assert _po.authority_of("regulation", ["domestic_official"]) == "limited"
    assert _po.authority_of("fact", ["secondary"]) == "insufficient"
    assert _po.authority_of("inference", ["secondary"]) == "sufficient"
    # 자격이 모자라도 인용은 한다. 막으면 근거 없는 글이 된다.
    assert _po.citable({"status": "supported", "authority": "insufficient"})
check("자격은 인용을 막지 않고 표현을 낮춘다", _authority_axis)

def _windows_keep_tail():
    """앞부분만 잘라 넘기지 않는다.

    법령 원문은 길다. 앞 12,000자만 보면 필요한 조항이 뒤에 있을 때
    insufficient 가 나오고 짧은 기사만 근거로 남는다.
    """
    from backend.steps.evidence import search as _se
    long = ("배경 " * 900) + " Article 40 Verification requirements apply. " + ("부록 " * 3000)
    got = _se._windows(long, "CBAM verification requirements")
    assert "Article 40 Verification" in got, "필요한 조항을 놓쳤다"
    assert len(got) < len(long) / 2, len(got)
    # 질의가 비면 앞부분으로 떨어진다. 지금보다 나빠지지 않는다.
    assert len(_se._windows(long, "")) == _se.WINDOW * _se.MAX_WINDOWS
check("웹 원문은 관련 구간만 넘긴다", _windows_keep_tail)

check("올린 문서는 명제에 걸린 것만 대조한다", lambda: (
    _po.MAX_PDF_CHECKS < _po.MAX_CHECKS
    and _po.MAX_DOCUMENT_CLAIMS == 2
    and "document_links" in _md("plan")) or 1/0)

check("규정을 기사로 뒷받침하지 말라고 적혀 있다", lambda: (
    "첫 질의의 `source_target` 은 반드시 `official_primary`" in _md("plan")
    and "그 기사는 법령이 아닙니다" in _md("plan")) or 1/0)

check("searchable 이 참을 뜻하지 않는다고 적혀 있다", lambda: (
    "그 명제가 참이라는 뜻이 아닙니다" in _md("claims")
    and "원문이 있으므로 참입니다" not in _md("claims")) or 1/0)

def _body_separates_official():
    """공식 요구사항과 실무 권고를 섞지 말라는 규칙이 있다."""
    md = _md("_write")
    for want in ("authority", "보도에 따르면", "별도 문단",
                 "권고로 씁니다", "`insufficient`"):
        assert want in md, want
check("본문이 규정과 권고를 가른다", _body_separates_official)

def _weak_authority_flagged():
    """자격이 모자란 출처로 규정을 서술했으면 확인 목록에 뜬다.

    코드가 문장을 못 읽으므로 막지 않고 어디를 볼지만 짚는다. 막으면
    근거 없는 글이 나온다 — 그 판단은 policy.citable() 에 있다.
    """
    from backend.output import checklist as _cl2
    w = {"sections": [{"cites": ["s0"]}, {"cites": ["s2"]}],
         "sources": [
            {"id": "s0", "claim_type": "regulation", "authority": "insufficient",
             "title": "수입자가 정보를 확보해야 한다"},
            {"id": "s1", "claim_type": "regulation", "authority": "insufficient",
             "title": "인용 안 한 것"},
            {"id": "s2", "claim_type": "inference", "authority": "insufficient",
             "title": "추론은 원래 그렇다"}]}
    out = []
    _cl2._authority(out, {}, w)
    assert len(out) == 1 and "1건" in out[0]["text"], out
    # 안 쓴 것과 추론은 안 센다
    assert "인용 안 한 것" not in out[0]["note"], out
check("자격 모자란 서술을 확인 목록에 올린다", _weak_authority_flagged)

check("자격이 본문 프롬프트까지 간다", lambda: (
    "authority" in _wr._claim_row(
        {"claim_id": "c1", "claim": "x", "status": "supported",
         "authority": "insufficient", "claim_type": "regulation",
         "sources": [{"status": "supported", "title": "t", "url": "u",
                      "evidence_spans": [], "limitations": []}]}, [], [])) or 1/0)

def _evidence_summary_row():
    """근거 단계가 통째로 무엇을 했는지 한 줄로 남는다.

    지금은 claims · plan · search · check 를 명제마다 뒤져야 안다.
    "검색이 돌았나 · 몇 건 걸렸나 · 왜 미확인인가" 는 자주 묻는 것이다.
    """
    from backend.steps.evidence import search as _se3
    from backend.steps import evidence as _ev2
    old_gen, old_en = llm.generate, _se3.api.ENABLED
    FK = {"claims": {"claims": [
            {"claim": "규정 명제", "claim_type": "regulation",
             "required_source": "원문", "searchable": True, "why": "w"},
            {"claim": "추론 명제", "claim_type": "inference",
             "required_source": "사례", "searchable": False, "why": "w"}]},
          "plan": {"plans": [], "document_links": []}}
    llm.generate = lambda n, p, strong=False: FK[n]
    _se3.api.ENABLED = False
    try:
        d = {"_sid": "evsum", "topic": {"label": "t", "payload": {}},
             "intent": {"payload": {"question": "q", "sub_questions": []}},
             "angle": {"payload": {}}, "type": {"payload": {}},
             "reader": {"payload": {}}}
        _ev2.verified(d, _ev2.build_input(d), "evsum")
    finally:
        llm.generate, _se3.api.ENABLED = old_gen, old_en

    rows = history.find(sid="evsum", step="evidence", full=True)["rows"]
    assert rows, "요약 행이 없다"
    raw = json.loads(rows[-1]["raw"])
    assert "상태별" in raw and raw["상태별"]["search_disabled"] == 1, raw
    metas = [o["meta"] for o in rows[-1]["options"]]
    assert all("·" in m for m in metas), metas   # 상태 · 자격
check("근거 단계 요약이 한 줄로 남는다", _evidence_summary_row)

def _enabled_not_copied():
    """검색 가능 여부를 상수로 복사해 두지 않는다.

    `ENABLED = api.ENABLED` 로 두면 import 시점 값이 굳는다. 그 뒤에 키가
    들어와도 이쪽은 옛 값을 든 채로 남고, 두 곳이 다른 답을 내면서 오류는
    안 난다.
    """
    from backend.steps.evidence import search as _se2
    # 모듈에 상수가 남아 있으면 그게 굳은 값이다. 문자열로 세면 이
    # 검사 자신의 설명에 걸린다.
    assert not hasattr(_se2, "ENABLED"), "import 시점 값을 굳혔다"
    assert callable(_se2.enabled), "enabled 가 함수가 아니다"
    old = _se2.api.ENABLED
    try:
        _se2.api.ENABLED = True
        assert _se2.enabled() is True
        _se2.api.ENABLED = False
        assert _se2.enabled() is False
    finally:
        _se2.api.ENABLED = old
check("검색 가능 여부를 실행 시점에 본다", _enabled_not_copied)

def _off_is_not_notfound():
    """"안 찾아봤다" 와 "찾았는데 없다" 를 가른다.

    뭉치면 원인을 고칠 수 없다 — 키를 안 넣은 것인지 자료가 없는 것인지가
    화면에서 똑같이 보인다. 그리고 **안 찾아본 것은 고를 수 있어야 한다.**
    안 그러면 키가 없는 날 고를 근거가 하나도 없어 사람이 막힌다.
    """
    for rc in ("search_disabled", "check_limit_exceeded"):
        c = {"status": "unverified", "claim_type": "regulation", "reason_code": rc}
        assert _po.selectable(c), f"{rc} 인데 못 고른다"
        assert not _po.citable(c), f"{rc} 인데 인용된다"
    for rc in ("no_search_result", "fetch_failed", "no_source"):
        c = {"status": "unverified", "claim_type": "regulation", "reason_code": rc}
        assert not _po.selectable(c), f"{rc} 인데 고를 수 있다"
    assert "search_disabled" in _po.REASONS and "no_search_result" in _po.REASONS
check("안 찾아본 것과 못 찾은 것을 가른다", _off_is_not_notfound)

def _selectable_is_a_value():
    """고를 수 있는지를 값으로 내려보낸다.

    예전에는 메타에 "고를 수 없음" 이라는 글자만 있었다. 화면이 그 글자를
    읽을 수 없으니 상태를 보고 다시 판단했고, 그러면 정책이 두 곳에 생긴다.
    """
    from backend.steps.step import opt as _opt
    assert _opt("i", "t", "s", "m", {}, selectable=False)["selectable"] is False
    assert "selectable" not in _opt("i", "t", "s", "m", {})
    # 확정도 같은 값을 본다. 화면만 막으면 주소를 직접 쳐서 넘길 수 있다.
    src = (paths.BACKEND / "session.py").read_text(encoding="utf-8")
    assert 'opts[c].get("selectable", True)' in src, "확정이 안 막는다"
    js = _js("pages/step.js")
    assert "selectable: o.selectable" in js, "화면에 값이 안 간다"
    assert "o.selectable === false" in _js("ui.js"), "화면이 값을 안 읽는다"
check("고를 수 있는지를 값으로 내려보낸다", _selectable_is_a_value)

def _article_fetched_directly():
    """소재 기사는 검색과 별개로 바로 가져온다.

    예전에는 주소만 넣어 두고 검색이 같은 URL 을 우연히 다시 찾기를
    기다렸다 — 거의 안 채워지고 fetch_failed 로 남았다.
    """
    from backend.external import search as _api
    src = (paths.BACKEND / "steps" / "evidence" / "__init__.py").read_text(encoding="utf-8")
    assert "plain_fetch" in src, "기사를 직접 안 가져온다"
    assert callable(_api.plain_fetch)
    # 키 없이 도는 경로다
    fn = __import__("inspect").getsource(_api.plain_fetch)
    assert "api_key" not in fn.lower() and "_post(" not in fn, "키가 필요한 경로다"
check("소재 기사를 검색 없이 가져온다", _article_fetched_directly)

def _search_off_is_told():
    """검색이 꺼졌다는 것을 발행 전에 알린다."""
    from backend.output import checklist as _ck4
    out = []
    _ck4._evidence_gap(out, {"evidence": {"payload": {"items": [
        {"claim_id": "c01", "status": "unverified", "reason_code": "search_disabled"}]}}})
    kinds = [x["kind"] for x in out]
    assert "근거 검색 꺼짐" in kinds and "인용할 근거 없음" in kinds, out
    out2 = []
    _ck4._evidence_gap(out2, {"evidence": {"payload": {"items": [
        {"claim_id": "c01", "status": "supported"}]}}})
    assert out2 == [], out2
check("검색이 꺼진 것을 발행 전에 알린다", _search_off_is_told)

def _zero_evidence_is_told():
    """인용할 근거가 0건이면 본문이 그것을 안다.

    빈 목록만으로는 모델이 "안 준 것" 과 "없는 것" 을 구별 못 한다. 실제로
    빈 자리를 스스로 정의로 메웠다 — "공시 데이터 체계는 ~하는 구조입니다"
    같은 문장이 입력 어디에도 없이 나왔다.
    """
    d = {"evidence": {"payload": {"items": [
            {"claim_id": "c01", "claim": "x", "status": "unverified",
             "claim_type": "regulation", "sources": []}]}},
         "outline": {"payload": {"sections": []}}, "type": {"payload": {}},
         "reader": {"payload": {}}, "angle": {"payload": {}},
         "intent": {"payload": {}}, "topic": {"label": "t", "payload": {}},
         "title": {"payload": {}}, "channel": {"payload": {"channel": "naver"}}}
    st = _wr.build_input(d)["evidence_state"]
    assert st == {"citable": 0, "unverified": 1, "can_assert": False}, st
    md = _md("_write")
    assert "can_assert` 가 거짓이면" in md and "빈 자리를 스스로 메우는 것" in md
    assert "정의로 시작하지 않습니다" in md, "빈 claim_refs 규칙이 없다"
check("근거 0건을 본문이 안다", _zero_evidence_is_told)

def _ready_summary():
    """발행 가능 상태를 한 줄로 준다.

    확인 목록이 길면 사람이 안 읽고 발행한다. 그게 실제로 났던 실패다.
    막지는 않는다 — 근거 없이도 내야 할 때가 있다.
    """
    from backend.output import checklist as _ck5
    bad = _ck5.ready({"evidence": {"payload": {"items": [
        {"claim_id": "c01", "status": "unverified"}]}}},
        [{"kind": "인용할 근거 없음", "text": "출처를 달 수 있는 근거가 없습니다"}])
    assert bad["ok"] is False and bad["cited"] == 0 and bad["why"], bad
    ok = _ck5.ready({"evidence": {"payload": {"items": [
        {"claim_id": "c01", "status": "supported"}]}}}, [{"kind": "이미지 확인", "text": "x"}])
    assert ok["ok"] is True and ok["cited"] == 1, ok
    assert "readyBar(R)" in _js("pages/result.js"), "화면에 안 뜬다"
check("발행 가능 상태를 한 줄로 알린다", _ready_summary)

def _title_lowers_promise():
    """근거가 없으면 제목이 약속을 낮춘다.

    본문이 사실을 단정 못 하는데 제목이 "왜 어긋나는가" 를 걸면 본문이
    그 답을 못 준다 — 제목이 약속한 것을 본문이 못 주면 그 제목이 틀렸다.
    """
    d = {"topic": {"label": "t", "payload": {}}, "reader": {"payload": {}},
         "intent": {"payload": {}}, "angle": {"payload": {}},
         "type": {"payload": {}}, "channel": {"payload": {"channel": "site"}},
         "outline": {"payload": {"sections": [{"title": "가", "claim_refs": ["c01"]}]}},
         "evidence": {"payload": {"items": [
             {"claim_id": "c01", "claim": "x", "status": "unverified", "sources": []}]}}}
    assert _tt.build_input(d)["evidence_state"]["can_assert"] is False
    d["evidence"]["payload"]["items"][0]["status"] = "supported"
    assert _tt.build_input(d)["evidence_state"]["can_assert"] is True
    md = _md("_prompt", "title")
    assert "약속을 낮춥니다" in md and "쓰지 않는다" in md
    # 자동 치환은 안 한다. 문자열을 바꾸면 제목이 망가진다.
    src = (paths.BACKEND / "steps" / "title" / "__init__.py").read_text(encoding="utf-8")
    assert "replace(\"이유\"" not in src, "제목을 문자열로 고친다"
check("근거가 없으면 제목이 약속을 낮춘다", _title_lowers_promise)

def _recipe_from_body():
    """편집 안내를 본문 모양에서 만든다.

    본문 데이터에 정렬·간격을 넣지 않는다. 붙여넣기에서 대부분 안
    살아남고, 모델이 문단마다 정하면 장식이 과해진다.
    """
    from backend.output.naver import render as _nr
    d = {"write": {"lead": "리드", "sections": [{"heading": "가", "order": 1, "blocks": [
            {"type": "para", "text": "p"},
            {"type": "callout", "label": "주의", "text": "c"}]}]},
         "outline": {"payload": {"sections": [{"title": "가", "media": None}]}}}
    rows = _nr._recipe(d)
    where = [r["where"] for r in rows]
    assert "도입" in where and "소제목" in where and "강조 문단" in where, where
    assert all(set(r) == {"where", "what", "why"} for r in rows), rows
    # 본문 블록에 정렬·간격이 들어가지 않는다
    src = (paths.BACKEND / "output" / "write.py").read_text(encoding="utf-8")
    assert "align" not in src and "spacing" not in src, "본문에 서식이 섞였다"
    assert "recipe(out.naver.recipe)" in _js("pages/result.js")
check("편집 안내를 본문 모양에서 만든다", _recipe_from_body)

def _cta_is_real():
    """cta_strength 를 실제로 읽는다.

    채널마다 값을 정해 두고 **아무도 안 읽던 자리**였다. 결과물에는
    `<!-- CTA_SLOT -->` 주석 한 줄뿐이라 글이 "그래서 뭘 하면 되나" 없이
    끝났다. hero_ratio 와 같은 패턴이다.
    """
    from backend.data import company as _co2
    old = dict(_co2.SERVICES)
    try:
        _co2.SERVICES["svc_01"] = {"name": "CBAM 대응",
                                   "url": "https://example.com/cbam", "summary": "s"}
        d = {"channel": {"payload": {"channel": "site"}},
             "title": {"payload": {"title": "t"}}, "reader": {"payload": {}},
             "type": {"payload": {}},
             "topic": {"label": "x", "payload": {"service_id": "svc_01"}},
             "write": {"lead": "리드", "sections": [
                 {"heading": "가", "order": 1,
                  "blocks": [{"type": "para", "text": "문단"}]}]}}
        site = _r.build(d)["site"]["html"]
        # class 이름은 CSS 규칙에도 있다. 실제 요소가 나갔는지를 본다.
        assert '<aside class="post-cta">' in site, "CTA 가 안 나간다"
        assert "example.com/cbam" in site, "링크가 안 붙었다"
        assert "CTA_SLOT" not in site, "주석 자리가 남아 있다"

        d["channel"]["payload"]["channel"] = "naver"
        nav = _r.build(d)["naver"]["html"]
        assert "CBAM 대응" in nav, "네이버에 안내가 안 나간다"
        assert "post-cta-a" not in nav, "네이버에 버튼이 나갔다"

        # **서비스를 모르면 아예 안 나간다.** 작성자 이름과 같은 원칙이다.
        d["topic"]["payload"]["service_id"] = "없는것"
        d["channel"]["payload"]["channel"] = "site"
        assert '<aside class="post-cta">' not in _r.build(d)["site"]["html"], \
            "없는 서비스를 권한다"
    finally:
        _co2.SERVICES.clear(); _co2.SERVICES.update(old)
check("글 끝의 안내가 실제로 나간다", _cta_is_real)

def _cta_copy_is_ours():
    """안내 문구를 모델이 만들지 않는다.

    매번 다르게 지어내면 글마다 다른 회사처럼 보이고, 없는 서비스를 권한다.
    """
    from backend.data import company as _co3
    assert set(_co3.CTA) == {"soft", "medium", "strong"}, sorted(_co3.CTA)
    assert _co3.cta("medium", None) is None, "서비스 없이 문구가 나온다"
    for md in ("site_write", "naver_write"):
        assert "후속 코드가" in _md(md), f"{md} 가 CTA 를 만들 수 있다"
check("안내 문구는 회사가 정한다", _cta_copy_is_ours)

def _service_gap_told():
    """서비스 연결이 없으면 알린다."""
    from backend.output import checklist as _ck6
    out = []
    _ck6._service_link(out, {"topic": {"payload": {}}}, "site")
    assert out and "서비스 연결 없음" == out[0]["kind"], out
    out2 = []
    _ck6._service_link(out2, {"topic": {"payload": {"service_id": "svc_99"}}}, "site")
    assert "svc_99" in out2[0]["note"], out2
check("서비스 연결이 없으면 알린다", _service_gap_told)

def _paste_promise_is_honest():
    """붙여넣기 결과를 확언하지 않는다.

    네이버는 외부 글을 그대로 붙여넣는 것을 권장하지 않는다. "그대로
    따라갑니다" 는 지킬 수 없는 약속이고, 안 따라왔을 때 사람이 자기가
    잘못한 줄 안다.
    """
    js = _js("pages/result.js")
    assert "그대로 따라갑니다" not in js, "지킬 수 없는 약속이 남아 있다"
    assert "붙여넣은 뒤에는 서식을 확인해 주세요" in js
    assert "권장하지 않습니다" in js
check("붙여넣기 결과를 확언하지 않는다", _paste_promise_is_honest)

check("판정은 policy 한 곳이 정한다", lambda: (
    _confirmed({"claim_id": "c1", "status": "partial"})
    and not _confirmed({"claim_id": "c1", "status": "unverified",
                        "claim_type": "inference"})) or 1/0)


print("\n── 추천 표시 ──")

def _pick_on_first_only():
    """추천이 첫 후보에만 붙는다.

    프롬프트가 이미 "가장 맞는 것을 첫 번째로" 라고 정해 두었다. 순서에
    뜻이 있는데 화면에는 안 보이던 자리다 — 유형만 추천이 있었다.
    """
    for key in ("reader", "intent", "angle", "outline", "title"):
        opts = cu.get(f"/api/draft/{key}").json().get("options") or []
        if not opts:
            continue
        assert opts[0]["meta"].startswith("추천 · "), (key, opts[0]["meta"])
        for o in opts[1:]:
            assert not o["meta"].startswith("추천 · "), (key, o["meta"])
check("추천이 첫 후보에만 붙는다", _pick_on_first_only)

def _pick_has_a_reason():
    """왜 추천인지가 함께 나온다.

    이유가 없으면 "그냥 첫 번째" 라는 뜻이고, 사람은 그걸로 판단할 수 없다.
    이유는 각 단계가 이미 들고 있다 — differentiation · rationale.
    """
    from backend.steps.step import pick_meta as _pm
    # pick_meta(메타, 이유) — 이유가 앞에 온다. 사람이 먼저 읽는 것이 이유다.
    assert _pm("톤 실무적", "무엇을 먼저 짚는가") == "추천 · 무엇을 먼저 짚는가 · 톤 실무적"
    assert _pm("톤 실무적") == "추천 · 톤 실무적"
    assert _pm("") == "추천"
check("추천에 이유가 붙는다", _pick_has_a_reason)

def _volume_floor_by_type_and_channel():
    """유형·채널마다 담아야 할 최소치가 있다.

    **글자 수만 세면 반복이 는다.** 같은 말을 늘려 써도 넘기 때문이다.
    섹션 수 · 서로 다른 내용 · 쓴 명제를 함께 본다. 실제로 근거가 열
    묶음인데 셋만 쓰고 900자로 끝난 글이 나왔다.
    """
    from backend.data import skeletons as _sk3
    from backend.steps.outline.payload import (payload as _op3, volume as _vol,
                                               distinct_covers as _dc)
    # 홈페이지는 정의·근거·해석·서비스까지 담으므로 한 칸씩 더 든다
    n, s_ = _sk3.need("정보형", "naver"), _sk3.need("정보형", "site")
    assert s_["sections"] > n["sections"] and s_["chars"][0] > n["chars"][0]
    # 가이드형이 정보형보다 길다
    assert _sk3.need("가이드형", "naver")["sections"] > n["sections"]
    # 모르는 유형은 정보형으로 둔다
    assert _sk3.need("없는유형", "naver") == n

    # **같은 것을 표현만 바꿔 두 번 쓰면 하나로 센다.**
    p3 = _op3([{"title": "가", "covers": ["무엇인지 정의", "누가 신고하는지"]},
               {"title": "나", "covers": ["정의가 무엇인지"]}])
    assert _dc(p3) == 2, _dc(p3)

    v = _vol(p3, "정보형", "naver")
    assert v["short"]["sections"] == (2, 4), v["short"]
    assert v["short"]["claims"][0] == 0, v["short"]
check("유형·채널마다 담을 최소치가 있다", _volume_floor_by_type_and_channel)

def _volume_told():
    """일찍 끝난 글을 발행 전에 알린다. 도식 안 글자는 안 센다."""
    from backend.output import checklist as _ck14
    d = {"type": {"payload": {"article_type": "정보형"}},
         "outline": {"payload": {"sections": [
             {"title": "가", "covers": ["정의"], "claim_refs": ["c01"]}]}},
         "write": {"lead": "짧은 리드", "sections": [
             {"heading": "가", "blocks": [
                 {"type": "para", "text": "문단"},
                 # 표 하나로 하한을 넘기면 안 된다
                 {"type": "figure", "component": "대조표", "caption": "c",
                  "takeaway": "t", "data": {"columns": ["A" * 900], "rows": []}}]}]}}
    out = []
    _ck14._volume(out, d, "naver")
    kinds = [x["kind"] for x in out]
    # **근거 부족은 따로 알린다.** 구조를 바꿔도 안 풀리는 문제다.
    assert "근거가 적다" in kinds and "담은 것이 적다" in kinds, kinds
    body = next(x for x in out if x["kind"] == "담은 것이 적다")
    assert "본문 글자" in body["note"], body["note"]
    assert "근거" not in body["note"], "구조 문제에 근거가 섞였다"
    assert _ck14._body_chars(d) < 100, "도식 안 글자를 셌다"
check("일찍 끝난 글을 발행 전에 알린다", _volume_told)

def _pick_on_five_steps():
    """다섯 단계 첫 후보에 추천이 붙는다.

    유형만 추천이 있었고 나머지는 프롬프트에 "첫 번째를 ~로 두라" 가
    있어도 **화면에 안 보였다.** 순서에 둔 뜻이 사라진 상태였다.

    근거는 뺀다 — 여러 개 고르는 자리라 추천이 붙으면 그것만 고르고
    나머지를 안 본다.
    """
    old = llm.ENABLED
    llm.ENABLED = False
    try:
        d = {"topic": {"label": "CBAM", "payload": {}},
             "reader": {"payload": {"role": "담당자"}},
             "intent": {"payload": {"question": "q", "sub_questions": []}},
             "angle": {"payload": {}}, "type": {"payload": {}},
             "channel": {"payload": {"channel": "site"}},
             "outline": {"payload": {"sections": []}}, "evidence": {"payload": {}}}
        for name, mod in (("reader", _rd), ("intent", _in), ("angle", _ag)):
            rows = mod.make(d, mod.build_input(d))
            assert rows[0]["meta"].startswith("추천 · "), (name, rows[0]["meta"])
            assert not any(r["meta"].startswith("추천") for r in rows[1:]), name
            # "추천" 만 있고 이유가 없으면 그냥 첫 번째라는 뜻이다
            assert len(rows[0]["meta"]) > 10, (name, rows[0]["meta"])
    finally:
        llm.ENABLED = old
check("독자·검색의도·각도 첫 후보가 추천이다", _pick_on_five_steps)

def _no_pick_on_evidence():
    """근거에는 추천을 안 붙인다.

    여러 개 고르는 유일한 단계다. 추천이 붙으면 그것만 고르고 나머지를
    안 본다 — 근거는 나란히 놓고 견주는 자리다.
    """
    src = (paths.BACKEND / "steps" / "evidence" / "__init__.py").read_text(encoding="utf-8")
    assert "pick_meta" not in src, "근거에 추천이 붙었다"
    assert _st.BY_KEY["evidence"].multi, "근거는 여러 개 고르는 단계다"
check("근거에는 추천을 안 붙인다", _no_pick_on_evidence)

check("화면이 추천 카드를 구별한다", lambda: (
    "pick: (o.meta" in _js("pages/step.js")
    and "o.pick ? ' pick'" in _js("ui.js")) or 1/0)

def _reason_shows_once():
    """이유가 한 줄에 두 번 안 나온다.

    추천 말머리에 이유를 넣고 메타 끝에도 두면 같은 문장이 겹친다.
    실제로 검색의도에서 그렇게 났다.
    """
    for key in ("reader", "intent", "angle", "outline", "title"):
        opts = cu.get(f"/api/draft/{key}").json().get("options") or []
        if not opts:
            continue
        head = opts[0]["meta"][len("추천 · "):].split(" · ")[0]
        assert head and opts[0]["meta"].count(head) == 1, (key, opts[0]["meta"])
check("추천 이유가 한 번만 보인다", _reason_shows_once)

def _no_pick_where_it_hurts():
    """추천이 없어야 하는 자리에는 없다.

    근거는 **여러 개 고르는 자리**다. 하나에 추천이 붙으면 그것만 고르고
    나머지를 안 본다. 소재는 이미 점수로 줄 세워져 있고, 채널은 둘뿐이다.
    """
    for key in ("evidence",):
        opts = cu.get(f"/api/draft/{key}").json().get("options") or []
        assert not any(o["meta"].startswith("추천 · ") for o in opts), key
    assert _st.BY_KEY["evidence"].multi, "근거는 여러 개 고르는 단계다"
check("여러 개 고르는 단계엔 추천이 없다", _no_pick_where_it_hurts)

check("화면이 추천을 말머리로만 본다", lambda: (
    "'추천 · '" in _js("ui.js") and "b class=\"pick\"" in _js("ui.js")) or 1/0)


print("\n── 채널 규칙과 결과물 ──")

from backend.data import company as _co, brand as _br

def _channels_are_code_only():
    """channels.py 에는 코드가 읽는 값만 둔다.

    모델용 지침(guidance·capabilities·avoid)을 여기 두었더니 읽는 곳이 본문
    하나뿐이었고 구조·제목은 채널을 아예 몰랐다 — **데이터는 있고 아무도 안
    읽는 상태.** 지침은 채널 프롬프트로 옮겼다.
    """
    import dataclasses
    fields = {f.name for f in dataclasses.fields(_cn.ChannelPolicy)}
    # 모델이 읽을 문장은 하나도 없다
    assert not (fields & {"guidance", "capabilities", "avoid"}), fields
    for ch in _cn.NAMES:
        p = _cn.of(ch)
        assert isinstance(p, _cn.ChannelPolicy) and p.name, ch
check("채널 데이터에 모델용 지침이 없다", _channels_are_code_only)

def _floor_not_forced():
    """하한을 코드가 강제하지 않는다. 강제하면 모델이 수를 채운다."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(_cn.ChannelPolicy)}
    assert not any(k.startswith("min_") for k in fields), fields
    # 프롬프트는 권장으로만 적는다
    assert "더 적게" in _md("site_outline") and "더 적게" in _md("naver_outline")
check("하한은 권장이고 상한만 강제한다", _floor_not_forced)

def _one_channel_of():
    """채널 판별이 한 곳이다.

    예전에는 넷이 각자 했다 — steps 순서, 본문 프롬프트, 대표 이미지,
    결과물 조립. 우연히 같은 답을 내고 있었을 뿐이다.
    """
    # 외부 명령을 부르지 않는다. grep 은 윈도우에 없다.
    where = sorted(
        f.relative_to(paths.BACKEND).as_posix()
        for f in paths.BACKEND.rglob("*.py")
        if "__pycache__" not in f.parts
        and "def channel_of" in f.read_text(encoding="utf-8"))
    # data/channels.py 가 본체, steps 는 "아직 안 정함" 을 구별해야 해서 따로.
    assert where == ["data/channels.py", "steps/__init__.py"], where
    d = {"channel": {"payload": {"channel": "naver"}}}
    assert _cn.channel_of(d) == "naver"
    assert _cn.channel_of({"channel": {"payload": {"channel": "x"}}}) == "site"
    assert _cn.channel_of({}) == "site"
    # 순서를 정하는 쪽은 "아직 안 정함" 을 빈 문자열로 남긴다
    assert _st.channel_of({}) == "" and _st.channel_of(d) == "naver"
check("채널 판별이 한 곳이다", _one_channel_of)

def _labels_one_place():
    """같은 것을 두 이름으로 부르지 않는다.

    한때 output 은 "자료 화면", 구조 payload 는 "캡처" 로 불렀다.
    """
    assert _cn.label("naver", "capture") == "자료 화면"
    assert _cn.label("naver", "photo") == "실제 사진"
    # 홈페이지는 사진을 안 쓴다
    assert not _cn.of("site").media_allowed
    src = (paths.BACKEND / "output" / "common.py").read_text(encoding="utf-8")
    assert "MEDIA_LABELS" not in src, "전역 라벨이 남아 있다"
check("시각 요소 이름이 한 곳이다", _labels_one_place)

check("hero 비율이 실제로 쓰인다", lambda: (
    _cn.of("site").hero_ratio == "wide" and _cn.of("naver").hero_ratio == "1:1"
    and "ratio" in (paths.BACKEND / "output" / "hero.py").read_text(encoding="utf-8")) or 1/0)

check("태그는 제목에서 온다", lambda: (
    "import fake" not in
    (paths.BACKEND / "output" / "common.py").read_text(encoding="utf-8")) or 1/0)

check("네이버가 홈페이지보다 짧다", lambda: (
    _cn.of("naver").max_sections < _cn.of("site").max_sections) or 1/0)

def _prompts_layered():
    """채널 프롬프트를 통째로 복제하지 않는다.

    본문 프롬프트는 370줄인데 채널 차이는 문단 길이·말투·도입부 정도다.
    복제하면 한쪽만 고쳐지고 그 어긋남은 조용히 지나간다.
    """
    from backend import prompt as _pr
    for ch in _cn.NAMES:
        assert _pr.BASE[f"{ch}_write"].stem == "_write", ch
        assert _pr.BASE[f"{ch}_hero"].stem == "_hero", ch
    # 밑바탕이 실제로 앞에 깔린다
    built = _pr.build("naver_write")
    assert "limits 를 어떻게 읽나" in built, "밑바탕이 안 깔렸다"
    assert "네이버 블로그에 실립니다" in built, "채널 델타가 안 붙었다"
    assert built.index("limits 를 어떻게 읽나") < built.index("네이버 블로그에 실립니다")
check("본문 프롬프트는 밑바탕 위에 얹는다", _prompts_layered)

def _channel_prompt_picked():
    from backend.output import write as _w
    assert _w.prompt_of("naver") == "naver_write"
    assert _w.prompt_of("없는채널") == "site_write"
    inp = _w.build_input(as_channel({"topic": {"label": "x", "payload": {}}}, "naver"))
    assert inp["channel"] == "네이버 블로그", inp["channel"]
    assert inp["limits"]["max_sections"] == 5, inp["limits"]
check("본문이 채널 규칙을 주입받는다", _channel_prompt_picked)

def _no_channel_branch():
    """write.py 에 채널 이름으로 가르는 분기를 두지 않는다."""
    src = (paths.BACKEND / "output" / "write.py").read_text(encoding="utf-8")
    for bad in ('== "naver"', "== 'naver'", 'if ch == "site"'):
        assert bad not in src, bad
check("본문 코드에 채널 분기가 없다", _no_channel_branch)

def _renderers_isolated():
    """두 렌더러가 서로를 import 하지 않는다.

    한쪽이 다른 쪽을 부르면 네이버가 홈페이지의 파생물이 되어 채널을 가른
    뜻이 없어진다. 공유는 common.py 를 통해서만.
    """
    out = paths.BACKEND / "output"
    site = (out / "site" / "render.py").read_text(encoding="utf-8")
    nav = (out / "naver" / "render.py").read_text(encoding="utf-8")
    assert "naver" not in site.split('"""', 2)[2], "site 가 naver 를 안다"
    assert "from ..site" not in nav and "site import" not in nav, "naver 가 site 를 안다"
check("두 렌더러가 서로를 모른다", _renderers_isolated)

def _trust_hidden_when_empty():
    """작성자가 없으면 지어내지 않고 영역째 뺀다."""
    assert not _co.AUTHORS and not _co.REVIEWERS, "테스트 전제가 깨졌다"
    assert _co.author() is None and _co.reviewer() is None
    html = _render(ALL, "site")["html"]
    assert "post-trust" in html and "기준</time>" in html, "기준일은 남아야 한다"
    assert "환경 전문가" not in html and "post-by" not in html, html[:400]
check("작성자가 없으면 지어내지 않는다", _trust_hidden_when_empty)

check("작성 주체 없음이 확인 목록에 뜬다", lambda: (
    "작성 주체 없음" in [x["kind"] for x in
                    _r.build(as_channel(ALL, "site"))["checklist"]]) or 1/0)

def _tree_has_connectors():
    """구조도에 상하위를 잇는 선이 있다.

    선이 없으면 상자 셋을 그냥 늘어놓은 것으로 보인다. 순서열에는 세로선이
    있는데(`.fig-steps::before`) 구조도에만 없었다.
    """
    css = _fg.CSS
    for k in (".fig-root::after", ".fig-branch::before", ".fig-node::before"):
        assert k in css, f"{k} 규칙이 없다"
    # 가지가 하나뿐이면 잇는 것이 없다
    assert ".fig-branch>.fig-node:only-child" in css
check("구조도에 연결선이 있다", _tree_has_connectors)

def _table_keeps_words():
    """표가 낱말 가운데서 안 끊긴다.

    실제 캡처에서 "우선 산 / 정", "남길 기 / 록" 으로 끊겼다. 한국어는
    keep-all 이 없으면 글자 단위로 줄이 바뀐다.
    """
    css = _fg.CSS
    assert "word-break:keep-all" in css and "table-layout:fixed" in css, css[:0]
    tb = [r for r in css.split("}") if ".fig-cmp tbody th{" in r][0]
    assert "nowrap" in tb, "기준 열이 끊긴다"
check("표가 낱말 단위로 줄바꿈한다", _table_keeps_words)

def _connectors_line_up():
    """세 선이 정확히 이어진다.

    좌표가 어긋나면 가운데에 짧은 꼬리가 보이거나 선이 끊겨 보인다.
    루트 아래 10px → 가로선 → 노드 위 10px 이 가지 margin-top 20px 의
    가운데에서 만나야 한다.
    """
    css = _fg.CSS
    assert "bottom:-10px" in css and "height:10px" in css, "루트 세로선"
    assert "margin-top:20px" in css, "가지 여백"
    assert "top:-10px" in css, "가로선·노드 세로선"
    # 가로선은 첫 가지 가운데에서 마지막 가지 가운데까지.
    assert "left:var(--edge" in css, "끝 위치를 렌더러가 안 준다"
    assert "left:12.5%" not in css, "고정 좌표가 남아 있다"

    # **gap 을 빼야 정확하다.** CSS 안에서는 gap 을 못 세므로 렌더러가
    # 계산한다. 안 빼면 2가지는 4px, 3가지는 5.3px 안쪽으로 들어간다.
    for n, width in ((2, 900), (3, 900), (4, 960)):
        gap = _fg.BRANCH_GAP
        node = (width - gap * (n - 1)) / n
        first_center = node / 2
        import re as _re3
        m = _re3.search(r"calc\(([\d.]+)% - ([\d.]+)px\)", _fg._edge(n))
        line_start = width * float(m.group(1)) / 100 - float(m.group(2))
        assert abs(first_center - line_start) < 0.01, (n, first_center, line_start)
    assert "--edge" not in _fg._edge(1), "가지가 하나면 선을 안 그린다"
    # 캡처 라이브러리가 못 읽을 수 있는 선택자를 안 쓴다
    rules = "\n".join(l for l in css.splitlines() if not l.strip().startswith(("/*", "*")))
    assert ":has(" not in rules, ":has() 는 캡처에서 안 먹을 수 있다"

    h = _fg.html(_fg.figure("구조도", "c", {"root": {"label": "A", "children": [
        {"label": "B"}, {"label": "C"}, {"label": "D"}]}}))
    assert "--n:3" in h, h[:200]
check("구조도 연결선이 맞물린다", _connectors_line_up)

def _capture_box_is_a_class():
    """캡처 상자를 id 가 아니라 class 로 잡는다.

    앱은 한 번에 하나만 만들지만, 여러 개를 나란히 둘 때 문서에 같은 id 가
    둘 생기고 querySelector 가 첫 것만 잡는다.
    """
    js = _js("shot.js")
    assert "box.className = 'bs-shot'" in js and "box.id = 'bs-shot'" not in js
    assert "'.bs-shot .'" in js, "스타일 범위가 id 로 좁혀진다"
    assert ".bs-shot .fig{max-width:none" in _fg.CSS
check("캡처 상자를 class 로 잡는다", _capture_box_is_a_class)

def _capture_unlocks_width():
    """캡처 상자 안에서는 도식 폭 제한을 푼다.

    상자를 960px 로 잡아도 `.fig` 가 max-width:820px 에 갇히면 **바깥 흰
    여백만 늘고 표 열은 그대로 짓눌린다.** 폭을 나눈 뜻이 없어진다.
    본문에서는 820 이 맞다 — 글줄이 길어지면 읽기 나쁘다.
    """
    css = _fg.CSS
    assert "max-width:820px" in css, "본문 제한이 사라졌다"
    assert ".bs-shot .fig{max-width:none" in css, "캡처에서 안 풀린다"
    # 캡처 상자 클래스와 맞아야 한다
    assert "box.className = 'bs-shot'" in _js("shot.js")
check("캡처에서 도식 폭 제한이 풀린다", _capture_unlocks_width)

def _tree_root_is_a_thing():
    """구조도 루트는 기준이 되는 대상이지 도식 제목이 아니다.

    "보고기업 기준 가치사슬" 을 루트에 넣으면 "그 아래에 업스트림이 있다"
    가 되어 같은 것을 두 번 말한다. 제목은 caption 이 맡는다.
    """
    md = _md("_write")
    assert "root.label` 에 도식 제목을 넣지 않습니다" in md, md[:0]
    assert "흐름을 그려야 하면 구조도가 아닙니다" in md
    # 너무 긴 루트는 코드가 자른다
    long = "가" * 40
    got = _fg._tree({"root": {"label": long, "children": [{"label": "나"}]}})
    assert len(got["root"]["label"]) == _fg.ROOT_MAX, got["root"]["label"]
check("구조도 루트가 제목이 아니다", _tree_root_is_a_thing)

def _figure_relation_checked():
    """도식이 관계를 왜곡하는지 본다.

    **틀린 정보를 그림으로 확정하는 것**이 글로 쓰는 것보다 나쁘다. 글은
    고칠 수 있지만 그림은 캡처해서 나가면 못 고친다. 실제로 "신고 의무"
    아래에 신고 주체와 자료 제공자가 나란히 놓였다.
    """
    # 갈래마다 깊이가 다르면 같은 층으로 안 읽힌다
    bad = _fg.flaws("구조도", {"root": {"label": "신고 의무", "children": [
        {"label": "수입자", "children": [{"label": "신고서"}, {"label": "인증서"}]},
        {"label": "수출 제조기업", "children": []}]}})
    assert bad and "깊이" in bad[0], bad
    # 나란한 구조는 통과
    assert not _fg.flaws("구조도", {"root": {"label": "보고기업", "children": [
        {"label": "상류", "children": [{"label": "조달"}]},
        {"label": "하류", "children": [{"label": "유통"}]}]}})
    # 같은 이름이 위아래에 있으면 계층이 아니다
    same = _fg.flaws("구조도", {"root": {"label": "신고 의무", "children": [
        {"label": "신고 의무"}, {"label": "자료 제공"}]}})
    assert same and "같은 이름" in same[0], same

    # 다른 형식도 본다
    assert _fg.flaws("대조표", {"columns": ["A", "B"], "rows": [
        {"criterion": "가", "cells": ["1", ""]},
        {"criterion": "나", "cells": ["2", ""]}]}), "빈 열을 못 잡는다"
    assert _fg.flaws("항목카드", {"cards": [{"title": "품목"}, {"title": "품목"}]})
    assert _fg.flaws("순서열", {"steps": [{"title": "하나"}]})
    assert "갈래는 같은 층이어야 합니다" in _md("_write")
check("도식이 관계를 왜곡하는지 본다", _figure_relation_checked)

def _figure_sense_told():
    """어긋난 도식을 발행 전에 알린다. 막지는 않는다."""
    from backend.output import checklist as _ck11
    out = []
    _ck11._figure_sense(out, {"write": {"sections": [{"heading": "가", "blocks": [
        {"type": "figure", "component": "구조도", "caption": "c",
         "data": {"root": {"label": "신고 의무", "children": [
             {"label": "수입자", "children": [{"label": "신고서"}, {"label": "인증서"}]},
             {"label": "수출 제조기업", "children": []}]}}}]}]}})
    assert out and out[0]["kind"] == "도식 관계 확인", out
    out2 = []
    _ck11._figure_sense(out2, {"write": {"sections": [{"heading": "가", "blocks": [
        {"type": "figure", "component": "구조도", "caption": "c",
         "data": {"root": {"label": "보고기업", "children": [
             {"label": "상류", "children": [{"label": "조달"}]},
             {"label": "하류", "children": [{"label": "유통"}]}]}}}]}]}})
    assert out2 == [], out2
check("어긋난 도식을 발행 전에 알린다", _figure_sense_told)

def _type_must_covered():
    """유형이 답해야 할 것을 구조가 맡는다.

    **비교형인데 같은 기준이 없으면 비교가 아니다.** 유형을 골라 놓고 그
    뼈대가 빠지면 글이 그 유형이 아니게 된다. 예전 must_have 는
    "동일한 기준에 따른 비교" 처럼 추상적이라 무엇이 빠졌는지 알 수 없었다.
    """
    from backend.data import skeletons as _sk2
    from backend.steps.outline.payload import payload as _op2, missing_must as _mm
    for name in _sk2.TYPES:
        must = _sk2.for_outline(name)["must_have"]
        assert len(must) >= 4, (name, must)
        assert all(len(m) >= 6 for m in must), (name, must)

    must = _sk2.for_outline("비교형")["must_have"]
    good = _op2([
        {"title": "왜 다른가", "objective": "전환기간과 본격 시행을 견주는 공통 기준을 세운다",
         "covers": ["무엇과 무엇을 견주는지", "같은 기준이 무엇인지"]},
        {"title": "무엇이 다른가", "objective": "그 기준에서 무엇이 다른지 짚는다",
         "covers": ["차이"]},
        {"title": "어느 쪽인가", "objective": "어느 쪽을 언제 고르는지 정리한다",
         "covers": ["상황별 선택"]}])
    assert len(_mm(good, must)) <= 1, _mm(good, must)

    bare = _op2([{"title": "상황", "objective": "상황을 설명한다", "covers": ["배경"]}])
    assert len(_mm(bare, must)) >= 4, _mm(bare, must)
    assert "covers 는 must_have 를 갈라 맡습니다" in _md("_prompt", "outline")
check("유형 필수 항목을 구조가 맡는다", _type_must_covered)

def _leftovers_caught():
    """견본 값이 결과물에 남았는지 본다.

    **미완료 표시가 남은 글은 최종본이 아니다.** 도식·사진 자리는 사람이
    채우는 것이라 여기서 안 본다 — 그건 따로 알린다.
    """
    from backend.output import checklist as _ck12
    out = []
    _ck12._placeholders(out, {"write": {"lead": "리드", "sections": [
        {"heading": "가", "blocks": [
            {"type": "para", "text": "자세한 것은 example.com 을 보세요."}]}],
        "sources": [{"title": "가이드", "url": "https://example.com/g"}]}}, "site")
    assert out and out[0]["kind"] == "견본 값이 남음", out
    clean = []
    _ck12._placeholders(clean, {"write": {"lead": "리드", "sections": [], "sources": []}}, "site")
    assert clean == [], clean
    # 자리표시(도식·사진)는 여기서 안 본다 — 따로 알린다
    assert "[도식" not in str(_ck12.LEFTOVER)
check("견본 값이 남으면 알린다", _leftovers_caught)

def _naver_ends_properly():
    """네이버 글이 갑자기 끝나지 않는다.

    마지막 섹션이 목록이나 강조 박스로 끝나면 글이 멈춘 것처럼 읽힌다.
    홈페이지는 참고자료·작성자가 뒤에 붙어 마무리가 되므로 안 본다.
    """
    from backend.output import checklist as _ck13
    two = lambda last: {"write": {"sections": [
        {"heading": "가", "blocks": [{"type": "para", "text": "p"}]},
        {"heading": "나", "blocks": [{"type": "para", "text": "p"}, last]}]}}
    out = []
    _ck13._ending(out, two({"type": "list", "items": [{"title": "a", "body": "b"}]}), "naver")
    assert out and out[0]["kind"] == "맺음이 없다", out
    ok = []
    _ck13._ending(ok, two({"type": "para", "text": "정리 문단"}), "naver")
    assert ok == [], ok
    # 홈페이지는 안 본다
    site = []
    _ck13._ending(site, two({"type": "list", "items": [{"title": "a", "body": "b"}]}), "site")
    assert site == [], site
    assert "마지막 섹션은 요약입니다" in _md("naver_outline")
check("네이버 글이 갑자기 끝나지 않는다", _naver_ends_properly)

def _figure_width_apart():
    """도식은 본문보다 넓게 찍는다.

    본문 680px 은 휴대폰에 맞지만 4열 대조표에는 모자란다. 캡처본은 네이버
    본문에서 화면 폭에 맞춰 줄어드니 원본을 넓게 찍어도 최종 크기는 같다.
    """
    from backend.data import brand as _br5
    cap = _cn.capture("naver")
    assert cap["figure_widths"]["대조표"] > cap["width"], cap
    assert set(cap["figure_widths"]) == set(_fg.NAMES), cap["figure_widths"]
    assert "figure_widths" not in _cn.capture("site"), "홈페이지는 캡처를 안 한다"
    js = _js("shot.js")
    assert "widthOf(el)" in js and "data-fig" in js, "화면이 형식별 폭을 안 쓴다"
check("도식 캡처 폭이 본문과 다르다", _figure_width_apart)

def _naver_gets_figure_css():
    """네이버 결과물이 도식 스타일을 같이 받는다.

    채널을 가르면서 `figures.CSS` 를 싣는 곳이 홈페이지 렌더러 하나만
    남았다. 네이버는 마크업만 받아서 **class 는 있고 규칙이 없었다** —
    브라우저 기본값으로 그려진 것을 캡처해 그대로 내보냈다. 실제 도식이
    상자도 선도 색도 없는 글자 목록으로 나갔다.
    """
    got = _render(ALL, "naver")
    css = got.get("figure_css") or ""
    assert ".fig-cmp" in css and ".fig-card" in css, "도식 규칙이 없다"
    assert _br.COLORS["accent"] in css, "브랜드 색이 없다"
    # 화면이 실제로 싣는다
    js = _js("pages/result.js")
    assert "out.naver.figure_css" in js and "'<style>' + css" in js
check("네이버가 도식 스타일을 받는다", _naver_gets_figure_css)

def _naver_has_figure_source():
    """네이버 본문은 자리표시뿐이다. 저장할 원본이 따로 나와야 한다.

    예전에는 홈페이지 결과물에서 캡처했는데, 채널이 갈리면서 네이버
    드래프트에는 홈페이지 결과물이 없다. 같은 figures.py 로 여기서 그린다.
    """
    n = _render(ALL, "naver")
    assert "[도식 1 삽입]" in n["html"], "자리표시가 없다"
    figs = n["figures"]
    assert figs and figs[0]["n"] == 1, figs
    assert "figure class=\"fig\"" in figs[0]["html"], figs[0]
    # 번호가 본문 자리표시와 같아야 사람이 어디에 넣을지 안다
    assert all(f["n"] == i + 1 for i, f in enumerate(figs)), figs
    assert "Shot.png(jobs[i].el" in _js("pages/result.js")
check("네이버가 도식 원본을 따로 낸다", _naver_has_figure_source)

check("홈페이지는 도식 원본을 따로 안 낸다", lambda: (
    "figures" not in _render(ALL, "site")) or 1/0)

def _brand_no_shadow():
    """그림자를 쓰지 않는 것이 회사 기준이다. 카드에만 남아 있었다."""
    assert "box-shadow:none" in _fg.CSS and "rgba(" not in _fg.CSS, "그림자가 남았다"
    assert _br.SHADOW == "none"
check("도식에 그림자가 없다", _brand_no_shadow)

def _naver_capture_css():
    """네이버 도식은 렌더러가 아니라 캡처 스타일로 갈린다.

    렌더러를 둘로 만들면 도식 내용이 채널마다 어긋날 수 있다. 마크업은
    한 벌로 두고 찍을 때만 세로 1열·큰 글자로 갈아 끼운다.
    """
    css = _cn.capture("naver")["css"]
    assert "grid-template-columns:1fr" in css, css      # 카드·구조도 1열
    assert "font-size:18px" in css, css                 # 글자 크게
    assert "css" not in _cn.capture("site"), "홈페이지는 덧씌우지 않는다"
    # 캡처 상자 안으로만 범위를 좁힌다. 미리보기가 흔들리면 안 된다.
    assert "'.bs-shot .'" in _js("shot.js"), "범위를 안 좁혔다"
check("네이버 도식은 캡처 스타일로 갈린다", _naver_capture_css)

check("강조 박스가 종류별로 다르다", lambda: (
    "정의" in _wr.CALLOUT_LABELS
    and ".post-callout.warn" in _site_r.BODY_CSS
    and _site_r.KIND["주의"] == "warn") or 1/0)

check("네이버는 도식 캡처를 알린다", lambda: (
    "도식 캡처" in [x["kind"] for x in
                _r.build(as_channel(ALL, "naver"))["checklist"]]) or 1/0)

def _service_not_invented():
    """서비스명을 모델이 만들지 않는다. 표에 없으면 아무것도 안 나간다."""
    d = as_channel(ALL, "site")
    d["topic"] = {"label": "x", "payload": {"service_id": "svc_99"}}
    # class 이름은 CSS 규칙에도 있다. 실제 섹션이 나갔는지를 본다.
    assert '<section class="post-svc">' not in _r.build(d)["site"]["html"]
check("없는 서비스는 안 나간다", _service_not_invented)

def _brand_vars():
    """색이 세 군데 흩어져 있던 것을 변수 하나로 모았다."""
    html = _render(ALL, "site")["html"]
    assert "--bs-accent" in html and _br.COLORS["accent"] in html, html[:300]
    assert "#1685D5" not in html, "옛 색이 남았다"
    # 캡처는 도식을 .post 밖에 복제해 찍는다. 기본값이 없으면 색이 사라진다.
    assert f'var(--bs-accent, {_br.COLORS["accent"]})' in _fg.CSS, "기본값이 없다"
check("색은 브랜드 한 곳에서 온다", _brand_vars)


print("\n── 제목의 메타와 슬러그 ──")

def _slug_is_cleaned():
    """모델이 낸 슬러그를 그대로 쓰지 않는다.

    공백·대문자·한글이 섞여 들어오면 주소가 깨진다. 영문이 하나도 없으면
    빈 문자열을 준다 — 한글 로마자 표기는 규칙이 여럿이라 여기서 정할 일이
    아니고, 사람이 CMS 에서 채우는 편이 낫다.
    """
    assert _tt._slug("CBAM Supplier Data", "t") == "cbam-supplier-data"
    assert _tt._slug("한글 슬러그", "t") == ""
    assert _tt._slug("  --A--B  ", "t") == "a-b"
    got = {"meta_description": "설명", "slug": "A B"}
    pay = _tt.payload("제목", "선언형", ["cbam"], channel="site", got=got)
    assert pay["slug"] == "a-b" and pay["meta_description"] == "설명", pay
check("슬러그는 코드가 다듬는다", _slug_is_cleaned)

def _used_keywords_by_code():
    """쓰인 키워드를 모델에게 묻지 않는다.

    한국어는 조사가 붙어서 "CBAM" 이 "CBAM이" 로 나온다. 모델에게 물으면
    제목에 없는 것을 썼다고 하거나 조사 때문에 빠뜨린다. 세는 일은 코드가
    정확히 할 수 있다.
    """
    kws = [{"keyword": "CBAM", "volume": 900},
           {"keyword": "내재배출량", "volume": 300},
           {"keyword": "탄소 배출량", "volume": 500},
           {"keyword": "가", "volume": 10}]
    t = "CBAM이 본시행되면 내재배출량을 어떻게 산정하나"
    got = _tt.used_keywords(t, kws)
    assert got == ["CBAM", "내재배출량"], got          # 조사가 붙어도 잡힌다
    assert "가" not in got, "한 글자가 아무 데나 걸린다"
    # 공백을 접으므로 "탄소 배출량" 도 "탄소배출량" 안에서 잡힌다
    assert _tt.used_keywords("탄소배출량의 산정", kws) == ["탄소 배출량"]
    assert "used_keywords" not in _md("_prompt", "title"), "모델에게 아직 묻는다"
check("쓰인 키워드는 코드가 센다", _used_keywords_by_code)

def _main_keyword_validated():
    """대표 검색어를 모델이 고른 대로 믿지 않는다.

    입력에 없거나 제목에 안 들어간 낱말이면 검색에 안 걸린다.
    """
    kws = [{"keyword": "CBAM", "volume": 900}, {"keyword": "내재배출량", "volume": 300}]
    t = "CBAM이 본시행되면 내재배출량을 어떻게 산정하나"
    assert _tt._main("없는키워드", t, kws) == "CBAM", "엉뚱한 값을 그대로 썼다"
    assert _tt._main("내재배출량", t, kws) == "내재배출량"
    assert _tt._main("CBAM", "키워드 없는 제목", kws) == ""
check("대표 검색어를 코드가 검증한다", _main_keyword_validated)

check("슬러그는 낱말 수도 제한한다", lambda: (
    _tt._slug("CBAM Definitive Regime Supplier Emissions Data Requirements Guide")
    == "cbam-definitive-regime-supplier-emissions-data") or 1/0)

def _written_title_counts_keywords():
    """직접 쓴 제목도 키워드는 코드가 센다.

    메타·슬러그·태그는 채널마다 다른 프롬프트가 필요해 아직 안 채운다 —
    확인 목록이 그 사실을 알린다.
    """
    assert _st.BY_KEY["title"].written_needs_input
    v = _tt.written("CBAM이 본시행되면", {"keywords": [{"keyword": "CBAM", "volume": 9}],
                                    "channel": "naver"})[2]
    assert v["used_keywords"] == ["CBAM"] and v["main_keyword"] == "CBAM", v
    assert v["meta_description"] == "" and v["tags"] == [], v
check("직접 쓴 제목도 키워드를 센다", _written_title_counts_keywords)

def _title_meta_flagged():
    from backend.output import checklist as _ck2
    out = []
    d = {"title": {"payload": {"title": "t", "meta_description": "", "slug": "",
                               "main_keyword": "", "tags": []}}}
    _ck2._title_meta(out, d, "site")
    assert out and "메타 설명" in out[0]["text"] and "슬러그" in out[0]["text"], out
    out2 = []
    _ck2._title_meta(out2, d, "naver")
    assert out2 and "대표 키워드" in out2[0]["text"] and "태그" in out2[0]["text"], out2
def _site_goes_deeper():
    """홈페이지는 네이버 글을 늘린 것이 아니다.

    같은 근거를 쓰더라도 **한 층 더 들어간 설명**을 담는다. 문장을 늘리거나
    서비스·안내만 붙이면 네이버 본문에 CTA 만 얹은 꼴이 된다.
    """
    site, nav = _md("site_write"), _md("naver_write")
    assert "네이버 글을 늘린 것이 아닙니다" in site
    assert "왜 기존 자료로 대체할 수 없는지" in site
    # **전부 넣으라고 하지 않는다.** 근거 없는 것을 만들면 그게 더 나쁘다.
    assert "전부 넣으려 하지 않습니다" in site
    assert "네이버 글을 늘린 것이 아닙니다" not in nav, "네이버에도 붙었다"
check("홈페이지가 한 층 더 들어간다", _site_goes_deeper)

def _no_glued_particle():
    """조사를 목록 뒤에 이어 붙이지 않는다.

    앞말 받침에 따라 이/가가 달라지는데 목록 끝이 무엇일지 모른다 —
    "URL 슬러그이 비어 있습니다" 가 실제로 나왔다.
    """
    from backend.output import checklist as _ck15
    for ch in ("site", "naver"):
        out = []
        _ck15._title_meta(out, {"title": {"payload": {
            "title": "제목", "meta_description": "", "slug": "",
            "main_keyword": "", "tags": []}}}, ch)
        assert out, ch
        t = out[0]["text"]
        assert "슬러그이" not in t and "태그이" not in t, t
        assert t.startswith("비어 있습니다 — "), t
check("조사를 목록 뒤에 안 붙인다", _no_glued_particle)

def _no_internal_terms_on_screen():
    """화면에 내부 계약명을 보이지 않는다.

    `covers` · `claims` · `authority` · `partial` 은 파이프라인 안에서 쓰는
    이름이다. **사람은 그 뜻을 알 이유가 없다.** 실제로 구조 카드에
    "covers 10개 · 명제 5개" 가 그대로 나갔다.
    """
    from backend.steps.outline import LACK
    from backend.steps.evidence import policy as _po2
    from backend.steps.outline.payload import label as _lb2

    # 카드에 나가는 말
    assert set(LACK.values()) == {"부분", "다루는 내용", "확인된 근거"}, LACK
    assert "섹션" not in _lb2(3, 1, 1), _lb2(3, 1, 1)
    assert "부분" in _lb2(3, 1, 1)

    # 상태·자격 라벨
    for v in _po2.AUTHORITY_LABELS.values():
        assert "자격" not in v, v
    assert _po2.AUTHORITY_LABELS["insufficient"] == "공식 근거 부족"

    # 확인 목록에도 안 나간다
    from backend.output import checklist as _ck16
    d = {"type": {"payload": {"article_type": "정보형"}},
         "outline": {"payload": {"sections": [
             {"title": "가", "covers": ["정의"], "claim_refs": []}]}},
         "write": {"lead": "짧게", "sections": []}}
    out = []
    _ck16._volume(out, d, "naver")
    joined = " ".join(x["text"] + x["note"] for x in out)
    assert "명제" not in joined and "covers" not in joined, joined
    assert "다루는 내용" in joined, joined
check("화면에 내부 용어를 안 보인다", _no_internal_terms_on_screen)

def _fresh_folder_runs():
    """푼 폴더를 그대로 돌려도 된다.

    **폴더를 통째로 갈아끼우면 로그·업로드·이미지 폴더가 같이 사라진다.**
    셋 다 없어도 앱이 돌아야 한다 — 처음 쓸 때 알아서 만든다.

    `.env` 는 다르다. 그건 사람이 채워야 하고, 안 채우면 화면에
    "개발용 견본" 이 뜬다.
    """
    # 문서를 이름으로 열지 않는다. deploy 안의 md 를 다 합쳐서 본다 —
    # 파일 이름이 바뀌어도 검사가 안 깨진다.
    win = "\n".join(f.read_text(encoding="utf-8")
                    for f in sorted((paths.ROOT / "deploy").glob("*.md")))
    # 문서가 말하는 폴더 이름이 코드와 같아야 한다
    for name in ("images", "uploads", "choice", "response", "feedback"):
        assert f"{name}/" in win, name
    # 뜬 뒤에 무엇을 봐야 하는지
    for k in ('"llm"', '"imagen"', '"search"'):
        assert k in win, k
    # **없으면 만든다.** 사람이 미리 만들 필요가 없다
    src = (paths.BACKEND / "steps" / "evidence" / "upload.py").read_text(encoding="utf-8")
    assert "mkdir(parents=True, exist_ok=True)" in src
check("푼 폴더를 그대로 돌려도 된다", _fresh_folder_runs)

def _build_and_evidence_split():
    """구조 문제와 근거 문제를 갈라 적는다.

    한 줄에 섞으면 **구조를 바꿔야 하는지 근거를 더 찾아야 하는지** 사람이
    구분할 수 없다. 근거 부족은 구조를 바꿔도 안 풀린다.
    """
    src = (paths.BACKEND / "steps" / "outline" / "__init__.py").read_text(encoding="utf-8")
    assert "구성 점검: " in src and "근거 점검: " in src, "카드가 안 갈렸다"
    assert 'evid if k == "claims" else build' in src

    from backend.output import checklist as _ck17
    out = []
    _ck17._volume(out, {"type": {"payload": {"article_type": "정보형"}},
                        "outline": {"payload": {"sections": [
                            {"title": "가", "covers": ["정의"], "claim_refs": []}]}},
                        "write": {"lead": "짧게", "sections": []}}, "naver")
    ev = next(x for x in out if x["kind"] == "근거가 적다")
    assert "구조를 바꿔도 안 풀립니다" in ev["note"], ev
    # **2→4 같은 계산 표기를 안 쓴다**
    assert "→" not in ev["text"], ev["text"]
    assert "현재" in ev["text"] and "기준" in ev["text"], ev["text"]
check("구조 문제와 근거 문제를 갈라 적는다", _build_and_evidence_split)

def _marks_are_uniform():
    """요약 줄 표시를 한 모양으로 통일한다.

    `+도식` · `+그림` · `자료 1장` 처럼 섞으면 내부 표기처럼 보인다.
    """
    from backend.steps.outline.payload import payload as _op5, detail as _dt
    p5 = _op5([{"title": "가", "image": {"purpose": "p", "form": "순서열"}},
               {"title": "나", "illustration": {"purpose": "상황"}},
               {"title": "다", "media": {"type": "capture", "purpose": "요청 양식 화면"}}],
              media=True)
    line = _dt(p5)
    assert "[도식]" in line and "[본문 그림]" in line and "[자료 화면]" in line, line
    assert "+" not in line, line

    # 펼치면 **무엇이 빠졌는지** 보인다. 개수만으로는 고를 수 없다.
    src = (paths.BACKEND / "steps" / "outline" / "__init__.py").read_text(encoding="utf-8")
    assert "빠진 내용 — " in src
check("요약 줄 표시가 한 모양이다", _marks_are_uniform)

check("빈 제목 부가정보를 확인 목록이 알린다", _title_meta_flagged)

check("제목이 새 각도를 만들지 않는다", lambda: (
    "새 각도를 만들지 않습니다" in _md("_prompt", "title")
    and "직무명을 모든 제목에 되풀이해 넣지 않는다" in _md("_prompt", "title")) or 1/0)

check("근거가 제목의 단정 수준을 정한다", lambda: (
    "authority" in _md("_prompt", "title")
    and "공식 의무나 확정된 규정처럼 쓰지 않는다" in _md("_prompt", "title")) or 1/0)

def _offline_no_fixed_number():
    """오프라인 후보가 숫자를 약속하지 않는다.

    구조가 5개인지 모르는데 "대응 5단계" 를 만들면 뒤 단계가 그 수를 채운다.
    """
    rows = _tt._offline({"topic": {"label": "소재", "payload": {}},
                         "reader": {"payload": {}}}, {"keywords": []})
    import re as _re
    assert not any(_re.search(r"\d+\s*(단계|가지)", r["title"]) for r in rows), rows
    assert "click_reason" not in _md("_prompt", "title")
check("오프라인 후보가 숫자를 약속하지 않는다", _offline_no_fixed_number)

def _payload_same_shape():
    """모양은 채널과 상관없이 같다. 안 맞는 것만 코드가 비운다.

    채널마다 다른 필드를 내면 저장·API·화면·결과물이 전부 양쪽을 알아야
    한다. 그리고 프롬프트가 "비워 두라" 를 안 지키는 날 네이버 결과물에
    엉뚱한 슬러그가 붙는다 — 그래서 비우는 일도 코드가 한다.
    """
    got = {"meta_description": "설명", "slug": "A B", "main_keyword": "CBAM",
           "secondary_keywords": ["내재배출량"], "tags": ["#CBAM", "CBAM 대응", "#CBAM"]}
    a = _tt.payload("t", "s", ["k"], channel="site", got=got)
    b = _tt.payload("t", "s", ["k"], channel="naver", got=got)
    assert set(a) == set(b), (sorted(a), sorted(b))
    assert a["slug"] and not a["tags"], a
    assert not b["slug"] and not b["meta_description"], b
    assert b["tags"] == ["CBAM", "CBAM대응"], b["tags"]   # # 과 공백·중복 정리
check("제목 확정값 모양은 채널과 무관하다", _payload_same_shape)

check("메타·태그 여부는 채널이 정한다", lambda: (
    _cn.of("site").meta_required and not _cn.of("naver").meta_required
    and _cn.of("naver").tags_allowed and not _cn.of("site").tags_allowed) or 1/0)

def _channel_prompts_registered():
    """구조·제목이 채널마다 다른 프롬프트를 부른다."""
    from backend import prompt as _pr
    for key in ("outline", "title"):
        assert _st.BY_KEY[key].by_channel, key
        for ch in _cn.NAMES:
            n = f"{ch}_{key}"
            assert n in _pr.REGISTRY and _pr.BASE[n].stem == "_prompt", n
        assert _st.BY_KEY[key].prompt_of("naver") == f"naver_{key}"
        assert _st.BY_KEY[key].prompt_of("없는채널") == f"site_{key}"
    built = _pr.build("naver_outline")
    assert "3~5개" in built and "4~7개" not in built, "채널 델타가 안 붙었다"
check("구조·제목이 채널 프롬프트를 부른다", _channel_prompts_registered)

def _steps_are_flat():
    """단계 폴더가 steps/ 바로 아래 있다.

    한때 common/ 층을 두고 옆에 site/ · naver/ 를 만들 자리로 비워 뒀는데,
    채널을 프롬프트로 가르기로 정해서 그 자리를 안 쓰게 됐다. 형제가 없는
    common/ 은 "옆에 common 아닌 게 있다" 는 거짓말이라 걷어냈다.
    """
    d = paths.BACKEND / "steps"
    dirs = {p.name for p in d.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert "common" not in dirs and "site" not in dirs and "naver" not in dirs, dirs
    # 등록된 단계 폴더가 곧 그 목록이다
    assert dirs == set(_st.DIR_OF), (dirs, set(_st.DIR_OF))
check("단계 폴더는 steps 바로 아래 있다", _steps_are_flat)


print("\n── 배포 문서가 코드와 맞나 ──")


def _deploy_text(only=None) -> str:
    """deploy/ 안의 문서를 이어 붙인다.

    파일 이름을 목록으로 박아 두지 않는다. 한글 이름(운영.md)이 zip 을
    거치며 인코딩이 깨지는 환경이 있어서, 목록으로 열면 그 환경에서만
    FileNotFoundError 가 난다.

    only 를 주면 이름에 그 말이 든 것만 읽는다.
    """
    out = []
    for f in sorted((paths.ROOT / "deploy").glob("*.md")):
        if only and only not in f.name:
            continue
        out.append(f.read_text(encoding="utf-8"))
    assert out, f"deploy/ 에 읽을 문서가 없다 (only={only})"
    return "\n".join(out)

def _deploy_env_keys():
    """.env 의 키가 배포 문서에 다 적혀 있다.

    문서가 낡으면 **키를 안 넣은 채로 세팅된다.** 특히 TAVILY 는 없어도
    앱이 그대로 돌아서 오류가 안 나고, 결과물을 보고서야 눈치챈다.
    """
    readme = (paths.ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    env = (paths.ROOT / ".env").read_text(encoding="utf-8")
    # .env 에 있는 키 전부. 하나 추가하면 문서도 같이 고쳐야 통과한다.
    keys = [l.split("=")[0].strip() for l in env.splitlines()
            if "=" in l and not l.strip().startswith("#")]
    keys = [k for k in keys if k.endswith("_KEY")]
    assert len(keys) >= 3, keys
    # 설명만 있는 게 아니라 **채워 넣으라는 줄**이 있어야 한다.
    # 문장에만 이름이 나오면 사람이 어디에 넣을지 모른다.
    # 줄 앞뒤 공백과 \r 을 먼저 턴다. 윈도우에서 받아 고치면 CRLF 가 섞인다.
    fill = {l.split("=")[0].strip() for l in readme.splitlines()
            if "=" in l and l.strip().startswith(tuple(keys))}
    missing = [k for k in keys if k not in fill]
    assert not missing, f"배포 문서에 채워 넣을 줄이 없다: {missing}"
check("배포 문서가 모든 키를 적는다", _deploy_env_keys)

def _health_has_flags():
    """문서가 보라고 하는 값을 health 가 실제로 준다."""
    h = cu.get("/api/health").json()
    for k in ("llm", "imagen", "search"):
        assert k in h, f"/api/health 에 {k} 가 없다"
    docs = (paths.ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    assert "search" in docs, "문서가 search 를 안 알려 준다"
check("health 가 키 상태 셋을 알린다", _health_has_flags)

def _startup_warns():
    """키가 없으면 뜰 때 알린다. 셋 다."""
    src = (paths.ROOT / "run.py").read_text(encoding="utf-8")
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY"):
        assert k in src, f"run.py 가 {k} 없음을 안 알린다"
check("키가 없으면 뜰 때 알린다", _startup_warns)

def _deploy_log_dirs():
    """문서의 로그 폴더 이름이 실제와 같다.

    trail/ 하나였던 것이 셋으로 갈렸는데 문서가 옛 이름을 들고 있었다.
    """
    docs = _deploy_text()
    for s_ in history.STREAMS:
        assert f"{s_}/" in docs, f"배포 문서에 {s_}/ 가 없다"
    assert "trail/" not in docs, "옛 로그 폴더 이름이 남아 있다"
check("배포 문서의 로그 폴더가 실제와 같다", _deploy_log_dirs)


def _tests_are_portable():
    """검사가 OS 를 가정하지 않는다.

    윈도우에서 돌렸더니 넷이 실패했다. 앱 버그는 하나도 없었고 전부
    검사가 리눅스를 전제한 것이었다 — 외부 명령 호출, 경로가 슬래시로
    시작한다는 가정, 한글 파일명 하드코딩.

    개발은 리눅스에서 하고 실제로 쓰는 곳은 윈도우라, 여기서 안 막으면
    같은 일이 되풀이된다. **금지어를 문자열로 세지 않는다** — 이 파일
    자신이 그 낱말을 들고 있어서 자기에게 걸린다. 실제로 무엇을 하는지를
    본다.
    """
    import re as _re, subprocess as _sp
    src = pathlib.Path(__file__).read_text(encoding="utf-8")

    # ① 외부 명령을 부르지 않는다. 이 파일이 실제로 무엇을 import 했는지
    #    본다 — 문자열을 세면 이 검사 자신의 설명에 걸린다.
    import sys as _sys
    mine = _sys.modules[__name__]
    bad = [n for n in ("subprocess", "shlex") if hasattr(mine, n)]
    assert not bad, f"외부 명령 모듈을 들였다: {bad}. OS 마다 다르다"

    # ② 경로를 문자열로 판단하지 않는다
    assert not _re.search(r'startswith\(\s*[\'"]/[\'"]\s*\)', src), \
        "윈도우 경로는 슬래시로 시작하지 않는다. Path.is_absolute 를 쓴다"

    # ③ deploy 문서를 이름으로 열지 않는다. 한글 이름은 zip 을 거치며
    #    인코딩이 깨지는 환경이 있다.
    named = [f.name for f in (paths.ROOT / "deploy").glob("*.md")
             if f.name != "README.md" and f'"{f.name}"' in src]
    assert not named, f"deploy 문서를 이름으로 연다: {named}"

    # ④ 파일을 열 때 인코딩을 명시한다. 윈도우 기본은 cp949 다.
    bare = [o for o in _re.findall(r"read_text\(([^)]*)\)", src)
            if "encoding" not in o]
    assert not bare, f"read_text 에 encoding 이 없다: {bare[:3]}"


check("검사가 OS 를 가정하지 않는다", _tests_are_portable)


print("\n── 로그 보기 ──")
# 평가를 한 건도 안 남긴 채로 왔다. feedback/ 이 비어 있으면 세 갈래가 다
# 섞이는지 볼 수 없으므로 여기서 한 건 남긴다 — 엔드포인트 자체도 이 줄이
# 처음 부른다.
check("평가 저장",  lambda: c.post("/api/feedback", json={
    "step": "result", "option_id": "", "verdict": "up",
    "tags": [], "note": "확인용"}).json()["ok"] or 1/0)
check("평가가 feedback/ 에",
      lambda: (history.counts()["feedback"] > 0
               and history.read(stream="feedback")[-1]["note"] == "확인용") or 1/0)

_L = lambda q="": c.get("/api/logs" + q).json()

check("주소만 쳐도 나온다",   lambda: (_L()["ok"] and _L()["rows"]) or 1/0)
check("세 갈래가 다 섞인다",  lambda: {r["stream"] for r in _L("?limit=0")["rows"]}
                                      == set(history.STREAMS) or 1/0)
check("total 은 자르기 전 수", lambda: (_L("?limit=2")["total"] == len(history.read())
                                       and _L("?limit=2")["shown"] == 2) or 1/0)
check("stream 으로 거른다",   lambda: all(r["stream"] == "choice"
                                        for r in _L("?stream=choice&limit=0")["rows"]) or 1/0)
check("kind 로 거른다",       lambda: all(r["kind"] == "generated"
                                        for r in _L("?kind=generated&limit=0")["rows"]) or 1/0)
check("sid 로 거른다", lambda: (lambda sid: len(_L(f"?sid={sid}&limit=0")["rows"])
                                            == len(history.journey(sid)))(_L()["sids"][0]) or 1/0)
check("order 로 뒤집힌다",    lambda: (_L("?limit=0")["rows"][0]["at"]
                                      >= _L("?order=asc&limit=0")["rows"][0]["at"]) or 1/0)
check("요약에는 raw 가 없다", lambda: all("raw" not in r for r in _L("?limit=0")["rows"]) or 1/0)
check("full=1 이면 통째로",   lambda: any("raw" in r or "input" in r
                                        for r in _L("?full=1&limit=3")["rows"]) or 1/0)
def _empty_result_tells_what_exists():
    """빈 결과일 때 무엇을 물어야 하는지 알려 준다.

    예전에는 `steps: []` 만 돌려줘서 이름을 틀리면 실제 이름을 찾을 방법이
    없었다. 프롬프트 이름(naver_outline)과 단계 key(outline)가 달라서
    실제로 막혔다.
    """
    got = cu.get("/api/logs?step=naver_outline").json()
    assert got["total"] == 0, got["total"]
    assert got["asked"] == {"step": "naver_outline"}, got.get("asked")
    assert "outline" in got["available"]["steps"], got.get("available")
    assert "단계 key" in got["hint"], got.get("hint")
    # 결과가 있으면 힌트를 안 준다 — 있는데 붙으면 잡음이다
    ok = cu.get("/api/logs?step=outline").json()
    assert ok["total"] and "hint" not in ok, ok.get("hint")
check("빈 결과가 실제 이름을 알려 준다", _empty_result_tells_what_exists)

def _counts_follow_the_filter():
    """counts 가 필터를 탄다.

    예전에는 스트림 전체를 다시 세서 total 과 기준이 달랐다 — 같은 응답
    안에서 0 건인데 27 건이라고 적혀 있었다.
    """
    got = cu.get("/api/logs?stream=choice").json()
    assert sum(got["counts"].values()) == got["total"], (got["counts"], got["total"])
    assert got["counts"]["response"] == 0, got["counts"]
check("counts 가 필터 결과를 센다", _counts_follow_the_filter)

check("무엇으로 거를 수 있는지 알려 준다", lambda: (
    set(cu.get("/api/logs?limit=0").json()) >= {"steps", "kinds", "sids", "docs"}) or 1/0)

check("모르는 stream 은 거절", lambda: (_L("?stream=엉뚱")["reason"] == "unknown_stream") or 1/0)

print(f"\n════ 통과 {len(OK)} · 실패 {len(BAD)} ════")
print(f"  코드      {build.CODE}")
print(f"  프롬프트   {build.CONTENT}")
print(f"  로그 폴더   {' · '.join(history.STREAMS)}  (ROOT 아래)")
if BAD:
    for n, e in BAD: print(f"  ✗ {n}: {e}")
    sys.exit(1)
