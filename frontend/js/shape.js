/* 단계별 구조 지식.
 *
 * 어떤 단계는 확정값이 한 줄이 아니다. 구조 단계는 소제목과 이미지 계획을
 * 함께 담으므로, 그것을 펼쳐 보이고, 텍스트로 옮기고, 다시 읽어야 한다.
 * 그 셋이 같은 형식을 다루므로 한 파일에 둔다 — 흩어 놓으면 어긋난다.
 *
 *   detail  payload → 카드 펼침 영역 HTML
 *   text    payload → 직접 쓰기 칸에 붙일 수 있는 문자열
 *   parse   문자열 → 지금 몇 개로 읽혔는지 (표시용)
 *   insert  칸 아래 넣기 버튼
 *
 * 백엔드는 값만 준다. 마크업과 CSS 클래스 이름은 여기 있고 파이썬에는 없다.
 *
 * parse 는 표시용이다. 확정값은 백엔드 options.py 의 같은 규칙 파서가 만든다.
 * 두 곳에 같은 규칙이 있는 것은 알고 있다 — 타이핑마다 서버를 부르지 않고,
 * 프론트가 보낸 값을 믿지도 않기 위한 선택이다. 어긋나도 숫자만 틀리게 보이고
 * 저장되는 값은 백엔드 것이라 데이터가 상하지는 않는다.
 */
window.Shape = (function () {

  /* 부를 때 찾는다. 모듈 로드 순서에 매달리지 않게. */
  function esc(s) { return window.UI.esc(s); }

  var IMG = ['이미지:', '이미지 :'];
  var HERO = ['대표:', '대표 :'];
  /* 긴 대시를 먼저 본다. 짧은 붙임표는 앞뒤 공백이 있을 때만 구분자다 —
   * 안 그러면 "Before-Process-After" 같은 형식 이름이 잘린다. */
  var DASH = ['—', '–', ' - '];

  function after(s, list) {
    for (var i = 0; i < list.length; i++) {
      if (s.indexOf(list[i]) === 0) return s.slice(list[i].length);
    }
    return null;
  }

  function split(s) {
    for (var i = 0; i < DASH.length; i++) {
      var at = s.indexOf(DASH[i]);
      if (at >= 0) {
        return { form: s.slice(0, at).trim(),
                 purpose: s.slice(at + DASH[i].length).trim() };
      }
    }
    return { form: s.trim(), purpose: '' };
  }

  function filled(m) { return (m.form || m.purpose) ? m : null; }

  /* 구조 단계. 백엔드 _w_outline 과 같은 규칙이다. */
  function outline(text) {
    var secs = [], hero = null, warns = [];

    text.split('\n').forEach(function (line) {
      var s = line.trim();
      if (!s) return;

      var body = after(s, HERO);
      if (body !== null) { hero = filled(split(body)); return; }

      body = after(s, IMG);
      if (body !== null) {
        if (!secs.length) {
          warns.push('첫 줄이 이미지입니다. 이미지는 소제목 아래에 적습니다.');
          return;
        }
        secs[secs.length - 1].image = filled(split(body));
        return;
      }

      if (/^(이미지|대표)(\s|$)/.test(s)) {
        warns.push('"' + s.slice(0, 16) + '" 이 소제목으로 읽혔습니다. ' +
                   '이미지로 넣으려면 콜론을 붙이세요.');
      }
      secs.push({ title: s, image: null });
    });

    var body_n = 0;
    secs.forEach(function (x) { if (x.image) body_n++; });
    return {
      warns: warns,
      counts: [
        { icon: '소제목', n: secs.length, unit: '개' },
        { icon: '본문 이미지', n: body_n, unit: '장',
          where: secs.reduce(function (a, x, i) {
            if (x.image) a.push(i + 1 + '번'); return a;
          }, []) },
        { icon: '대표', n: hero ? 1 : 0, unit: '장' }
      ]
    };
  }

  /* payload → 카드 펼침 영역. */
  /* 섹션이 이 글에서 하는 일. 같은 역할이 연달아 이어지면 논리는 맞아도
   * 읽는 리듬이 평평해진다 — 사람이 그걸 보고 판단한다. */
  var SEC_ROLE = {
    context: '상황', diagnosis: '원인', structure: '구조', comparison: '비교',
    procedure: '절차', criteria: '기준', closing: '정리'
  };

  function outlineDetail(pay) {
    var out = '';
    (pay.sections || []).forEach(function (x, i) {
      out += '<div class="osec"><span class="osec-n">' + (i + 1) + '</span>' +
             '<span class="osec-t">' + esc(x.title) +
             /* 어느 명제를 다루는 섹션인지. 구조가 정한 배치라 본문이
              * 이걸 벗어나면 후속 코드가 인용을 걸러 낸다. */
             (x.role ? '<span class="osec-g">' + esc(SEC_ROLE[x.role] || x.role) +
                       '</span>' : '') +
             ((x.claim_refs && x.claim_refs.length)
               ? '<span class="osec-r">' + esc(x.claim_refs.join(' · ')) + '</span>' : '') +
             '</span></div>';
      if (x.image) out += imgRow('osec-i', x.image, '');
      /* 사람이 넣을 사진·자료 화면. 도식과 달리 만들어 주지 않는다. */
      if (x.media) out += mediaRow(x.media);
    });
    if (pay.hero_image) out += imgRow('osec-h', pay.hero_image, '대표 · ');
    return out;
  }

  var MEDIA_LABEL = { photo: '사진', capture: '자료 화면' };

  function mediaRow(m) {
    return '<div class="osec-m"><span class="osec-f">' +
      esc('준비 · ' + (MEDIA_LABEL[m.type] || '자료')) + '</span>' +
      (m.purpose ? ' — ' + esc(m.purpose) : '') + '</div>';
  }

  /* 도식은 form 만 보이면 무엇을 그릴지 알 수 없다. 목적까지 보여야
   * 사람이 "이 도식이 필요한가" 를 판단한다. */
  function imgRow(cls, img, lead) {
    return '<div class="' + cls + '"><span class="osec-f">' +
      esc(lead + (img.form || '')) + '</span>' +
      (img.purpose ? ' — ' + esc(img.purpose) : '') + '</div>';
  }

  /* payload → 직접 쓰기 칸에 그대로 붙는 문자열. parse 가 되읽을 수 있어야 한다. */
  function outlineText(pay) {
    var lines = [];
    (pay.sections || []).forEach(function (x) {
      lines.push(x.title);
      if (x.claim_refs && x.claim_refs.length) {
        lines.push('  근거: ' + x.claim_refs.join(', '));
      }
      if (x.image) lines.push('  이미지: ' + join(x.image));
      if (x.media) {
        lines.push('  ' + (x.media.type === 'capture' ? '캡처' : '사진') +
                   ': ' + (x.media.purpose || ''));
      }
    });
    if (pay.hero_image) lines.push('', '대표: ' + join(pay.hero_image));
    return lines.join('\n');
  }

  function join(img) {
    return [img.form, img.purpose].filter(function (v) { return v; }).join(' — ');
  }

  /* 검증한 명제를 펼쳐 보인다.
   *
   * 카드 겉면에는 상태와 출처 수만 뜬다. 그것만으로는 "왜 확인됐다는
   * 건가" 를 알 수 없어서, 펼치면 원문의 어느 대목이 그렇게 만들었는지
   * 보여 준다. 지어낸 인용이 걸린 경우도 여기서 눈에 띈다. */
  var CLAIM_STATUS = {
    supported: '확인됨', partial: '일부 확인',
    contradicted: '원문과 어긋남', unverified: '확인 필요',
    invalid_check: '검증 오류'
  };

  /* 클래스 이름은 osec- 로 시작한다. 레이아웃 쪽에 .sec-h(섹션 헤더)가
   * 이미 있어서, sec- 를 쓰면 대표 이미지 줄이 그 스타일을 뒤집어쓴다.
   * 한 번 데인 자리다. */

  var CLAIM_AUTH = {
    sufficient: '공식 근거', limited: '보조 근거', insufficient: '출처 자격 부족'
  };

  function claimDetail(pay) {
    if (!pay.claim_id) return null;
    var out = '<div class="cl-st cl-' + esc(pay.status || '') + '">' +
              esc(CLAIM_STATUS[pay.status] || pay.status || '') +
              (pay.claim_type ? ' · ' + esc(pay.claim_type) : '') +
              /* 의미 대응과 출처 자격은 다른 축이다. 규정을 기사가
               * 뒷받침하면 뜻은 맞아도 자격이 모자란다. */
              (pay.authority ? ' · ' + esc(CLAIM_AUTH[pay.authority] || pay.authority) : '') +
              '</div>';

    (pay.sources || []).forEach(function (s) {
      out += '<div class="cl-src">' +
             '<div class="cl-srct">' + esc(s.title || s.url || '출처') +
             ' <span>' + esc(CLAIM_STATUS[s.status] || s.status || '') +
             (s.actual_target ? ' · ' + esc(s.actual_target) : '') +
             (s.file ? ' · 올린 문서' : '') + '</span></div>';
      (s.evidence_spans || []).forEach(function (sp) {
        out += '<blockquote class="cl-q">' + esc(sp.quote || '') +
               (sp.location ? '<cite>' + esc(sp.location) + '</cite>' : '') +
               '</blockquote>';
      });
      /* partial 일 때 무엇이 확인 안 됐는지가 본문 규칙을 가른다. */
      (s.unsupported_parts || []).forEach(function (x) {
        out += '<div class="cl-no">확인 안 됨 · ' + esc(x) + '</div>';
      });
      (s.limitations || []).forEach(function (x) {
        out += '<div class="cl-lim">한계 · ' + esc(x) + '</div>';
      });
      if (s.reason) out += '<div class="cl-why">' + esc(s.reason) + '</div>';
      out += '</div>';
    });

    if (!(pay.sources || []).length) {
      out += '<div class="cl-why">' + esc(pay.why || '뒷받침할 원문이 없습니다') + '</div>';
    }
    return out;
  }

  /* 복사하면 그대로 쓸 수 있는 형태. 인용은 원문 그대로 둔다. */
  function claimText(pay) {
    if (!pay.claim_id) return null;
    var lines = [pay.claim || ''];
    (pay.sources || []).forEach(function (s) {
      lines.push('- ' + (s.title || s.url || '출처'));
      (s.evidence_spans || []).forEach(function (sp) {
        lines.push('  "' + (sp.quote || '') + '"' +
                   (sp.location ? ' (' + sp.location + ')' : ''));
      });
    });
    return lines.join('\n');
  }

  var BY_STEP = {
    evidence: { detail: claimDetail, text: claimText },
    outline: {
      detail: outlineDetail, text: outlineText, parse: outline,
      /* 칸 위 placeholder 는 한 글자만 써도 사라진다. 형식은 늘 보여야 한다. */
      hint: '소제목 아래에 "근거: c01, c02" 로 쓸 명제를, "이미지: 형식 — 목적" 으로 도식을 적는다.',
      insert: [
        { label: '근거 줄 넣기', text: '  근거: ' },
        { label: '이미지 줄 넣기', text: '  이미지:  — ' },
        { label: '사진 줄 넣기', text: '  사진: ' },
        { label: '대표 줄 넣기', text: '대표:  — ' }
      ]
    }
  };

  function shape(key) { return BY_STEP[key] || null; }

  /* 형식을 모르는 단계는 null 을 준다. 그러면 카드가 지금까지와 똑같이 그려진다. */
  function detail(key, pay) {
    var f = shape(key);
    return (f && pay) ? f.detail(pay) : null;
  }

  function text(key, pay) {
    var f = shape(key);
    return (f && pay) ? f.text(pay) : null;
  }

  function insert(ta, text) {
    var a = ta.selectionStart, b = ta.selectionEnd;
    var head = ta.value.slice(0, a), tail = ta.value.slice(b);
    if (head && head.charAt(head.length - 1) !== '\n') text = '\n' + text;
    ta.value = head + text + tail;
    var at = (head + text).length;
    ta.focus();
    ta.setSelectionRange(at, at);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function row(counts) {
    return counts.map(function (c) {
      var on = c.n > 0;
      var where = (on && c.where && c.where.length)
        ? ' <span class="wr-w">' + c.where.join(', ') + '에</span>' : '';
      return '<span class="wr-c' + (on ? ' on' : '') + '">' +
        c.icon + ' <b>' + c.n + '</b>' + c.unit + where + '</span>';
    }).join('');
  }

  /* 칸 아래에 버튼줄과 결과줄을 붙인다. 파서가 없는 단계는 그대로 둔다. */
  function setup(key, ta) {
    var f = shape(key);
    if (!ta || !f) return;
    var parse = f.parse;

    var box = document.createElement('div');
    box.className = 'wr';
    var btns = (f.insert || []).map(function (b, i) {
      return '<button type="button" class="xbtn" data-i="' + i + '">' + b.label + '</button>';
    }).join('');
    box.innerHTML = (f.hint ? '<div class="wr-h">' + esc(f.hint) + '</div>' : '') +
                    (btns ? '<div class="wr-b">' + btns + '</div>' : '') +
                    '<div class="wr-r" id="wr-r"></div>';
    ta.parentNode.insertBefore(box, ta.nextSibling);

    box.querySelectorAll('button[data-i]').forEach(function (b) {
      b.addEventListener('click', function () {
        insert(ta, f.insert[+b.dataset.i].text);
      });
    });

    var out = box.querySelector('.wr-r');
    function draw() {
      if (!ta.value.trim()) { out.innerHTML = ''; return; }
      var r = parse(ta.value);
      out.innerHTML = row(r.counts) +
        r.warns.map(function (w) {
          return '<div class="wr-warn">' + w + '</div>';
        }).join('');
    }
    ta.addEventListener('input', draw);
    draw();
  }

  return { detail: detail, text: text, setup: setup, parse: outline };
})();
