"""본문 작성.

확정값을 write.md 에 넘기고, 돌아온 것을 조립이 그대로 쓸 수 있는 모양으로
검증한다. options.py 와 자리를 나눈 이유는 하는 일이 다르기 때문이다 —
저쪽은 사람이 고를 후보를 만들고, 여기는 고르기가 끝난 뒤 한 벌을 만든다.

검증이 이 모듈의 절반이다. 본문은 고를 여지 없이 나온 그대로 나가는
유일한 단계라, LLM 이 흘린 것을 여기서 못 잡으면 그대로 화면에 나간다.
"""

import re

import pathlib

from .. import llm, prompt as prompts
from . import figures
from ..data import skeletons
from ..data.channels import channel_of
from ..data import channels
from ..steps.payload import is_confirmed

# 본문은 승인 이후에 도는 것이라 단계가 아니다. 프롬프트만 옆에 둔다.
#
# **채널마다 다른 것은 프롬프트뿐이다.** 입력 조립·근거 가르기·출력 검증은
# 채널을 가리지 않으므로 이 모듈을 복제하지 않는다. 복제하면 한쪽만 고쳐지고
# 그 어긋남은 조용히 지나간다 — sanitize 를 한 곳에 모은 것과 같은 이유다.
#
# 채널 분기도 코드에 넣지 않는다. 규칙은 data/channels.py 에서 주입받고
# 프롬프트는 이름으로 고른다.
_DIR = pathlib.Path(__file__).parent
for _ch in channels.NAMES:
    prompts.register(f"{_ch}_write", _DIR / _ch / "write.md",
                     base=_DIR / "_write.md")


def prompt_of(channel: str) -> str:
    return f"{channel if channel in channels.NAMES else 'site'}_write"

# 본문에 섞여 나오는 마크다운. 프롬프트로 금지했지만 흘러나온다.
# 조립이 문단을 <p> 로 그대로 감싸므로 기호가 화면에 그대로 보인다.
_MD_HEAD = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s+)")


def _s(v, n=2000):
    return "" if v is None else str(v).strip()[:n]


def _pay(d, key):
    return d.get(key, {}).get("payload", {}) or {}


def _label(d, key):
    return d.get(key, {}).get("label", "")


def _para(t):
    """문단 한 줄. 마크다운 흔적을 걷어낸다."""
    t = _MD_HEAD.sub("", _s(t))
    return t.replace("**", "").replace("__", "").strip()


# ── 근거 가르기 ───────────────────────────────────────────────
#
# **실물이 손에 있는 것만 확인된 출처다.** 두 가지가 그렇다.
#
#   url   소재에 딸려온 기사
#   file  사람이 올린 PDF — 원문을 직접 올린 것이라 기사보다 확실하다
#
# 7단계 프롬프트는 검색을 하지 않고 URL 을 금지하므로, 둘 다 없는 것은
# "확인해야 할 대상" 이지 인용할 출처가 아니다.
#
# 예전에는 url 하나로만 갈랐다. 그때는 올린 PDF 가 미확인으로 떨어져
# 인용도 못 하고 참고자료에도 못 나갔다 — 사람이 원문을 손에 쥐고
# 올렸는데 글이 그것을 못 쓰는 상태였다.
#
# id 는 여기서 새로 매긴다. 후보 id 는 세션 한정이라 기대지 않는다.

def _evidence_state(d) -> dict:
    """근거를 얼마나 확보했나. 본문이 약속할 수 있는 범위를 정한다.

    빈 목록만으로는 모델이 "안 준 것" 과 "없는 것" 을 구별하지 못한다.
    수를 세어 명시하면 **없다는 사실 자체가 입력**이 된다.
    """
    conf, unconf = _split(d)
    return {
        "citable": len(conf),
        "unverified": len(unconf),
        # 하나도 없으면 이 글은 사실을 새로 단정할 수 없다.
        "can_assert": bool(conf),
    }


def _split(d):
    p = _pay(d, "evidence")
    items = p.get("items", [p]) if p else []
    conf, unconf = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        url = _s(it.get("url"), 500)
        linked = url.startswith(("http://", "https://"))
        file_id = _s(it.get("file"), 60)
        if it.get("claim_id"):
            # 검증한 명제. 상태에 따라 본문에서 다루는 법이 다르다.
            #
            #   supported   그대로 쓴다
            #   partial     범위를 좁히고 조건을 붙여 쓴다
            #   그 밖       사실로 단정하지 않고 확인 대상으로만 둔다
            #
            # 인용문을 그대로 넘긴다. 요약해서 넘기면 모델이 그 요약을 다시
            # 요약해 원문에서 멀어진다.
            (conf if is_confirmed(it) else unconf).append(_claim_row(it, conf, unconf))
            continue

        if is_confirmed(it):
            row = {"id": f"s{len(conf)}", "title": _s(it.get("title"), 200),
                   "source": _s(it.get("source"), 60),
                   "url": url if linked else "", "file": file_id}
            if file_id:
                # 올린 문서는 본문을 함께 넘긴다. 파일명만 주면 모델이
                # 인용할 것이 없어서 "첨부 자료 참고" 같은 문장만 쓴다.
                row["excerpt"] = _s(it.get("excerpt"), 20000)
            conf.append(row)
        else:
            unconf.append({"id": f"e{len(unconf)}", "kind": _s(it.get("kind"), 60),
                           "title": _s(it.get("title"), 200),
                           "claim_to_verify": _s(it.get("claim_to_verify"), 300),
                           "where_to_look": _s(it.get("where_to_look"), 300)})
    return conf, unconf


def _claim_row(it, conf, unconf) -> dict:
    """명제 하나를 프롬프트가 읽을 모양으로.

    확인된 것과 아닌 것의 모양을 맞춰 둔다 — 다르게 두면 프롬프트가 두 벌의
    규칙을 들어야 하고, 상태가 바뀔 때 한쪽만 고쳐진다.
    """
    ok = is_confirmed(it)
    sid = f"s{len(conf)}" if ok else f"e{len(unconf)}"
    _CID[sid] = it.get("claim_id", "")
    row = {
        "id": sid,
        "kind": "명제",
        "title": _s(it.get("claim"), 300),
        "status": _s(it.get("status"), 20),
        # 자격이 표현의 강도를 정한다. 규정을 기사가 뒷받침하면 뜻은 맞아도
        # "규정이 정한다" 로 쓰면 안 된다.
        "authority": _s(it.get("authority"), 20),
        "claim_type": _s(it.get("claim_type"), 20),
        "limitations": [_s(x, 200) for s_ in (it.get("sources") or [])
                        for x in (s_.get("limitations") or [])][:3],
    }
    if ok:
        src = [s_ for s_ in (it.get("sources") or [])
               if s_.get("status") in ("supported", "partial")]
        first = src[0] if src else {}
        # 참고자료에 실릴 이름. 명제 문장이 아니라 **뒷받침한 원문**이다.
        # 명제를 실으면 "우리가 한 말" 이 출처로 나간다.
        row["ref_title"] = _s(first.get("title"), 200)
        row["source"] = _s(first.get("source_target"), 60)
        row["url"] = _s(first.get("url"), 500)
        # 올린 문서면 어느 쪽을 봤는지까지 남긴다. 참고자료에 문서명만
        # 적으면 읽는 사람이 그 문서 어디를 보라는 것인지 알 수 없다.
        row["file"] = _s(first.get("file"), 40)
        if row["file"]:
            row["evidence_spans"] = [
                {"location": _s(sp.get("location"), 80)}
                for s_ in src for sp in (s_.get("evidence_spans") or [])][:8]
        # 뒷받침하는 대목. 본문이 이것을 근거로 쓴다.
        row["quotes"] = [_s(sp.get("quote"), 600)
                         for s_ in src for sp in (s_.get("evidence_spans") or [])][:3]
        row["unsupported_parts"] = [_s(x, 200) for s_ in src
                                    for x in (s_.get("unsupported_parts") or [])][:3]
    else:
        row["claim_to_verify"] = _s(it.get("claim"), 300)
        row["where_to_look"] = _s(it.get("required_source"), 120)
    return row


def _sections(d):
    """확정된 섹션. order 는 여기서 매긴다 — 소제목을 다시 붙일 열쇠다.

    objective·covers·exclude 는 구조 단계가 소제목을 지을 때 쓴 설계 의도다.
    안 넘기면 본문 작성이 소제목만 보고 내용을 다시 추론하고, 섹션마다 같은
    이야기가 반복된다. 직접 쓴 구조에는 없으므로 빈 값이면 키를 빼서 보낸다 —
    빈 배열을 넘기면 모델이 "다룰 게 없다" 로 읽는다.

    **claim_refs 는 참고가 아니라 계약이다.** 구조가 "이 명제는 여기" 라고
    정해 둔 것이고, 본문이 그것을 무시하면 구조 단계가 한 판단이 사라진다.
    전체 명제는 맥락으로 다 넘기되(`sources_confirmed`), 각 섹션의 핵심
    주장과 인용은 그 섹션의 claim_refs 안에서만 고른다. 코드도 같이 막는다.
    """
    out = []
    for i, s in enumerate(_pay(d, "outline").get("sections", []), 1):
        img = s.get("image") or {}
        comp = figures.component_of(img.get("form"))
        row = {
            "order": i,
            "heading": _s(s.get("title"), 200),
            "figure": {"purpose": _s(img.get("purpose"), 300), "form": comp} if comp else None,
            "claim_refs": [_s(r, 20) for r in (s.get("claim_refs") or [])][:6],
        }
        # 이 섹션이 글에서 하는 일. **본문 프롬프트가 이걸 읽는다** —
        # "role 이 어울리는 맺음을 알려 준다" 고 적어 두고 정작 값을 안
        # 넘기고 있었다. 직접 쓴 구조에는 없으므로 빈 값이면 키째 뺀다.
        if s.get("role"):
            row["role"] = _s(s["role"], 20)
        if s.get("objective"):
            row["objective"] = _s(s["objective"], 200)
        if s.get("covers"):
            row["covers"] = [_s(x, 120) for x in s["covers"]][:5]
        if s.get("exclude"):
            row["exclude"] = [_s(x, 120) for x in s["exclude"]][:5]
        out.append(row)
    return out


def build_input(d):
    """프롬프트에 넘길 것. URL 은 뺀다 — 본문에 URL 을 쓰지 않기 때문이다."""
    atype = _pay(d, "type").get("article_type", "")
    conf, unconf = _split(d)
    return {
        # 채널 규칙. 코드에 분기를 두지 않고 데이터로 넘긴다.
        # 채널 이름과 상한만 넘긴다. 나머지 지침은 채널 프롬프트에 있다.
        "channel": channels.of(channel_of(d)).name,
        # **근거를 얼마나 확보했는지.** 0 이면 본문이 사실을 단정하면 안
        # 된다. 예전에는 sources_confirmed 가 빈 배열인 것을 모델이
        # "근거를 안 줬구나" 로 읽고 스스로 정의를 만들어 채웠다.
        "evidence_state": _evidence_state(d),
        "limits": channels.limits(channel_of(d)),
        "intent": _pay(d, "intent"),
        "title": _pay(d, "title").get("title", ""),
        "topic": _label(d, "topic"),
        "reader": _pay(d, "reader"),
        "angle": _pay(d, "angle"),
        "article_type": atype,
        "type_guide": skeletons.for_write(atype),
        "sections": _sections(d),
        # URL 은 뺀다 — 본문에 URL 을 쓰지 않기 때문이다. file(내부 id)도
        # 뺀다. 모델이 알아야 할 것은 제목·출처·본문이지 저장 이름이 아니다.
        "sources_confirmed": [{k: v for k, v in c.items() if k not in ("url", "file")}
                              for c in conf],
        "evidence_topics": unconf,
    }


# ── 검증 ──────────────────────────────────────────────────────

def _by_order(got):
    """order 로 찾는다. 인덱스로 맞추지 않는다 — LLM 이 순서를 흐트러뜨리거나
    하나를 빠뜨리면 인덱스는 조용히 어긋난 섹션에 본문을 붙인다."""
    out = {}
    for s in got if isinstance(got, list) else []:
        if not isinstance(s, dict):
            continue
        try:
            out[int(s.get("order"))] = s
        except (TypeError, ValueError):
            continue
    return out


# ── 표현 블록 검증 ────────────────────────────────────────────
#
# 섹션 하나가 문단만 갖지 않는다. 번호형 목록·체크리스트·강조 박스가 문단
# 사이 어디에도 올 수 있어야 해서 blocks 배열로 받는다.
#
# 도식의 form 은 여기서 정하지 않는다. 6단계가 확정한 계획에서 온다 —
# 모델이 form 까지 고르면 계획과 어긋난 도식이 나온다. 모델은 caption 과
# data, 그리고 해석 문장만 낸다.

# 강조 박스의 종류. 종류마다 화면에서 모양이 다르다(site/render.py 의 KIND).
# 목록 밖 값은 "핵심" 으로 떨어뜨린다 — 모르는 종류가 오면 스타일이 안 걸려
# 그 박스만 밋밋하게 나가는데, 그건 조용한 어긋남이다.
CALLOUT_LABELS = ("핵심", "주의", "실무 포인트", "정의")


def _list_items(b):
    """번호형 목록. [{title, body}] — 3~5개."""
    out = []
    for x in b.get("items") or []:
        if not isinstance(x, dict):
            continue
        title, body = _para(x.get("title"))[:60], _para(x.get("body"))[:300]
        if title or body:
            out.append({"title": title, "body": body})
    return out[:5] if len(out) >= 2 else []


def _check_items(b):
    """체크리스트. 문항 문자열 — 3~10개."""
    out = [_para(x)[:120] for x in b.get("items") or []]
    out = [x for x in out if x]
    return out[:10] if len(out) >= 3 else []


def _blocks(sec, plan_fig, order, dropped):
    """블록 배열을 조립이 쓸 모양으로.

    모르는 타입, 빈 것, 계획에 없는 도식은 버린다. 도식 하나가 못 쓸
    모양이라고 글 전체를 막지 않는다 — 그 자리만 비고 점검표에 뜬다.
    """
    out, drawn = [], False

    for b in sec.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")

        if t == "para":
            x = _para(b.get("text"))
            if x:
                out.append({"type": "para", "text": x})

        elif t == "list":
            items = _list_items(b)
            if items:
                out.append({"type": "list", "items": items})

        elif t == "check":
            items = _check_items(b)
            if items:
                out.append({"type": "check", "items": items})

        elif t == "callout":
            x = _para(b.get("text"))
            if x:
                label = _para(b.get("label"))
                out.append({"type": "callout",
                            "label": label if label in CALLOUT_LABELS else "핵심",
                            "text": x[:200]})

        elif t == "figure":
            # 계획에 없는 자리에 만들어 왔거나 한 섹션에 둘 이상이면 버린다.
            if not plan_fig or drawn:
                continue
            fig = figures.figure(plan_fig["form"], b.get("caption"), b.get("data"))
            if fig:
                drawn = True
                out.append({"type": "figure", **fig,
                            "takeaway": _para(b.get("takeaway"))[:200]})

    if plan_fig and not drawn:
        dropped.append(order)
    return out


# 무엇을 하라고 권하는 말. 이런 문장은 무엇을 보라고까지 적어야 한다.
ACTIONS = ("확인", "점검", "관리", "연결", "구분", "검토", "정리", "비교",
           "파악", "대조", "판단")

# 무엇을 어떤 기준으로 보는지 알려 주는 말.
MARKERS = ("시스템", "자료", "원천", "출처", "증빙", "기록", "문서", "값",
           "기간", "보고기간", "연도", "시점", "일정",
           "범위", "경계", "조직", "제품", "공정", "품목", "부서", "채널",
           "단위", "기준", "산정", "방식", "코드", "이름", "지점",
           "승인", "책임", "누가",
           "완료", "상태", "결과", "예외", "조건", "업무")

# 행동 문장 하나에 이만큼은 있어야 한다.
NEED = 2

# 이 아래로 짧으면 안 센다. "다시 확인합니다" 같은 이음말까지 잡으면
# 잡음이 는다. 다만 "원천 데이터를 확인합니다"(14자)는 잡아야 하므로
# 낮게 둔다.
MIN_LEN = 12


def vague(text: str) -> bool:
    """무엇을 하라고만 하고 무엇을 보라고는 안 하는 문장인가.

    **"확인합니다" 로 끝나는 문장은 아무것도 안 알려 준다.** 독자는 이미
    확인해야 한다는 걸 알고 있고, 무엇을 어떤 기준으로 보는지를 모른다.
    실제로 네이버 글이 이런 문장으로 채워져 나왔다.

        원천 데이터를 확인합니다.
        담당 부서를 정해 관리해야 합니다.

    **사실을 설명하는 문장은 안 본다.** "전환기간에는 분기별 보고가
    적용됩니다" 는 무엇을 하라는 말이 아니므로 짧아도 된다. 행동을 권하는
    문장에만 붙는 규칙이다.
    """
    t = (text or "").strip()
    if len(t) < MIN_LEN or not any(v in t for v in ACTIONS):
        return False
    # 행동 동사가 붙은 말은 표시로 안 센다. "담당 부서를 정해 관리한다" 의
    # `담당` 은 무엇을 볼지 알려 주는 것이 아니라 행동 그 자체다.
    hit = {m for m in MARKERS if m in t}
    return len(hit) < NEED


# 무엇이 뭔지 안 풀고 넘어가는 말. 이런 말을 쓰면 그게 무엇인지 함께
# 적어야 한다.
LOOSE = ("구간", "형식", "상태", "체계", "기준으로", "방식으로",
         "관련 자료", "관련 정보", "해당 항목", "필요한 자료", "필요한 정보")

# 그 말이 무엇인지 **바로 뒤에서** 풀었다는 표시.
#
# 쉼표나 "어느" 같은 의문사는 표시가 못 된다 — "우리 자료가 요청 형식과
# 맞는지, 두 가지입니다" 처럼 풀지 않고도 붙는다. 실제로 나열하거나
# 예시를 드는 말만 본다.
UNFOLD = ("포함", "예를", "구체적", "다음", "아래", "곧", "즉",
          "·", "：", ":", "—", "등의", "같은")

# 그 말 **바로 뒤** 이만큼 안에서 푼 것만 본다. 멀리 있는 말은 다른
# 이야기다 — "관련 자료를 모아 두면 다음에 찾기 쉽습니다" 의 `다음` 은
# 자료를 푸는 말이 아니다.
NEAR = 14


def loose(text: str) -> bool:
    """무엇인지 안 풀고 넘어간 말이 있는가.

    **"요청 형식과 맞는지 확인합니다" 는 형식이 뭔지 안 알려 준다.**
    `vague()` 는 이걸 통과시킨다 — `자료` · `형식` 이 표시로 잡히기
    때문이다. 표시는 있는데 **그 표시가 가리키는 것이 안 풀린** 경우다.

        ✗  거래처가 어느 의무 구간에 있는지, 우리 자료가 요청 형식과 맞는지
        ✓  거래처의 수입량이 기준을 넘는지, 요청 양식에 CN 코드·설비 정보·
           보고기간이 포함되는지

    뒤에 목록이나 예시가 붙으면 푼 것으로 본다.
    """
    t = (text or "").strip()
    if len(t) < MIN_LEN:
        return False
    # 나열이 있으면 푼 것으로 본다. "CN 코드, 설비명, 보고기간" 처럼
    # 항목을 늘어놓는 것이 곧 무엇인지 적는 것이다.
    if t.count(",") >= 2 or t.count("·") >= 2:
        return False
    for w in LOOSE:
        i = t.find(w)
        if i < 0:
            continue
        # 그 말 앞뒤로 무엇인지 풀었나. 같은 문장 안에서만 본다.
        # **뒤만 본다.** 앞에 무엇이 있든 그 말을 푸는 것은 뒤에 온다.
        near = t[i:i + len(w) + NEAR]
        if not any(u in near for u in UNFOLD):
            return True
    return False


# 출처를 흐리게 적는 말. 어디를 봐야 하는지 안 알려 준다.
BLURRY = ("관련 보도", "일부 자료", "업계에서", "일각에서", "전문가들은",
          "알려진 바", "전해진다", "여러 자료", "관련 자료에 따르면")


def blurry(text: str) -> bool:
    """출처를 뭉뚱그렸는가.

    `관련 보도에서` 는 어디를 봐야 하는지 안 알려 준다. **출처를 흐리게
    적는 것은 없는 근거를 있는 것처럼 보이게 한다.** 인용할 자료가 있으면
    cites 로 달고, 없으면 그 문장을 안 쓰는 것이 맞다.
    """
    return any(w in (text or "") for w in BLURRY)


def figure_ahead(section) -> list[str]:
    """도식이 본문에 없는 기준을 드는가.

    본문이 셋을 짚는데 도식에 다섯이 들어가면 **읽는 사람은 나머지 둘을
    어디서 확인해야 할지 모른다.** 도식과 본문이 따로 움직인다.

    확실히 못 가른다 — 같은 뜻을 다른 말로 쓸 수 있다. 낱말 겹침으로
    보고 표시만 한다.
    """
    from .. import sanitize as z
    text = " ".join(t for b in (section.get("blocks") or [])
                    if b.get("type") != "figure" for t in _texts(b))
    if not text:
        return []
    said = z.stems(text)
    out = []
    for b in (section.get("blocks") or []):
        if b.get("type") != "figure":
            continue
        for k in _figure_keys(b.get("data") or {}):
            w = z.stems(k)
            # **기준의 낱말이 본문에 있는지**로 본다. 겹침 비율로 보면 본문이
            # 길수록 늘 낮게 나와서 전부 걸린다.
            if w and len(w & said) / len(w) < AHEAD:
                out.append(k)
    return out


# 기준의 낱말이 이만큼은 본문에 있어야 한다.
AHEAD = 0.5


def _figure_keys(d) -> list[str]:
    """도식이 드는 기준 이름. 형식마다 자리가 다르다."""
    out = [r.get("criterion", "") for r in (d.get("rows") or [])]
    out += [c.get("title", "") for c in (d.get("cards") or [])]
    out += [s_.get("title", "") for s_ in (d.get("steps") or [])]
    root = d.get("root") or {}
    out += [k.get("label", "") for k in (root.get("children") or [])]
    return [x for x in out if x]


def vague_rows(sections) -> list[dict]:
    """구체 기준이 모자란 문장을 모은다. 지우지는 않는다.

    이미 만들어진 본문을 코드가 다시 쓸 수는 없고, 정당한 경우도 있다.
    어느 문장을 손볼지 알려 주는 것까지가 코드 몫이다.
    """
    out = []
    for s_ in sections:
        for b in (s_.get("blocks") or []):
            for t in _texts(b):
                if vague(t):
                    out.append({"heading": s_.get("heading", ""), "text": t,
                                "why": "무엇을 볼지 안 적음"})
                elif blurry(t):
                    out.append({"heading": s_.get("heading", ""), "text": t,
                                "why": "출처를 뭉뚱그림"})
                elif loose(t):
                    out.append({"heading": s_.get("heading", ""), "text": t,
                                "why": "무엇인지 안 풀었음"})
    return out


def _texts(b) -> list[str]:
    """블록 하나가 든 문장들. 문단·목록·체크·강조를 다 본다."""
    t = (b or {}).get("type")
    if t in ("para", "callout"):
        return [b.get("text") or ""]
    if t == "check":
        return [str(x) for x in (b.get("items") or [])]
    if t == "list":
        return [f'{x.get("title", "")} {x.get("body", "")}'.strip()
                for x in (b.get("items") or []) if isinstance(x, dict)]
    if t == "figure":
        return [b.get("takeaway") or ""]
    return []


def shape_of(section) -> str:
    """이 섹션이 무엇으로 끝나나. 읽는 사람이 느끼는 리듬이다.

    마지막 블록을 보는 이유는, 섹션을 다 읽고 넘어갈 때 남는 인상이
    그것이기 때문이다. 셋이 연속으로 같으면 글이 평평해진다.
    """
    blocks = section.get("blocks") or []
    for b in reversed(blocks):
        t = (b or {}).get("type")
        if t in ("list", "check", "callout", "figure"):
            return t
    return "para"


def flat_run(sections) -> list[str]:
    """같은 모양으로 끝나는 섹션이 **연속으로 셋 이상** 이어지는가.

    프롬프트에 "list 다음에 바로 list 를 놓지 않습니다" 가 있었지만 그건
    **한 섹션 안의 규칙**이라, 섹션을 건너뛴 반복은 아무도 안 봤다. 실제로
    섹션 셋이 전부 번호형 목록으로 끝난 글이 나왔다.

    막지 않는다. 정당한 경우가 있고, 이미 만들어진 본문을 코드가 다시 쓸
    수는 없다. 발행 전 확인 목록이 짚는다.
    """
    out, run, prev = [], 0, None
    for s_ in sections:
        t = shape_of(s_)
        run = run + 1 if t == prev else 1
        prev = t
        if run >= 3 and t not in out:
            out.append(t)
    return out


def _allowed(p, cite_ids):
    """이 섹션이 인용할 수 있는 id. 배치가 없으면 None(제한 없음).

    구조가 `claim_refs` 를 안 남긴 섹션(직접 쓴 구조가 그렇다)까지 막으면
    인용이 통째로 사라진다. 그때는 지금까지처럼 확인된 것 전부를 연다.
    """
    refs = p.get("claim_refs") or []
    if not refs:
        return None
    return {c for c in cite_ids if _cid_of(c) in refs}


def _cid_of(source_id: str) -> str:
    """본문이 쓰는 출처 id(s0·s1…) → 그것이 가리키는 명제 id."""
    return _CID.get(source_id, "")


# source_id → claim_id. _split() 이 채운다. 본문 출력의 cites 는 s0 같은
# 짧은 id 라서 어느 명제인지 여기서 되돌린다.
_CID: dict[str, str] = {}


def check(got, plan, cite_ids, channel="site"):
    """받은 것을 조립이 쓸 모양으로. 못 쓰면 LLMError.

    섹션이 하나라도 비면 올린다. 구멍 난 글이 조용히 나가는 것보다
    다시 부르는 게 낫다.
    """
    hit = _by_order(got.get("sections"))
    missing = [p["order"] for p in plan if p["order"] not in hit]
    if missing:
        raise llm.LLMError(f"본문에 빠진 섹션이 있다: {missing}")

    dropped = []
    out = []
    for p in plan:
        s = hit[p["order"]]

        # 미확인 근거는 인용할 수 없다. 프롬프트로 막았지만 코드에서도 막는다 —
        # 확인 안 된 것에 출처가 붙는 게 이 파이프라인의 오래된 실패다.
        cites = [c for c in (s.get("cites") or []) if c in cite_ids]
        # 구조가 정한 배치를 벗어난 인용도 뺀다. claim_refs 는 참고가 아니라
        # 계약이다 — 벗어나면 구조 단계가 한 판단이 사라진다.
        allow = _allowed(p, cite_ids)
        if allow is not None:
            off = [c for c in cites if c not in allow]
            if off:
                dropped.append(f"{p['order']}번 섹션: 배치 밖 인용 {len(off)}건")
            cites = [c for c in cites if c in allow]
        row = {"order": p["order"], "heading": p["heading"], "cites": cites}

        if isinstance(s.get("blocks"), list) and s["blocks"]:
            blocks = _blocks(s, p["figure"], p["order"], dropped)
            if not any(b["type"] == "para" for b in blocks):
                raise llm.LLMError(f"{p['order']}번 섹션에 문단이 없다")
            row["blocks"] = blocks
        else:
            # blocks 를 못 받았을 때. 프롬프트가 흔들려도 글이 통째로
            # 막히지는 않게 옛 형식을 그대로 받는다.
            paras = [x for x in (_para(t) for t in s.get("paragraphs") or []) if x]
            if not paras:
                raise llm.LLMError(f"{p['order']}번 섹션 본문이 비었다")
            fig = None
            if p["figure"]:
                raw = s.get("figure") or {}
                fig = figures.figure(p["figure"]["form"],
                                     raw.get("caption"), raw.get("data"))
                if not fig:
                    dropped.append(p["order"])
            row["paragraphs"] = paras
            row["figure"] = fig

        out.append(row)

    return {"lead": _para(got.get("lead")), "sections": out, "dropped_figures": dropped}


def run(d, inp=None):
    """본문 한 벌. 확정값을 받아 검증까지 끝난 것을 준다.

    inp 를 받는 이유는 실패했을 때도 "무엇을 넣었는지"를 남겨야 하기
    때문이다. 부르는 쪽이 먼저 만들어 두고 넘긴다.
    """
    inp = inp or build_input(d)
    ch = channel_of(d)
    # 본문은 고를 여지 없이 나온 그대로 나가므로 상위 등급을 쓴다.
    got = llm.generate(prompt_of(ch), inp, strong=True)
    conf, unconf = _split(d)
    res = check(got, inp["sections"], {c["id"] for c in conf}, ch)
    res["sources"] = conf          # URL 은 조립이 쓴다
    res["unverified"] = unconf     # 결과물이 아니라 발행 전 확인 목록으로 간다
    return res, inp
