/* 화면 공통 조각. 백엔드를 모른다 — 받은 값을 그리기만 한다. */
window.UI = (function () {

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function go(url) { location.href = url; }
  function $(id) { return document.getElementById(id); }

  /* 페이지 껍데기. HTML 파일 4개가 똑같은 이유 — 여기서 다 만든다. */
  function boot() {
    document.body.insertAdjacentHTML('afterbegin',
      '<div class="topbar"><div class="topbar-in">' +
        '<span class="brand">SOLUTIS C&amp;T</span>' +
        '<span class="brand-div">·</span>' +
        '<span class="brand-sub">콘텐츠 제작</span>' +
      '</div></div>');
  }

  function title(t) { document.title = t + ' · SOLUTIS C&T'; }

  function stepUrl(key, no) {
    return no === 1 || key === 'topic' ? '/' :
           key === 'approve' ? '/approve.html' :
           '/step.html?s=' + encodeURIComponent(key);
  }

  function query(k) { return new URLSearchParams(location.search).get(k); }

  /* ── 뼈대 조각 ───────────────────────────────────────────── */

  function stepbar(steps, current, doneKeys) {
    return '<div class="stepbar">' + steps.map(function (x) {
      var now = x.key === current;
      var ok = !now && doneKeys.indexOf(x.key) >= 0;
      return '<div class="sb' + (now ? ' now' : '') + (ok ? ' ok' : '') + '">' +
             '<span class="sb-n">' + x.no + '</span>' +
             '<span class="sb-t">' + esc(x.name) + '</span></div>';
    }).join('') + '</div>';
  }

  function carry(done, opt) {
    opt = opt || {};
    if (!done.length) return '';
    return '<div class="carry' + (opt.big ? ' big' : '') + '">' +
      done.map(function (x) {
        return '<div class="carry-r">' +
          '<span class="carry-n">' + x.no + '</span>' +
          '<span class="carry-k">' + esc(x.name) + '</span>' +
          (opt.big
            ? '<span class="carry-b"><span class="carry-v">' + esc(x.label) + '</span>' +
              (x.detail ? '<span class="carry-d">' + esc(x.detail) + '</span>' : '') + '</span>'
            : '<span class="carry-v">' + esc(x.label) + '</span>') +
          '<a class="carry-e" href="' + stepUrl(x.key, x.no) + '">고치기</a>' +
          '</div>';
      }).join('') + '</div>';
  }

  function sec(head, cnt, body) {
    return '<div class="sec"><div class="sec-h">' + head +
      (cnt ? '<span class="cnt">' + cnt + '</span>' : '') + '</div>' + body + '</div>';
  }

  function actions(inner) {
    return '<div class="actions"><div class="actions-in">' + inner + '</div></div>';
  }

  /* 고를 거리 하나. home 은 여기에 점수·출처·피드백을 더 붙인다.
   *
   * o.selectable 이 거짓이면 못 고른다. **화면이 상태를 보고 다시 판단하지
   * 않는다** — 백엔드가 값으로 내려보낸 것만 읽는다. 판단이 두 곳에 있으면
   * 어긋나고, 실제로 미확인 추론을 화면이 전부 막아 버린 적이 있다. */
  function card(o) {
    var off = o.selectable === false;
    return '<div class="card' + (o.sel ? ' sel' : '') + (o.down ? ' down' : '') +
        (off ? ' off' : '') + (o.pick ? ' pick' : '') + '"' +
        (o.id != null ? ' data-id="' + esc(o.id) + '"' : '') + '>' +
      '<label class="card-main">' +
        '<input type="' + (o.multi ? 'checkbox' : 'radio') + '" name="' + o.name +
          '" value="' + esc(o.value) + '" hidden' +
          (off ? ' disabled' : '') + (o.sel && !off ? ' checked' : '') + '>' +
        '<span class="dot' + (o.multi ? ' sq' : '') + '"></span>' +
        '<span class="card-b">' +
          '<span class="card-t">' + o.title + '</span>' +
          (o.summary ? '<span class="card-s">' + esc(o.summary) + '</span>' : '') +
          /* "추천 · " 로 시작하면 그 말머리만 강조한다. 백엔드가 붙인
           * 문자열을 화면이 다시 해석하지 않는다 — 판단은 거기서 끝났다. */
          (o.meta
            ? '<span class="card-m">' +
              (o.meta.indexOf('추천 · ') === 0
                ? '<b class="pick">추천</b>' + o.meta.slice(4)
                : o.meta) + '</span>'
            : '') +
          (o.extra || '') +
        '</span>' +
      '</label>' +
      (o.detail
        ? '<div class="card-x">' +
            '<div class="card-x-b">' + o.detail + '</div>' +
            '<div class="card-x-a">' +
              (o.copy != null ? '<button type="button" class="xbtn x-copy">복사</button>' : '') +
              (o.edit ? '<button type="button" class="xbtn x-edit">고쳐 쓰기</button>' : '') +
              '<button type="button" class="xbtn x-fold">접기</button>' +
            '</div>' +
          '</div>' +
          '<div class="card-x-t"><button type="button" class="xbtn x-open">펼치기</button></div>'
        : '') +
      (o.foot || '') + '</div>';
  }

  /* 카드의 펼침 영역. detail 을 준 카드에만 붙는다.
   *
   * 여러 개를 동시에 펼 수 있게 둔다. 후보를 나란히 비교하는 게 이 화면의
   * 목적이라, 하나를 펴면 나머지가 접히는 아코디언은 맞지 않는다.
   *
   * texts 는 카드 id 를 키로 하는 복사할 문자열 모음이다. HTML 에 심어 두면
   * 이스케이프 왕복이 생기고, 줄바꿈이 살아남지 못한다. */
  function expand(texts, onEdit) {
    cardsIn(document).forEach(function (card) {
      var open = card.querySelector('.x-open');
      var fold = card.querySelector('.x-fold');
      var cp = card.querySelector('.x-copy');
      var ed = card.querySelector('.x-edit');
      if (!open) return;

      if (ed) ed.addEventListener('click', function () {
        var t = (texts || {})[card.dataset.id];
        if (t != null && onEdit) onEdit(t);
      });

      function set(on) { card.classList.toggle('xopen', on); }
      open.addEventListener('click', function () { set(true); });
      if (fold) fold.addEventListener('click', function () { set(false); });

      if (cp) cp.addEventListener('click', function () {
        var t = (texts || {})[card.dataset.id];
        if (t == null) return;
        copy(t).then(function () {
          cp.textContent = '복사했습니다';
          setTimeout(function () { cp.textContent = '복사'; }, 1200);
        }, function () {
          cp.textContent = '복사 실패';
          setTimeout(function () { cp.textContent = '복사'; }, 1200);
        });
      });
    });
  }

  function cardsIn(root) { return [].slice.call(root.querySelectorAll('.card')); }

  /* 파일로 내려받기. 도식 PNG 는 shot.js 가 캔버스에서 만들지만, 글자
   * 결과물은 이미 문자열로 있으므로 여기서 바로 내보낸다. */
  function download(text, name, mime) {
    mime = mime || 'text/plain';
    /* 텍스트 파일에만 BOM 을 붙인다. 윈도 메모장이 UTF-8 을 알아보게 하려는
     * 것인데, HTML 에 붙으면 CMS 에 넣었을 때 앞에 보이지 않는 글자가 남는다. */
    var body = mime === 'text/plain' ? "\ufeff" + text : text;
    var blob = new Blob([body], { type: mime + ';charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /* 이미 만들어진 Blob 을 내려받는다. 문자열이 아니라 파일을 받을 때 쓴다. */
  function saveBlob(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /* 파일 이름으로 못 쓰는 글자를 뺀다. 제목이 그대로 파일명이 되므로
   * 콜론·슬래시가 들어가면 윈도에서 저장이 막힌다. */
  function safeName(t, ext) {
    var base = (t || '결과물').replace(/[\\/:*?"<>|]/g, '').trim().slice(0, 60);
    return (base || '결과물') + ext;
  }

  /* 클립보드. LAN 으로 열면(http://192.168.x.x) navigator.clipboard 가 막힌다 —
   * 보안 컨텍스트가 아니어서다. 그때는 옛 방식으로 떨어진다. */
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (ok, no) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px';
      document.body.appendChild(ta);
      ta.select();
      var done = false;
      try { done = document.execCommand('copy'); } catch (e) { done = false; }
      document.body.removeChild(ta);
      done ? ok() : no();
    });
  }

  /* 누른 버튼을 잠그고 무슨 일이 일어나는지 알린다.
   *
   * 직접 쓰기로 확정하면 그 자리에서 프롬프트가 한 번 더 돌아 1~3초 걸린다.
   * 그 구간에 표시가 없으면 안 눌린 줄 알고 다시 누르게 되고, 그러면
   * 같은 프롬프트가 두 번 돈다 — 값이 덮어써지고 호출도 두 배 나간다.
   *
   * 되돌리는 함수를 준다. 화면이 넘어갈 때는 되돌리지 않는다. */
  function busy(btn, label) {
    if (!btn || btn.disabled) return null;
    var was = btn.textContent;
    btn.disabled = true;
    btn.textContent = label || '잠시만…';
    return function () { btn.disabled = false; btn.textContent = was; };
  }

  /* 피드백 한 덩이. 소재 카드든 단계 후보든 결과물이든 같은 모양이다.
   * tags 를 주면 '별로'일 때 이유 칩이 열린다. 단계 후보에는 아직 안 준다 —
   * 무엇이 반복되는 이유인지는 메모가 쌓여야 알 수 있다. */
  function fb(o) {
    o = o || {};
    var on = o.on || [];
    return '<div class="fb"><span class="fb-label">피드백</span>' +
      '<button type="button" class="ev' + (o.verdict === 'up' ? ' on-up' : '') + '" data-v="up">좋음</button>' +
      '<button type="button" class="ev' + (o.verdict === 'down' ? ' on-down' : '') + '" data-v="down">별로</button>' +
      '<input type="text" class="fb-note" value="' + esc(o.note || '') +
        '" placeholder="' + esc(o.hint || '의견 한 줄 — 왜 그렇게 봤는지 (선택)') + '">' +
      (o.tags && o.tags.length
        ? '<div class="fb-tags' + (o.verdict === 'down' ? ' open' : '') + '">' +
            '<span class="fb-tags-h">이유</span>' +
            o.tags.map(function (t) {
              return '<button type="button" class="chip' +
                (on.indexOf(t) >= 0 ? ' on' : '') + '">' + esc(t) + '</button>';
            }).join('') +
          '</div>'
        : '') +
      '</div>';
  }

  /* 피드백 덩이에 동작을 붙인다. save(값) 이 실제 저장을 한다.
   * 저장이 실패해도 화면은 그대로 둔다 — 평가는 곁가지고, 작업이 멈추면 안 된다. */
  function fbWire(root, save, opt) {
    opt = opt || {};
    var box = root.querySelector('.fb');
    if (!box) return;
    var tagbox = box.querySelector('.fb-tags');

    function value() {
      var hit = box.querySelector('.ev.on-up, .ev.on-down');
      var n = box.querySelector('.fb-note');
      return {
        verdict: hit ? hit.dataset.v : 'none',
        tags: [].slice.call(box.querySelectorAll('.chip.on'))
                .map(function (c) { return c.textContent.trim(); }),
        note: n ? n.value : ''
      };
    }

    function flash() {
      var t = opt.flash || root;
      t.classList.add('saved');
      setTimeout(function () { t.classList.remove('saved'); }, 700);
    }

    function send() { Promise.resolve(save(value())).then(flash, function () {}); }

    box.querySelectorAll('.ev').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var was = btn.classList.contains('on-up') || btn.classList.contains('on-down');
        box.querySelectorAll('.ev').forEach(function (b) { b.classList.remove('on-up', 'on-down'); });
        if (!was) btn.classList.add(btn.dataset.v === 'up' ? 'on-up' : 'on-down');
        var down = btn.dataset.v === 'down' && !was;
        if (tagbox) tagbox.classList.toggle('open', down);
        if (opt.onDown) opt.onDown(down);
        send();
      });
    });

    box.querySelectorAll('.chip').forEach(function (chip) {
      chip.addEventListener('click', function () { chip.classList.toggle('on'); send(); });
    });

    var note = box.querySelector('.fb-note');
    if (note) {
      note.addEventListener('change', send);
      note.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); note.blur(); }
      });
    }
  }

  /* 파일 올리기 상자.
   *
   * 단계 이름으로 분기하지 않는다. 백엔드 단계 정의에 upload 플래그가 있으면
   * 그리고, 없으면 안 그린다 — multi·custom 과 같은 방식이다. 나중에 다른
   * 단계가 파일을 받게 되면 이 화면 코드는 안 바뀐다.
   *
   * 올린 문서는 아래 후보 목록에도 카드로 나타난다. 여기 목록은 "무엇을
   * 올렸나" 를 보여주고 지우는 자리고, 고르는 것은 카드에서 한다. */
  /* 올린 뒤 화면을 다시 그리면 상자도 새로 만들어진다. 그때 방금 무슨
   * 일이 있었는지 알려 줄 자리가 없으면 **아무 변화가 없어 보인다** —
   * 파일이 사라지고 메시지도 지워진다. 다시 그린 뒤에 이어서 보인다. */
  var upSaid = '';

  function uploader(docs) {
    return '<div class="up">' +
      /* 올리는 동안 상자 자체가 진행 상태를 보인다. 예전에는 아래쪽
       * 한 줄뿐이라 스크롤 밖이면 아무 일도 안 일어나는 것처럼 보였다. */
      '<div class="up-drop" id="up-drop">' +
        '<input type="file" id="up-file" accept="application/pdf,.pdf" multiple hidden>' +
        '<div class="up-work" id="up-work" hidden>' +
          '<div class="up-spin"></div>' +
          '<div class="up-work-t" id="up-work-t"></div>' +
          '<div class="up-work-s" id="up-work-s"></div>' +
        '</div>' +
        '<div class="up-drop-in">' +
          '<span class="up-drop-t">여기로 PDF 를 끌어다 놓으세요</span>' +
          '<span class="up-drop-s">또는 <button type="button" class="up-link" id="up-browse">파일 고르기</button></span>' +
        '</div>' +
      '</div>' +
      '<div class="up-bar" id="up-bar" hidden>' +
        '<span class="up-name" id="up-name"></span>' +
        '<button type="button" class="mini" id="up-clear">비우기</button>' +
        '<button type="button" class="mini solid" id="up-go">올리기</button>' +
      '</div>' +
      '<div class="up-hint">글자가 선택되는 PDF 여야 합니다. 스캔한 문서는 글자를 뽑을 수 없습니다.<br>한 개당 20MB · 40만 자까지. 더 긴 문서는 필요한 장만 나눠 올리세요.</div>' +
      '<div class="up-msg" id="up-msg">' + esc(upSaid) + '</div>' +
      '<div class="up-list" id="up-list">' + upRows(docs) + '</div>' +
      '</div>';
  }

  function upRows(docs) {
    if (!docs || !docs.length) return '';
    return docs.map(function (d) {
      var segs = d.segments || [];
      /* 어느 쪽을 근거로 쓰는지 번호와 첫 줄까지 보여준다. 엉뚱한 데를
       * 골랐으면 발행 전에, 본문을 만들기도 전에 사람이 알아야 한다. */
      var picked = d.picked
        ? '<div class="up-seg"><span class="up-seg-h">근거 구간 ' + segs.length + '곳' +
            (d.pick_why ? ' · ' + esc(d.pick_why) : '') + '</span>' +
            segs.map(function (g) {
              return '<div class="up-seg-r"><span class="up-pg">' + g.page + '쪽</span>' +
                     '<span class="up-hd">' + esc(g.head) + '</span></div>';
            }).join('') + '</div>'
        : '';
      var warn = d.pick_error
        ? '<div class="up-seg bad">구간을 고르지 못해 앞부분만 씁니다 — ' + esc(d.pick_error) + '</div>'
        : (!d.picked && d.truncated
            ? '<div class="up-seg bad">앞부분만 넘어갑니다</div>' : '');

      return '<div class="up-r" data-doc="' + esc(d.id) + '">' +
        '<div class="up-r-top">' +
          '<span class="up-t">' + esc(d.name) + '</span>' +
          '<span class="up-m">' + d.pages + '쪽 · ' + Math.round(d.chars / 100) / 10 + '천자</span>' +
          '<button type="button" class="up-x" title="지우기">지우기</button>' +
        '</div>' + picked + warn +
        '</div>';
    }).join('');
  }

  /* 상자에 동작을 붙인다. onChange 는 목록이 바뀐 뒤 화면을 다시 그리라는 신호다.
   *
   * 끌어다 놓기와 파일 고르기가 같은 자리로 모인다. 브라우저마다 드래그
   * 이벤트가 조금씩 달라서, 실제로 파일을 얻는 경로는 setFiles() 하나로 둔다.
   *
   * 여러 개를 한 번에 받는다. 규정 원문과 이행 가이드를 함께 올리는 일이
   * 흔한데 한 개씩만 되면 같은 동작을 여러 번 하게 된다. 올리는 것은 하나씩
   * 차례로 보낸다 — 한꺼번에 보내면 어느 것이 왜 거절됐는지 알 수 없다.
   */
  function upWire(onChange) {
    var file = $('up-file'), drop = $('up-drop'), bar = $('up-bar');
    var go = $('up-go'), clear = $('up-clear'), name = $('up-name'), msg = $('up-msg');
    var work = $('up-work'), workT = $('up-work-t'), workS = $('up-work-s');
    if (!file || !drop) return;

    /* 올리는 동안 상자를 진행 화면으로 바꾼다. 단계를 적는 이유는 PDF
     * 하나에 30초 넘게 걸릴 수 있어서다 — 글자를 뽑고, 필요하면 어느 쪽을
     * 쓸지 모델이 고른다. 그동안 아무 표시가 없으면 멈춘 줄 안다. */
    function working(on, title, sub) {
      if (!work) return;
      work.hidden = !on;
      drop.classList.toggle('busy', !!on);
      if (on) {
        workT.textContent = title || '';
        workS.textContent = sub || '';
      }
    }

    var queue = [];

    function say(t, bad, keep) {
      msg.textContent = t || '';
      msg.classList.toggle('bad', !!bad);
      // keep 이면 다시 그린 뒤에도 남는다. 올린 결과가 그렇다.
      upSaid = keep ? (t || '') : '';
    }

    function show() {
      bar.hidden = !queue.length;
      name.textContent = queue.length === 1
        ? queue[0].name
        : queue.length + '개 · ' + queue.map(function (f) { return f.name; }).join(', ');
    }

    /* PDF 만 남긴다. 확장자로 먼저 거르는 것은 서버 왕복을 아끼려는 것이고,
     * 진짜 검사는 서버가 앞머리 바이트로 한다. */
    function setFiles(list) {
      var all = [].slice.call(list || []);
      var pdf = all.filter(function (f) { return /\.pdf$/i.test(f.name); });
      queue = pdf;
      show();
      if (!all.length) return;
      if (!pdf.length) say('PDF 파일만 받습니다', true);
      else if (pdf.length < all.length) say((all.length - pdf.length) + '개는 PDF 가 아니라 뺐습니다', true);
      else say('');
    }

    $('up-browse').addEventListener('click', function () { file.click(); });
    drop.addEventListener('click', function (e) {
      if (e.target.id !== 'up-browse') file.click();
    });
    file.addEventListener('change', function () { setFiles(file.files); });

    /* dragover 를 막지 않으면 drop 이 오지 않고 브라우저가 파일을 연다. */
    ['dragenter', 'dragover'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) {
        e.preventDefault(); e.stopPropagation();
        drop.classList.add('over');
      });
    });
    ['dragleave', 'dragend'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) {
        e.preventDefault(); e.stopPropagation();
        if (ev === 'dragend' || !drop.contains(e.relatedTarget)) drop.classList.remove('over');
      });
    });
    drop.addEventListener('drop', function (e) {
      e.preventDefault(); e.stopPropagation();
      drop.classList.remove('over');
      setFiles(e.dataTransfer && e.dataTransfer.files);
    });

    /* 창 어디에 놓아도 브라우저가 파일을 열어 버리지 않게 막는다. 상자 밖에
     * 놓으면 아무 일도 안 일어나는 편이, 쓰던 화면이 PDF 로 바뀌는 것보다 낫다. */
    ['dragover', 'drop'].forEach(function (ev) {
      window.addEventListener(ev, function (e) {
        if (!drop.contains(e.target)) e.preventDefault();
      });
    });

    clear.addEventListener('click', function () {
      file.value = ''; queue = []; show(); say('');
    });

    go.addEventListener('click', function () {
      if (!queue.length) return;
      var undo = busy(go, '올리는 중…');
      if (!undo) return;

      var list = queue.slice(), done = 0, bad = [];

      var total = queue.length;

      function step() {
        if (!list.length) {
          working(false);
          undo();
          file.value = ''; queue = []; show();
          /* 한 개를 올려도 알린다. 예전에는 done > 1 이라 한 개일 때
           * 아무 말이 없었고, 그러면 올라갔는지 알 수가 없다. */
          say(bad.length ? bad.join(' / ')
                         : (done ? done + '개를 올렸습니다' : ''),
              !!bad.length, true);
          if (done) {
            /* 목록을 다시 받는다. 여기서 터지면 화면이 멈추므로 잡는다. */
            var back = onChange();
            if (back && back.catch) {
              back.catch(function () { say('올렸지만 화면을 다시 받지 못했습니다', true); });
            }
          }
          return;
        }
        var f = list.shift();
        var nth = total > 1 ? (done + bad.length + 1) + ' / ' + total + ' · ' : '';
        working(true, nth + f.name,
                '글자를 뽑고 쓸 쪽을 고르는 중입니다. 쪽수가 많으면 30초 넘게 걸립니다.');
        say('');
        API.docUpload(f).then(function (r) {
          if (r.ok) done += 1;
          else bad.push(f.name + ': ' + (r.detail || '올리지 못했습니다'));
          step();
        }, function () {
          bad.push(f.name + ': 서버에 닿지 못했습니다');
          step();
        });
      }
      step();
    });

    document.querySelectorAll('.up-r .up-x').forEach(function (b) {
      b.addEventListener('click', function () {
        var id = b.closest('.up-r').dataset.doc;
        b.disabled = true;
        API.docDelete(id).then(function (r) {
          if (r.ok) onChange(); else { b.disabled = false; say('지우지 못했습니다', true); }
        }, function () { b.disabled = false; say('서버에 닿지 못했습니다', true); });
      });
    });
  }

  /* 직접 쓰기 상자 */
  function write(placeholder, value, opt) {
    opt = opt || {};
    return '<div class="write' + (opt.lead ? ' lead' : '') + '">' +
      (opt.head ? '<div class="write-h">' + esc(opt.head) + '</div>' : '') +
      '<textarea id="dw" placeholder="' + esc(placeholder) + '">' + esc(value || '') + '</textarea>' +
      '<div class="write-hint" id="dw-hint">' + esc(opt.hint || '여기에 쓰면 위에서 고른 건 무시됩니다.') + '</div>' +
      (opt.buttons ? '<div class="write-btns">' + opt.buttons + '</div>' : '') +
      '</div>';
  }

  /* ── 고르기 ──────────────────────────────────────────────── */
  //
  // 카드를 고르면 직접 쓰기를 비우고, 직접 쓰면 카드를 푼다.
  // 1단계와 2~7단계가 똑같이 동작하므로 여기 한 번만 적는다.
  // 안내 문구는 화면마다 다르니 message 로 받는다.

  function picker(opt) {
    var dw = $('dw'), hint = $('dw-hint'), note = $('note');

    function cards() { return [].slice.call(document.querySelectorAll('.card')); }
    function checked() {
      return [].slice.call(document.querySelectorAll('input[name=' + opt.name + ']:checked'));
    }
    function typed() { return dw ? dw.value.trim() : ''; }

    function refresh() {
      if (note) note.textContent = opt.message(typed(), checked());
      if (hint) hint.style.visibility = typed() ? 'visible' : 'hidden';
      if (opt.after) opt.after();
    }

    cards().forEach(function (card) {
      var box = card.querySelector('input[name=' + opt.name + ']');
      if (!box) return;
      box.addEventListener('change', function () {
        if (!opt.multi) cards().forEach(function (c) { c.classList.remove('sel'); });
        card.classList.toggle('sel', box.checked);
        /* both 면 고른 것과 쓴 것이 함께 확정된다. 여러 개를 담는 단계에서는
         * 둘 중 하나만 남기면 나머지가 조용히 버려진다. */
        if (dw && box.checked && !opt.both) dw.value = '';
        refresh();
      });
    });

    if (dw) dw.addEventListener('input', function () {
      if (typed() && !opt.both) {
        checked().forEach(function (b) { b.checked = false; });
        cards().forEach(function (c) { c.classList.remove('sel'); });
      }
      refresh();
    });

    refresh();
    return {
      cards: cards, checked: checked, refresh: refresh,
      values: function () { return checked().map(function (b) { return b.value; }); },
      text: function () { return dw ? dw.value : ''; },
      unset: function (card) {
        var box = card.querySelector('input[name=' + opt.name + ']');
        if (box && box.checked) { box.checked = false; card.classList.remove('sel'); }
      }
    };
  }

  /* 목록이 잘려 있으면 알려 준다 */
  function scrollFoot(listId, footId) {
    var list = $(listId), foot = $(footId);
    if (!list || !foot) return function () {};
    function tick() {
      var hidden = list.scrollHeight - list.clientHeight;
      var atEnd = list.scrollTop + list.clientHeight >= list.scrollHeight - 4;
      foot.textContent = (hidden > 8 && !atEnd) ? '아래로 더 있습니다 ↓' : '';
    }
    list.addEventListener('scroll', tick);
    window.addEventListener('resize', tick);
    tick();
    return tick;
  }

  /* ── 실패 처리 ───────────────────────────────────────────── */

  /* 거절 사유 → 사람이 읽을 문구. 백엔드가 "왜" 를 주므로 화면은
   * 그것을 옮기기만 한다. */
  var SAY = {
    empty:      '고르거나 직접 쓴 것이 없습니다',
    no_sources: '근거로 쓸 문서나 출처가 없습니다. PDF 를 올리거나 후보를 고르세요',
    no_claims:  '검증할 명제가 없습니다. 앞 단계를 다시 확인하세요'
  };

  function why(e) {
    return (e && SAY[e.reason]) || (e && e.message) || '알 수 없는 이유';
  }

  function fail(msg) {
    $('app').innerHTML =
      '<div class="page"><div class="err"><div class="err-t">화면을 열지 못했습니다</div>' +
      '<div class="err-s">' + esc(msg) + '</div>' +
      '<div class="err-btns"><a class="mini solid" href="/">소재 선택으로</a></div></div></div>';
  }

  /* 백엔드가 거절하면 가야 할 곳으로 보낸다 */
  function guard(res) {
    if (res.ok) return false;
    if (res.reason === 'no_topic') { go('/'); return true; }
    if (res.reason === 'no_body') { go('/approve.html'); return true; }
    if (res.reason === 'skipped' || res.reason === 'incomplete') {
      go(stepUrl(res.need, 9)); return true;
    }
    fail(res.detail || res.reason || '알 수 없는 이유');
    return true;
  }

  return { esc: esc, go: go, $: $, boot: boot, title: title, query: query,
           stepUrl: stepUrl, stepbar: stepbar, carry: carry, sec: sec,
           actions: actions, card: card, write: write, picker: picker,
           fb: fb, fbWire: fbWire, busy: busy,
           uploader: uploader, upWire: upWire,
           expand: expand, copy: copy,
           download: download, saveBlob: saveBlob, safeName: safeName,
           scrollFoot: scrollFoot, fail: fail, guard: guard, why: why };
})();
