"""근거로 쓸 PDF 받기.

7단계 프롬프트는 검색을 하지 않는다. 그래서 URL 이 붙은 확인된 출처는 소재에
딸려온 기사뿐이고, 나머지는 "무엇을 어디서 확인할지" 까지만 정해진 대상이다.
사람이 원문 PDF 를 직접 올리면 그 자리가 메워진다 — **기사보다 확실한 근거다.**

그래서 올린 문서는 확인된 출처로 다룬다. 다만 URL 이 없으므로 참고자료에는
링크가 아니라 문서명으로 나간다.

**파일명만 받으면 근거가 아니라 장식이다.** 본문 작성이 그 안을 봐야 인용할
수 있으므로 올리는 순간 텍스트를 뽑아 둔다. 전문을 프롬프트에 실으면 입력이
터지므로 발췌 길이를 자른다.

pypdf 를 쓴다. pdftotext 가 여러 단 문서에 더 낫지만 poppler 설치가 필요하고,
이 서버는 윈도라 파이썬만으로 되는 쪽을 고른다.

스캔본은 글자 층이 없어서 아무것도 안 나온다. 그때는 조용히 빈 문서를 만들지
않고 이유를 올린다 — 올렸는데 근거로 안 쓰이면 사람이 알 방법이 없다.
"""

import hashlib
import re
import uuid

from ... import paths, sanitize as z

# 20MB. 실무 문서는 대개 이 아래고, 넘는 것은 스캔본이라 어차피 글자가 없다.
MAX_BYTES = 20 * 1024 * 1024

# ── 글자 수 상한 ──────────────────────────────────────────────
#
# 파일 크기로는 무게를 못 잰다. 조밀한 30쪽이 성긴 200쪽보다 무겁다.
# 그래서 글자 수로 재고, 쪽 수는 세지 않는다.
#
# **자르지 않고 거절한다.** 앞부분만 쓰거나 앞머리를 줄여 실으면, 실패했을 때
# 그게 문서 탓인지 신호가 얇아서인지 사람이 구별할 수 없다. 거절하면 그
# 자리에서 안다. 그리고 잘라 넘긴 문서가 카드에 "출처 확인됨" 으로 뜨는 것이
# 이 파이프라인에서 이미 한 번 났던 사고다.
#
# 두 수 다 **재서 정한 값이 아니다.** 실제 규정 원문이 쪽당 2,000~3,000자쯤
# 되므로 대략 150~200쪽에서 걸린다고 보고 잡았다. 거절은 choice/ 에 남으므로,
# 몇 자짜리가 얼마나 자주 걸리는지 쌓인 다음에 조정한다.

MAX_CHARS = 400_000     # 문서 전체 글자 수

# 쪽 고르기 프롬프트에 실릴 쪽 목록의 글자 수. 쪽 수 × PEEK 로 어림잡지 않고
# 실제로 실릴 만큼(min(쪽 글자수, PEEK))을 센다 — 짧은 쪽이 많으면 훨씬 작다.
MAX_LIST = 60_000

# 쪽마다 보여 줄 앞부분. pick.py 가 쪽 목록을 만들 때 쓴다. 여기 두는 이유는
# 목록 크기를 재는 곳이 여기라서다. pick 에 두고 가져오면 순환 import 가 된다.
PEEK = 300

# 한 문서에서 프롬프트로 넘길 글자 수. 넘는 만큼은 저장만 해 둔다.
EXCERPT = 6000

# 후보 카드에 보일 요약.
PREVIEW = 200

MAGIC = b"%PDF-"


class UploadError(Exception):
    """받을 수 없는 파일. 화면에 이유가 그대로 뜬다."""


def _clean_name(name: str) -> str:
    """화면에 보일 이름. 저장 이름으로는 쓰지 않는다.

    저장은 우리가 만든 id 로 한다 — 사용자가 준 이름을 경로에 쓰면
    ../ 하나로 폴더 밖에 쓸 수 있다.
    """
    base = re.sub(r"[\\/\x00-\x1f]", "", name or "")
    # 앞의 점을 턴다. 저장 이름은 우리가 만든 id 라 위험하지는 않지만,
    # 이 이름이 payload 의 source 로 들어가 참고자료에 그대로 나간다.
    base = base.strip().lstrip(". ").strip()
    return (base or "문서.pdf")[:120]


def _folder(sid: str):
    d = paths.UPLOADS / (re.sub(r"[^0-9a-zA-Z]", "", sid or "") or "nosid")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pages(path) -> list[str]:
    """PDF 에서 쪽별로 글자를 뽑는다.

    통째로 이어 붙이지 않는 이유는, 긴 문서에서 **어느 쪽을 쓸지** 골라야
    하기 때문이다. 이어 붙인 뒤에는 되돌릴 수 없다.
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise UploadError("pypdf 가 없다. pip install -r requirements.txt") from e

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")          # 빈 암호로 열리는 것이 흔하다
            except Exception:
                raise UploadError("암호가 걸린 PDF 입니다")
        raw = [(p.extract_text() or "") for p in reader.pages]
    except UploadError:
        raise
    except Exception as e:
        raise UploadError(f"PDF 를 읽지 못했습니다: {e}") from e

    return [clean(t) for t in raw]


def clean(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t or "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


# 쪽마다 반복되면 머리글로 본다. 9쪽짜리에서 4쪽 이상 같으면 내용이 아니다.
HEADER_RATIO = 0.4


def _line(t: str) -> str:
    return " ".join((t or "").strip().split())


def _noise(line: str) -> bool:
    """쪽 이름으로 못 쓰는 줄.

    쪽 번호, 기준일만 있는 줄, 너무 짧은 줄. 이런 것이 목록에 뜨면
    사람이 어느 쪽에 무엇이 있는지 알 수 없다.
    """
    if len(line) < 5:
        return True
    if re.fullmatch(r"[-–—]?\s*\d+\s*[-–—/]?\s*\d*", line):
        return True
    if re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\s*(기준|현재)?$", line):
        return True
    return False


def headers(pages) -> set:
    """쪽마다 되풀이되는 줄. 머리글·꼬리말이다.

    **한 쪽만 봐서는 머리글인지 알 수 없다.** 문서 전체에서 같은 줄이
    여러 쪽에 나오는지 세야 안다. 실제로 9쪽짜리 가이드를 올렸더니 근거
    구간 목록이 이렇게 나왔다.

        4쪽  EU CBAM 본격 시행 대응 가이드 | 2026.08.06 기준
        5쪽  EU CBAM 본격 시행 대응 가이드 | 2026.08.06 기준

    쪽마다 같은 문구라 **어느 쪽에 무엇이 있는지 알 수 없다.**
    """
    from collections import Counter
    tops = []
    for t in pages:
        lines = [_line(x) for x in (t or "").splitlines()]
        lines = [x for x in lines if x]
        # 위아래 두 줄씩 본다. 꼬리말도 같은 문제를 낸다.
        tops += lines[:2] + lines[-2:]
    if not tops:
        return set()
    need = max(2, int(len(pages) * HEADER_RATIO))
    return {line for line, n in Counter(tops).items() if n >= need}


def head(t: str, n: int = 110, skip=()) -> str:
    """그 쪽이 무엇을 다루는지 한 줄. 머리글은 건너뛴다."""
    for raw in (t or "").splitlines():
        line = _line(raw)
        if not line or line in skip or _noise(line):
            continue
        return line[:n]
    return z.s((t or "").replace("\n", " "), n)


def list_chars(pages) -> int:
    """쪽 목록이 프롬프트에 실릴 때의 글자 수."""
    return sum(min(len(p), PEEK) for p in pages if p)


def save(sid: str, filename: str, data: bytes) -> dict:
    """파일 하나를 받아 문서 한 건으로 만든다.

    검증에 걸리면 파일을 남기지 않는다. 못 쓸 파일이 폴더에 쌓이면
    나중에 지우는 사람이 무엇을 지워도 되는지 알 수 없다.
    """
    name = _clean_name(filename)
    if not name.lower().endswith(".pdf"):
        raise UploadError("PDF 파일만 받습니다")
    if not data:
        raise UploadError("빈 파일입니다")
    if len(data) > MAX_BYTES:
        raise UploadError(f"파일이 큽니다 ({len(data)//1024//1024}MB · 최대 20MB)")
    # 확장자는 바꿔 달 수 있다. 앞머리를 본다.
    if not data.startswith(MAGIC):
        raise UploadError("PDF 가 아닙니다")

    doc_id = uuid.uuid4().hex[:12]
    f = _folder(sid) / f"{doc_id}.pdf"
    f.write_bytes(data)

    try:
        pages = _pages(f)
    except UploadError:
        f.unlink(missing_ok=True)
        raise

    body = "\n".join(p for p in pages if p).strip()
    if not body:
        f.unlink(missing_ok=True)
        raise UploadError(
            "글자를 뽑지 못했습니다. 스캔한 문서로 보입니다 — "
            "글자가 선택되는 PDF 여야 근거로 쓸 수 있습니다")

    # 글자 수 상한. 크기 검사와 달리 글자를 뽑아 봐야 알 수 있어서 여기 있다.
    # 넘으면 파일을 지운다 — 못 쓸 파일을 남기지 않는 것은 위와 같은 이유다.
    too = _too_big(len(body), list_chars(pages))
    if too:
        f.unlink(missing_ok=True)
        raise UploadError(too)

    # 여기서는 발췌를 정하지 않는다. 어느 쪽을 쓸지는 확정된 제목·소제목을
    # 봐야 알 수 있어서 pick.narrow() 가 이어서 채운다.
    return {
        "id": doc_id,
        "name": name,
        "title": name.rsplit(".", 1)[0][:120],
        "pages": len(pages),
        "bytes": len(data),
        "chars": len(body),
        # 내용 지문. id 는 올릴 때마다 새로 나므로 같은 문서를 두 번 올렸는지
        # 알 수 없다. 로그에서 "이 파일이 그 파일인가" 를 이걸로 맞춘다.
        "sha": hashlib.sha256(data).hexdigest()[:12],
        "pages_text": pages,
    }


def _too_big(chars: int, listed: int) -> str:
    """상한을 넘었으면 사람이 다음에 뭘 하면 되는지까지 적은 사유. 아니면 빈 문자열.

    막다른 길로 두지 않는다. 800쪽 규정을 근거로 쓰고 싶은 것은 정당한
    요구이고, 실제로 노리는 것은 그중 특정 장 하나다. 쪼개 올리면 쪽 목록이
    짧아져 모델이 더 정확히 고른다 — 더 나은 근거가 되기도 한다.
    """
    tail = " 필요한 장만 나눠 올리면 근거로 쓸 수 있습니다."
    if chars > MAX_CHARS:
        return (f"문서가 깁니다 ({chars:,}자 · 최대 {MAX_CHARS:,}자)." + tail)
    if listed > MAX_LIST:
        return (f"쪽이 많습니다 (목록 {listed:,}자 · 최대 {MAX_LIST:,}자)." + tail)
    return ""


# ── 드래프트에 붙여 두기 ──────────────────────────────────────
#
# 세션 메모리에 둔다. 파일은 디스크에 있지만 목록은 드래프트에 있어서
# 소재를 바꾸면 같이 비워진다 — 다른 글의 근거가 딸려 오지 않는다.

KEY = "_docs"


def docs(draft) -> list[dict]:
    return draft.setdefault(KEY, [])


def add(draft, doc) -> dict:
    docs(draft).append(doc)
    return doc


def remove(draft, doc_id: str, sid: str) -> bool:
    rows = docs(draft)
    hit = next((d for d in rows if d["id"] == doc_id), None)
    if not hit:
        return False
    rows.remove(hit)
    (_folder(sid) / f"{doc_id}.pdf").unlink(missing_ok=True)
    return True


HEAVY = ("excerpt", "pages_text")


def listed(draft) -> list[dict]:
    """화면에 보일 목록. 본문은 빼고 준다 — 목록 한 번에 수백 KB 가 된다."""
    return [{k: v for k, v in d.items() if k not in HEAVY} for d in docs(draft)]


def brief(draft) -> list[dict]:
    """프롬프트 입력에 실을 요약. 무엇이 이미 첨부됐는지 알려 준다.

    preview 는 **골라 낸 구간의 앞부분**이다. 문서 앞머리를 쓰면 표지와
    목차가 실려서, 프롬프트가 "이미 첨부된 것" 을 판단할 근거가 없어진다.
    실제로 사람이 방금 올린 규정을 "규정 원문에서 확인할 것" 으로 다시
    내놓는 일이 있었다.

    발췌 전문은 넣지 않는다. 7단계는 "무엇을 확인할지" 를 정하는 자리라
    문서를 다 읽을 필요가 없고, 넣으면 매 호출에 수십 KB 가 실린다.
    """
    return [{"title": d["title"],
             "sections": [s["head"] for s in d.get("segments") or []],
             "preview": d.get("preview", "")} for d in docs(draft)]
