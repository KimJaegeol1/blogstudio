"""세션과 드래프트 상태.

여기는 HTTP도 화면도 모른다. 상태를 들고 있고 바꾸는 것만 한다.
저장은 메모리다. 나중에 파일이나 DB로 갈아끼울 때 이 모듈만 바뀐다.
"""

import json
import time
import uuid

from . import llm, steps
from .output import hero as heromaker, illust as illustmaker
from .output import write as writer
from .record import feedback as fb
from .record import choice as rec_choice
from .record import response as rec
from .data import fake

COOKIE = "bs_sid"

_sessions: dict[str, dict] = {}


def new_sid() -> str:
    return uuid.uuid4().hex


def get(sid: str | None) -> tuple[str, dict]:
    """세션 하나를 꺼낸다. 없으면 만든다."""
    sid = sid or new_sid()
    st = _sessions.setdefault(sid, {
        "sid": sid,        # 자취를 남길 때 쓴다
        "topic": None,     # 고른 소재 id
        "custom": None,    # 직접 쓴 소재
        "source": None,    # picked | written | recommended
        "evals": {},       # {topic_id: {verdict, tags[], note}}
        "draft": {},       # 2~8단계 확정값
    })
    return sid, st


# ── 1단계 ──────────────────────────────────────────────────────

def topics(st: dict, state: str = "normal") -> list[dict]:
    """소재 목록에 이 세션의 평가를 얹어서 준다."""
    out = fake.load_topics(state)
    for t in out:
        e = st["evals"].get(t["topic_id"])
        t["verdict"] = e["verdict"] if e else None
        t["tags"] = e["tags"] if e else []
        t["note"] = e["note"] if e else ""
    return out


def recommended(items: list[dict]) -> dict | None:
    """아무것도 안 고르면 여기로 간다. 제외한 건 건너뛴다."""
    alive = [t for t in items if t.get("verdict") != "down"]
    return min(alive, key=lambda t: t.get("rank", 999)) if alive else None


def evaluate(st: dict, topic_id: str, verdict: str, tags: list[str], note: str) -> None:
    """1단계 소재 평가. 화면 상태에도 반영된다."""
    note = (note or "").strip()
    if verdict == "none" and not note and not tags:
        st["evals"].pop(topic_id, None)
    else:
        st["evals"][topic_id] = {
            "verdict": None if verdict == "none" else verdict,
            "tags": tags,
            "note": note,
        }
    # 제외한 소재가 선택돼 있으면 선택을 푼다.
    if verdict == "down" and st["topic"] == topic_id:
        st["topic"] = None
        st["source"] = None


# ── 평가 저장 ──────────────────────────────────────────────────

def _evaluated(d: dict, step: str, option_id: str) -> tuple[dict | None, dict | None]:
    """평가 대상이 무엇이었는지와, 그것을 만들 때 프롬프트에 넣은 입력.

    후보 id 는 세션 한정 임시 번호다. 내용을 함께 남기지 않으면 나중에
    p0 가 무엇이었는지 알 수 없다. 캐시에 둘 다 들어 있으니 꺼내 쓴다.
    """
    if step == "result":
        # 결과물은 고른 것들의 합이다. 무엇을 정해서 여기까지 왔는지 남긴다.
        return ({k: v.get("label") for k, v in d.items()
                 if isinstance(v, dict) and "label" in v}, None)

    hit = d.get("_opts", {}).get(step)
    if not hit:
        return None, None
    opt = next((o for o in hit["items"] if o["id"] == option_id), None)
    try:
        inp = json.loads(hit["sig"])
    except (TypeError, ValueError):
        inp = None
    return opt, inp


def feedback(st: dict, sid: str, step: str, option_id: str,
             verdict: str, tags: list[str], note: str) -> None:
    """평가 한 건을 파일로 남긴다. 1단계는 화면 상태도 같이 바꾼다."""
    tags = [x for x in (tags or []) if x]
    note = (note or "").strip()

    if step == "topic":
        evaluate(st, option_id, verdict, tags, note)
        t = fake.find_topic(option_id)
        opt = {"topic_title": t["topic_title"]} if t else None
        inp = None
    else:
        opt, inp = _evaluated(st["draft"], step, option_id)

    fb.record(
        sid=sid, step=step, option_id=option_id,
        verdict=verdict if verdict in ("up", "down") else None,
        tags=tags, note=note,
        option=opt, prompt_input=inp,
        model=llm.model_for(steps.BY_KEY[step].strong)
              if llm.ENABLED and steps.uses_llm(step) else "",
    )


def pick_topic(st: dict, topic_id: str | None, custom: str | None) -> bool:
    """소재를 확정한다. 직접 쓴 게 있으면 그게 이긴다."""
    custom = (custom or "").strip()
    st["custom"] = custom or None
    offered = topics(st)                       # 그 순간 화면에 있던 목록

    if custom:
        st["topic"] = None
        st["source"] = "written"
    elif topic_id:
        st["topic"] = topic_id
        st["source"] = "picked"
    else:
        rec = recommended(offered)
        if not rec:
            return False
        st["topic"] = rec["topic_id"]
        st["source"] = "recommended"

    _record_topic(st, offered, custom)
    return True


def _record_topic(st: dict, offered: list[dict], custom: str) -> None:
    """1단계도 다른 단계와 같은 모양으로 남긴다.

    소재는 LLM 이 만든 게 아니라 시트에서 오므로 생성 시점이 따로 없다.
    그래서 고르는 순간에 "그때 이 목록이 있었다"와 "이걸 골랐다"를 나란히
    남긴다. 2~7단계와 행 모양이 같아야 나중에 같은 방법으로 읽는다.

    점수와 근거기사는 왜 그걸 골랐는지 판단하는 재료라 목록째 남긴다.
    """
    sid = st.get("sid", "")
    items = [{"id": t["topic_id"], "title": t["topic_title"],
              "summary": t.get("topic_summary", ""),
              "meta": f"점수 {t.get('final_score')} · 근거기사 {len(t.get('sources') or [])}건",
              "payload": t}
             for t in offered]
    rec.generated(sid, "topic", {}, items,
                    model="", source="sheet", refresh=False, ms=0)

    hit = next((t for t in offered if t["topic_id"] == st["topic"]), None)
    rec_choice.confirmed(
        sid, "topic", items,
        [st["topic"]] if st["topic"] else [], custom,
        {"label": custom or (hit or {}).get("topic_title", ""),
         "detail": st["source"],
         "payload": hit or {"topic_title": custom}})


# ── 2~8단계 ────────────────────────────────────────────────────

def draft(st: dict) -> dict:
    """1단계에서 고른 소재를 draft 첫 칸에 넣는다.
    소재를 바꾸면 뒤에 쌓아 둔 값은 앞과 안 맞으므로 비운다."""
    d = st["draft"]
    key = st["custom"] or st["topic"]
    if d.get("_key") == key:
        return d

    d.clear()
    d["_sid"] = st.get("sid", "")
    d["_key"] = key
    t = fake.find_topic(st["topic"])
    if t:
        d["topic_id"] = t["topic_id"]
        # 키워드를 소재에 붙여서 넣는다. n8n 4단계(검색 데이터 보강)가 소재에
        # 달아 주는 값인데 지금 공급원에서는 따로 들고 있다. 여기서 합치면
        # 뒤 단계들이 소재 payload 하나만 읽으면 된다 — 다섯 곳이 각자
        # 키워드를 어디서 가져올지 알 필요가 없다.
        payload = {**t, "keywords": fake.load_keywords(t["topic_id"])}
        d["topic"] = {"label": t["topic_title"], "detail": t["topic_summary"],
                      "payload": payload}
    elif st["custom"]:
        d["topic_id"] = None
        d["topic"] = {"label": st["custom"], "detail": "직접 쓴 소재", "payload": {}}
    return d


def need(d: dict) -> str | None:
    """아직 안 정한 첫 단계."""
    for s in steps.order(d):
        if s.key == "approve":
            return None
        if not d.get(s.key):
            return s.key
    return None


def done(d: dict, upto: str | None = None) -> list[dict]:
    """지금까지 정한 것. upto 앞까지만."""
    out = []
    for i, s in enumerate(steps.order(d), 1):
        if upto and s.key == upto:
            break
        v = d.get(s.key)
        if v:
            out.append({"no": i, "key": s.key, "name": s.name,
                        "label": v["label"], "detail": v.get("detail", "")})
    return out


def illust(d: dict) -> dict:
    """본문 그림. 계획된 섹션마다 한 장씩.

    대표 이미지와 따로 두는 이유가 둘이다. 하나는 **없어도 글이 나가는
    것**이라 실패해도 막지 않아야 하고, 하나는 **여러 장**이라 일부만
    성공할 수 있다.

    이미 만든 것은 다시 안 만든다. 나눠 부를 때마다 새로 그리면 사람이
    저장해 둔 그림과 화면의 것이 달라진다.
    """
    return illustmaker.make(d, d.get("_sid", ""))


def hero(d: dict) -> dict:
    """대표 이미지 한 장을 만들어 드래프트에 붙인다.

    본문과 따로 두는 이유는 되돌리기 때문이다. 그림은 보자마자 아니다 싶은
    일이 잦고, 그때 본문까지 다시 만들 이유가 없다. 캐시하지 않는다 —
    다시 부르면 다시 만들고 파일을 덮어쓴다.
    """
    t0 = time.perf_counter()
    sid = d.get("_sid", "")
    inp = heromaker.build_input(d)
    try:
        res = heromaker.make(d, sid)
    except Exception as e:
        # 대표 이미지가 없어도 글은 나간다. 다만 조용히 넘기지 않는다 —
        # 왜 안 나왔는지 화면에 보이지 않으면 사람이 알 방법이 없다.
        rec.failed(sid, "hero", inp, str(e),
                     round((time.perf_counter() - t0) * 1000),
                     raw=llm.raw(f"{writer.channel_of(d)}_hero"))
        raise
    d["hero"] = res
    return res


def write(d: dict) -> dict:
    """본문 한 벌을 만들어 드래프트에 붙인다.

    후보가 아니라 한 벌이므로 캐시하지 않는다. 다시 부르면 다시 만든다 —
    마음에 안 들 때 다시 뽑는 게 이 단계의 유일한 되돌리기다.
    """
    t0 = time.perf_counter()
    sid = d.get("_sid", "")
    model = llm.model_for("write") if llm.ENABLED else ""

    # 입력을 먼저 만들어 둔다. 실패해도 무엇을 넣었는지는 남아야 한다.
    inp = writer.build_input(d)
    try:
        res, _ = writer.run(d, inp)
    except llm.LLMError as e:
        rec.failed(sid, "write", inp, str(e),
                     round((time.perf_counter() - t0) * 1000),
                     raw=llm.raw(writer.prompt_of(writer.channel_of(d))))
        raise

    d["write"] = res
    rec.written(sid, inp, res, model=model,
                  ms=round((time.perf_counter() - t0) * 1000),
                  raw=llm.raw(writer.prompt_of(writer.channel_of(d))))

    # 대표 이미지를 이어서 만든다. 결과물 화면에 처음부터 다 보이는 편이
    # 낫다는 판단이다.
    #
    # 이미 있으면 다시 만들지 않는다. 본문이 마음에 안 들어 다시 뽑는 일은
    # 흔한데, 그때마다 이미지 값이 또 나가면 아깝다. 대표 이미지 계획은
    # 6단계에서 오므로 본문을 다시 써도 그대로 맞다.
    #
    # 실패해도 본문은 나간다. 다만 조용히 넘기지 않는다 — 이유를 남겨
    # 화면에서 볼 수 있게 한다.
    if not d.get("hero"):
        try:
            hero(d)
            d.pop("hero_error", None)
        except Exception as e:
            d["hero_error"] = str(e)

    return res


def confirm(d: dict, key: str, choice: list[str], custom: str):
    """단계 하나를 확정한다.

    성공하면 True, 아니면 **왜 안 됐는지 사유 문자열**을 준다. 예전에는
    False 하나였는데, 그러면 화면이 "빈 입력" 이라고만 말한다 — PDF 를
    올려 두고 아무것도 못 고른 사람에게 그건 틀린 안내다.
    """
    step = steps.BY_KEY[key]
    custom = (custom or "").strip()
    if not step.custom:
        custom = ""                      # 이 단계는 고르기만 받는다

    # 이미 뽑아 둔 후보. 무엇이 주어졌었는지를 자취에 남기려고 먼저 꺼낸다.
    # 캐시에 있으면 다시 만들지 않으므로 직접 쓴 경우에도 값이 더 들지 않는다.
    offered = list(d.get("_opts", {}).get(key, {}).get("items", []))

    if step.multi:
        return _confirm_many(d, step, choice, custom, offered)

    # 하나만 고르는 단계는 둘 중 하나다. 고른 것과 쓴 것을 동시에 확정값에
    # 담을 자리가 없다 — 독자도 각도도 제목도 하나여야 한다.
    if custom:
        # 직접 쓴 값을 쓸 때는 선택지를 만들 필요가 없다. 만들면 후보 생성이
        # 한 번 더 돈다 — 쓰지도 않을 것을 위해.
        v = steps.written(key, custom, d)
        v["choice_ids"] = []
        v["written"] = custom
        d[key] = v
        rec_choice.confirmed(d.get("_sid", ""), key, offered, [], custom, v)
        return True

    opts = {o["id"]: o for o in steps.options(key, d)}
    offered = offered or list(opts.values())
    picked = [opts[c] for c in choice if c in opts]
    if not picked:
        return "empty"

    o = picked[0]
    v = {"label": o["title"], "detail": o["summary"], "payload": o["payload"],
         "choice_ids": [o["id"]], "written": ""}
    d[key] = v
    rec_choice.confirmed(d.get("_sid", ""), key, offered, v["choice_ids"], "", v)
    return True


def warn_of(d: dict, key: str) -> str:
    """이 단계를 고르기 전에 알아야 할 것.

    **결과물을 만든 뒤에 알면 늦다.** 근거가 하나도 없으면 구조도 제목도
    본문도 사실을 담을 수 없는데, 지금까지는 그 사실이 결과물 맨 위에만
    떴다. 사람이 구조를 고를 때 무엇을 감수하는지 알아야 한다.
    """
    if key not in ("outline", "title"):
        return ""
    from .output.write import _evidence_state
    st = _evidence_state(d)
    if st["can_assert"]:
        return ""
    if st["unverified"]:
        return (f"확인된 근거가 없습니다 (확인 필요 {st['unverified']}건). "
                "이 구조로 쓰면 본문이 사실을 단정하지 못하고 "
                "무엇을 확인해야 하는지만 씁니다.")
    return ("근거가 하나도 없습니다. 구조는 소재·독자·각도만 보고 만들어지고, "
            "본문이 사실을 단정하지 못합니다.")


def _auto_claims(d, key, picked) -> list[dict]:
    """검증된 명제는 기본으로 담는다.

    **"안 고름 = 버림" 이 이 단계엔 안 맞는다.** 근거 단계는 "무엇을 쓸지
    고르는" 자리가 아니라 **"확인된 것을 확인하는"** 자리다. 화면이
    `확인됨 · 공식 근거 · 출처 3건` 이라고 표시해 놓고 다음을 누르면
    사라지는 것은 앞뒤가 안 맞는다.

    실제로 그렇게 났다. `supported` 3건 + `partial` 1건을 검증해 놓고
    아무것도 안 고른 채 넘어갔더니 **구조가 받은 claims 가 빈 배열**이었다.
    그래서 글이 근거 없이 추상적으로 나왔다.

    사람이 고른 것이 있으면 그 뜻을 따른다 — 골랐다는 것은 무엇을 쓸지
    직접 정했다는 뜻이다.
    """
    if key != "evidence" or picked:
        return []
    from .steps.evidence import policy
    rows = (d.get("_opts", {}).get(key, {}).get("items") or [])
    return [o["payload"] for o in rows
            if isinstance(o, dict) and o.get("id", "").startswith("claim:")
            and policy.citable(o.get("payload") or {})]


def _confirm_many(d, step, choice, custom, offered) -> bool:
    """여러 개를 담는 단계. **고른 것과 쓴 것을 함께 담는다.**

    하나만 고르는 단계와 다르다. 근거는 성격이 다른 것을 나란히 놓는 자리다 —
    소재에 딸려온 기사, 올린 PDF, 프롬프트가 만든 확인 대상, 사람이 아는
    근거. 이 중 하나만 고르게 하면 나머지는 버려진다. 실제로 PDF 를 올려 놓고
    직접 쓴 근거를 한 줄 더 적으면 문서 쪽이 통째로 사라졌다.

    빈 줄은 written() 이 걸러 낸다. 고른 것도 쓴 것도 없으면 확정하지 않는다.
    """
    key = step.key
    picked = []
    if choice:
        # 고른 것이 있을 때만 후보를 꺼낸다. 직접 쓰기만 했으면 후보 생성이
        # 한 번 더 도는 것을 피한다.
        opts = {o["id"]: o for o in steps.options(key, d)}
        offered = offered or list(opts.values())
        # 고를 수 없다고 표시된 것은 확정에서도 막는다. 화면만 막으면
        # 주소를 직접 쳐서 넘길 수 있고, 그러면 확인 안 된 것이 근거가 된다.
        picked = [opts[c] for c in choice
                  if c in opts and opts[c].get("selectable", True)]

    typed = []
    if custom:
        w = steps.written(key, custom, d)
        typed = (w.get("payload") or {}).get("items") or []

    # 아무것도 안 골랐으면 검증된 명제를 기본으로 담는다. 문서는 여기
    # 안 넣는다 — **문서는 명제가 아니라 명제의 출처다.** 이미 plan 이
    # document_links 로 걸고 check 가 대조해서 그 명제의 sources 에 들어가
    # 있다. 따로 담으면 "문서 제목이 사실인가" 라는 이상한 명제가 생긴다.
    docs = _auto_claims(d, key, picked)

    if not picked and not typed and not docs:
        # **왜 못 넘어가는지 갈라서 알린다.** `empty` 하나로 뭉개면 사람이
        # 무엇을 해야 할지 모른다 — PDF 를 올렸는데 막혔을 때 실제로 그랬다.
        return "no_sources" if offered else "empty"

    rows = [o["payload"] for o in picked] + typed + docs
    titles = ([o["title"] for o in picked]
              + [t.get("title", "") for t in typed if isinstance(t, dict)]
              + [t.get("title", "") for t in docs])

    v = {"label": steps.many_label(key, [{"payload": r} for r in rows]),
         "detail": " / ".join(x for x in titles if x),
         "payload": {"items": rows},
         "choice_ids": [o["id"] for o in picked],
         "written": custom}
    d[key] = v
    rec_choice.confirmed(d.get("_sid", ""), key, offered,
                         v["choice_ids"], custom, v)
    return True
