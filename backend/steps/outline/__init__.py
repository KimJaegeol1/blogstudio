"""8단계 — 본문 구조.

소제목과 이미지 계획을 **한 단계에서 함께** 정한다. 어느 자리에 표가
필요한지는 그 자리에 무엇이 들어가는지 정한 다음에 알 수 있어서, 나눠 놓으면
사람이 두 화면을 왔다 갔다 하며 같은 판단을 두 번 하게 된다.

유형별 권장 골격은 data/skeletons.py 에 데이터로 있다. 여섯 개를 다 실으면
쓰지 않을 골격이 매 호출에 실리고 모델이 그쪽으로 새므로, 해당 유형 하나만
프롬프트 입력에 싣는다.

상위 모델을 쓴다(strong=True). 글 전체의 뼈대라 잘못 잡히면 뒤가 전부
흔들리고, 사람이 소제목 목록만 보고 좋은지 나쁜지 판단하기도 어렵다.

    payload.py   확정값 스키마 · 라벨
    parse.py     직접 쓴 구조 읽기
"""

from ... import llm
from ...data import channels, skeletons
from ..payload import topic_brief, topic_keywords
from ..step import Step, label_of, opt, pay, pick_meta, pick_meta
from . import parse
from .payload import (ROLE_LABELS, detail, label, missing_must, overlap,
                      payload, role_repeat, signature, volume, flow)

# 카드에 적을 이름. 무엇이 모자란지 한눈에 보여야 한다.
# 화면에 나가는 말. 내부 이름(covers · claims)을 그대로 보이지 않는다.
LACK = {"sections": "부분", "covers": "다루는 내용", "claims": "확인된 근거"}

# 키 없이 돌 때 쓰는 구조안. 골격 데이터에서 뽑으므로 따로 적어 두지 않는다.
DEFAULT = ["도입", "핵심 1", "핵심 2", "핵심 3", "마무리"]


def build_input(d) -> dict:
    atype = pay(d, "type").get("article_type", "")
    return {
            # 제목 한 줄만 넘기면 구조가 소재의 범위를 모른다. 같은 제목이라도
            # 요약과 키워드가 다르면 다뤄야 할 것이 다르다.
            "topic": topic_brief(d),
            "reader": pay(d, "reader"),
            "intent": pay(d, "intent"),
            # 프롬프트 이름이 이미 채널을 정한다. 이 값은 규칙을 고르는 데
            # 쓰지 않고 자취에서 무엇으로 돌았는지 보려고 싣는다.
            "channel": pay(d, "channel").get("channel", "site"),
            "angle": pay(d, "angle"), "article_type": atype,
            # 확정된 명제. 무엇을 댈 수 있는지 알아야 구조가 근거 없는
            # 섹션을 만들지 않는다. 제목은 이 뒤에 정해지므로 없다.
            "claims": brief(d),
            # 근거가 어느 쪽으로 쏠려 있는지. 구조를 정하는 값이 아니라
            # 모델이 흐름을 고를 때 보는 요약이다.
            "evidence_shape": evidence_shape(brief(d)),
            # 해당 유형 골격만 싣는다.
            "type_structure": skeletons.for_outline(
                atype, pay(d, "channel").get("channel", "site"))}


# 확인된 명제가 무엇을 말하는지. **구조를 정하는 분류기가 아니라 요약이다** —
# 모델이 이걸 보고 이 글에 맞는 흐름을 스스로 정한다.
SIGNALS = {
    "변화·시점": ("변경", "달라", "이전", "이후", "시행", "종료", "전환", "개정"),
    "주체·책임": ("주체", "책임", "신고인", "담당", "역할", "수행", "제공"),
    "기준·예외": ("기준", "대상", "조건", "면제", "예외", "범위", "판정"),
    "절차·순서": ("절차", "순서", "제출", "준비", "신청", "단계"),
    "자료·산정": ("자료", "데이터", "산정", "증빙", "기록", "계산", "검증"),
    "비교·차이": ("차이", "비교", "반면", "각각", "구분"),
    "일정·기한": ("시점", "기한", "일정", "마감", "까지"),
    "위험·누락": ("위험", "누락", "불일치", "부담", "오류"),
}


def evidence_shape(rows) -> list[str]:
    """확인된 명제가 어느 쪽으로 쏠려 있나.

    **같은 근거로 같은 구조가 나오면 안 된다.** 질문이 책임 변화면 주체
    중심, 준비 자료면 데이터 흐름, 적용 대상이면 기준·예외 흐름이 맞다.
    그런데 지금은 유형 골격이 앞에 있어서 무엇을 물어도 비슷하게 접힌다.

    **분류기가 아니라 요약이다.** 이 값으로 구조를 정하지 않는다 — 모델에
    "지금 근거가 이런 쪽이다" 를 한 줄로 알려 주고, 흐름은 모델이 정한다.
    """
    text = " ".join(f'{r.get("claim", "")} {r.get("why", "")}' for r in rows)
    hit = [(k, sum(1 for w in ws if w in text)) for k, ws in SIGNALS.items()]
    hit = [(k, n) for k, n in hit if n]
    hit.sort(key=lambda x: -x[1])
    return [k for k, _ in hit[:3]]


def brief(d) -> list[dict]:
    """확정된 명제를 구조가 읽을 만큼만 줄인다.

    전문을 실으면 매 호출에 수십 KB 가 실린다. 인용문과 URL 은 본문 작성이
    확정값에서 다시 읽으므로 여기서는 뺀다.

    **상태를 참·거짓으로 접지 않는다.** 예전에는 `confirmed` 하나로 줄였는데,
    그러면 "원문과 어긋남" 과 "아직 못 찾음" 이 같은 값이 된다 — 앞은 쓰면
    안 되는 것이고 뒤는 조건을 붙여 쓸 수 있는 것이다. `claim_id` 도 버려서
    어느 섹션이 어느 명제를 쓰는지 이을 수가 없었다.
    """
    out = []
    for x in pay(d, "evidence").get("items") or []:
        if not isinstance(x, dict):
            continue
        cid, text = x.get("claim_id"), x.get("claim") or x.get("title")
        if not (cid and text):
            # 직접 쓴 근거는 명제가 아니다. 구조가 참조할 id 가 없다.
            continue
        row = {
            "claim_id": cid,
            "claim": text,
            "claim_type": x.get("claim_type", ""),
            "status": x.get("status", ""),
            "authority": x.get("authority", ""),
            "limitations": [z_ for s_ in (x.get("sources") or [])
                            for z_ in (s_.get("limitations") or [])][:3],
            "source_count": len(x.get("sources") or []),
        }
        # **`partial` 은 명제 전문을 그대로 넘기지 않는다.** 원문이 확인해 준
        # 것은 일부인데 전문을 주면 구조가 전체를 확인된 사실로 읽는다.
        # 실제로 "모든 수입에 신고 의무" 가 확인된 것처럼 흘러간 적이 있다 —
        # 원문은 50톤 미만 면제를 함께 말하고 있었다.
        if row["status"] == "partial":
            ok = [p_ for s_ in (x.get("sources") or [])
                  for p_ in (s_.get("supported_parts") or [])][:3]
            if ok:
                row["confirmed_parts"] = ok
            no = [p_ for s_ in (x.get("sources") or [])
                  for p_ in (s_.get("unsupported_parts") or [])][:3]
            if no:
                row["unconfirmed_parts"] = no
        out.append(row)
    return out


def claim_ids(inp) -> set:
    return {c["claim_id"] for c in (inp.get("claims") or [])}


def make(d, inp) -> list[dict]:
    atype = inp.get("article_type")
    cands = (llm.candidates(STEP.prompt_of(inp.get("channel", "")), inp, ("sections",), strong=True)
             if llm.ENABLED
             else [{"sections": skeletons.sections(atype) or DEFAULT}])
    known = claim_ids(inp)
    # 사진·캡처는 네이버만 쓴다. 채널에 안 맞으면 코드가 비운다 — 프롬프트에
    # "쓰지 마라" 를 적어 두어도 안 지키는 날이 있다.
    media_ok = channels.of(inp.get("channel", "site")).media_allowed

    out, seen, flows = [], {}, {}
    for i, c in enumerate(cands):
        p = payload(c["sections"], c.get("hero_image"),
                    known=known, media=media_ok)
        secs = p["sections"]
        if not secs:
            continue
        body = sum(1 for x in secs if x["image"])
        media = sum(1 for x in secs if x.get("media"))
        illus = sum(1 for x in secs if x.get("illustration"))
        hero = 1 if p["hero_image"] else 0

        # 근거 배치가 같으면 소제목만 다른 후보다. 지우지 않고 표시한다 —
        # 지웠다가 후보가 하나만 남으면 화면이 막힌다.
        sig = signature(p)
        twin = seen.get(sig) if any(sig) else None
        if twin is None and any(sig):
            seen[sig] = len(out) + 1

        # 근거 배치가 달라도 설명 흐름이 같으면 독자가 이해하는 경로는
        # 같다. 실제로 소재와 질문이 달라도 "개념 → 목록 → 확인" 으로
        # 접히는 일이 있었다.
        fl = flow(p)
        same_flow = flows.get(fl) if any(fl) else None
        if same_flow is None and any(fl):
            flows[fl] = len(out) + 1

        meta = label(len(secs), body, hero, media, illus)
        if twin is not None:
            meta += f" · {twin}번 후보와 근거 배치가 같음"
        elif same_flow is not None:
            meta += f" · {same_flow}번 후보와 설명 흐름이 같음"
        # 같은 명제를 여러 섹션이 맡으면 같은 설명이 반복된다.
        dup = overlap(p)
        if dup:
            meta += f" · 근거 {len(dup)}건이 여러 섹션에 겹침"
        # 같은 역할이 연달아 셋이면 읽는 리듬이 평평해진다.
        # 이 유형의 뼈대가 빠졌는가. 비교형인데 같은 기준이 없으면
        # 비교가 아니다.
        # 근거가 있는데 구조가 일찍 끝나는가. 실제로 근거 열 묶음에 셋만
        # 쓰고 900자로 끝난 글이 나왔다.
        vol = volume(p, atype, inp.get("channel") or "naver")
        # **구조 문제와 근거 문제를 갈라 적는다.** 한 줄에 섞으면 구조를
        # 바꿔야 하는지 근거를 더 찾아야 하는지 사람이 구분할 수 없다.
        build, evid = [], []

        gap = missing_must(p, (inp.get("type_structure") or {}).get("must_have"))
        if gap:
            build.append(f"{atype}에 필요한 내용 {len(gap)}가지 부족")
        for k, (a, b) in vol["short"].items():
            (evid if k == "claims" else build).append(
                f"{LACK[k]} 현재 {a} / 기준 {b}")
        rep = role_repeat(p)
        if rep:
            names = " · ".join(ROLE_LABELS.get(r, r) for r in rep)
            build.append(f"{names} 중심 부분이 3개 연속")

        if build:
            meta += " · 구성 점검: " + ", ".join(build)
        if evid:
            meta += " · 근거 점검: " + ", ".join(evid)

        why = c.get("rationale") or f"{atype or '유형 미정'} 권장 구조"
        # 첫 후보가 추천이다. 프롬프트가 "질문과 claims 에 가장 직접
        # 답하는 구조를 첫 번째로" 라고 이미 정해 두었다.
        # 펼쳤을 때 **무엇이 빠졌는지** 보인다. 개수만으로는 이 구조를
        # 고를지 판단할 수 없다.
        body = detail(p)
        if gap:
            body += "\n\n빠진 내용 — " + " · ".join(gap[:5])

        out.append(opt(f"o{i}", meta, body,
                       pick_meta(why) if not out else why, p))
    return out


STEP = Step(
    key="outline", name="구조", eyebrow="OUTLINE", h1="구조 선택",
    strong=True,
    hint="소제목을 한 줄에 하나씩.",
    build_input=build_input, make=make, written=parse.read,
    prompt="_prompt.md", by_channel=True,
)
