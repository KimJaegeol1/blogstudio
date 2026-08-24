/* 결과물 — 네이버용 / 홈페이지용 두 갈래.
 *
 * 보이는 쪽이 원본이고 반대쪽은 거기서 만들어진다.
 * 네이버는 서식 → 텍스트 한 방향, 홈페이지는 양방향이다.
 */
(function () {
  var $ = UI.$;

  /* 발행 전 확인할 것. 결과물 안에 넣지 않는다 — 확인되지 않은 근거가
     참고자료에 실리면 확인 안 된 것에 출처가 붙은 글이 된다. */
  function checklist(items) {
    if (!items || !items.length) return '';
    return UI.sec('발행 전 확인할 것', items.length + '건',
      '<div class="chk">' + items.map(function (x) {
        return '<div class="chk-r">' +
          '<span class="chk-k">' + UI.esc(x.kind) + '</span>' +
          '<span class="chk-b"><span class="chk-t">' + UI.esc(x.text) + '</span>' +
          (x.note ? '<span class="chk-n">' + UI.esc(x.note) + '</span>' : '') +
          '</span></div>';
      }).join('') + '</div>');
  }

  /* 대표 이미지. 두 갈래에 다 쓰이므로 탭 밖에 둔다.
   *
   * 본문 작성과 따로 만드는 이유는 되돌리기 때문이다. 그림은 보자마자
   * 아니다 싶은 일이 잦고, 그때 본문까지 다시 만들 이유가 없다. */
  /* 이 글을 그대로 내도 되는지 한 줄로. 확인 목록을 다 읽지 않고
   * 발행하는 것이 실제로 났던 실패라, 맨 위에서 한 번 잡는다.
   * 막지는 않는다 — 근거 없이도 내야 할 때가 있고 그 판단은 사람 몫이다. */
  function readyBar(R) {
    var r = R.out && R.out.ready;
    if (!r) return '';
    return '<div class="ready' + (r.ok ? '' : ' warn') + '">' +
      '<b>' + UI.esc(r.text) + '</b>' +
      (r.why && r.why.length
        ? '<span>' + r.why.map(UI.esc).join(' · ') + '</span>' : '') +
      (r.claims ? '<em>명제 ' + r.claims + '건 중 인용 가능 ' + r.cited + '건</em>' : '') +
      '</div>';
  }

  function heroBlock(R) {
    var plan = R.hero_plan || '';
    var made = R.hero || null;
    if (!plan && !made) return '';

    var body = made
      ? '<img class="hero-img" id="hero-img" src="/api/draft/hero.png?t=' +
          Date.now() + '" alt="' + UI.esc(made.alt || plan) + '">' +
        '<div class="hero-alt">' + UI.esc(made.alt || '') + '</div>'
      : '<div class="hero-plan">' + UI.esc(plan) + '</div>';

    return '<div class="out hero"><div class="out-h">대표 이미지' +
      '<span class="out-n" id="hero-note">' +
        UI.esc(made ? '내려받아 두 곳에 올리세요'
                    : (R.hero_error || '아직 만들지 않았습니다')) +
      '</span>' +
      (made ? '<button type="button" class="mini" id="hero-dl">16:9 저장</button>' +
              '<button type="button" class="mini" id="hero-sq">1:1 저장</button>' : '') +
      '<button type="button" class="mini solid" id="hero-go">' +
        (made ? '다시 만들기' : '만들기') +
      '</button></div>' +
      '<div class="out-b" id="hero-body">' + body + '</div></div>';
  }

  function heroWire() {
    /* 대표 이미지 내려받기.
     *
     * 홈페이지는 16:9 를 그대로 쓰고, 네이버 목록은 정사각이라 가운데를
     * 남기고 자른 판이 따로 필요하다. 자르는 일은 브라우저가 한다 —
     * 서버에 이미지 처리 패키지를 얹지 않으려는 것이다. */
    function heroName(suffix) {
      var t = $('n-title');
      return UI.safeName((t ? t.textContent : '') + suffix, '.png');
    }

    var img = $('hero-img');
    var dl = $('hero-dl');
    if (dl && img) dl.addEventListener('click', function () {
      fetch(img.src).then(function (r) { return r.blob(); })
        .then(function (b) { UI.saveBlob(b, heroName('-대표-16x9')); });
    });

    var sq = $('hero-sq');
    if (sq && img) sq.addEventListener('click', function () {
      run(sq, function () { return Shot.square(img, heroName('-대표-1x1')); },
          '저장했습니다');
    });

    var go = $('hero-go');
    if (!go) return;
    go.addEventListener('click', function () {
      var was = go.textContent;
      go.disabled = true;
      go.textContent = '만드는 중…';
      API.hero().then(function (r) {
        if (r && r.ok) { location.reload(); return; }
        go.disabled = false;
        go.textContent = was;
        var note = $('hero-note');
        if (note) note.textContent = (r && r.detail) || '만들지 못했습니다';
      }, function () {
        go.disabled = false;
        go.textContent = was;
        var note = $('hero-note');
        if (note) note.textContent = '서버에 닿지 못했습니다';
      });
    });
  }

  function block(title, note, buttons, body) {
    return '<div class="out"><div class="out-h">' + UI.esc(title) +
      '<span class="out-n">' + note + '</span>' + buttons + '</div>' + body + '</div>';
  }

  function btns(revertFor, extra, copyAttrs) {
    return '<button type="button" class="revert" data-for="' + revertFor + '" hidden>되돌리기</button>' +
      (extra || '') + '<button type="button" class="copy" ' + copyAttrs + '>복사</button>';
  }

  function render(STEPS, R) {
    var out = R.out, by = {};
    /* 캡처 폭·글자 크기는 채널마다 다르다. 백엔드가 준 값을 쓴다. */
    if (out.capture) Shot.setStyle(out.capture);
    R.done.forEach(function (x) { by[x.key] = x; });

    $('app').innerHTML =
      '<div class="page">' +
        '<div class="eyebrow">RESULT</div><div class="h1">만들어진 글</div>' +
        '<div class="note-bar">고칠 곳을 <b>더블클릭</b>하면 그 자리에서 고쳐집니다.' +
          ' 고친 내용은 저장되지 않으니 붙여넣기 직전에 손보세요.</div>' +
        readyBar(R) +

        heroBlock(R) +

        /* 한 드래프트는 한 채널이다. 고른 쪽만 그린다 —
         * 탭은 둘 다 있을 때만 뜻이 있다. */
        (out.naver ? '' : '') +

        (out.naver ? '<div class="pane" data-p="naver">' +
          block('제목', '글쓰기 화면의 제목 칸',
                btns('n-title', '', 'data-src="n-title"'),
                '<div class="out-b one" id="n-title" data-edit>' + UI.esc(out.naver.title) + '</div>') +
          block('본문', '본문 칸',
                btns('n-rich',
                     '<button type="button" class="mini" id="n-html">HTML 저장</button>' +
                     '<button type="button" class="mini" id="n-dl">텍스트 저장</button>' +
                     '<button type="button" class="mini" id="n-toggle">텍스트로 보기</button>',
                     'data-html="n-rich" data-src="n-body"'),
                '<div class="out-b naver" id="n-rich" data-edit-in>' + out.naver.html + '</div>' +
                '<pre class="out-b text" id="n-body" hidden></pre>') +
          block('태그', out.naver.tags.length + '개',
                btns('n-tags', '', 'data-src="n-tags"'),
                '<div class="out-b one" id="n-tags" data-edit>' + UI.esc(out.naver.tag_line) + '</div>') +
          figureShop(out.naver.figures, out.naver.figure_css) +
          illustShop(out.illust) +
          recipe(out.naver.recipe) +
        '</div>' : '') +

        (out.site ? '<div class="pane" data-p="site">' +
          block('HTML', UI.esc(out.site.meta_note) + ' · 제목·설명은 코드 맨 위 주석에',
                btns('s-prev',
                     '<button type="button" class="mini" id="s-dl">HTML 저장</button>' +
                     '<button type="button" class="mini" id="s-toggle">코드 보기</button>',
                     'data-src="s-html"'),
                '<div class="out-b" id="s-prev" data-edit-in>' + out.site.html + '</div>' +
                '<pre class="out-b code" id="s-html" data-edit-code hidden></pre>') +
        '</div>' : '') +

        checklist(out.checklist) +

        UI.sec('이 결과물 어땠나', '',
          '<div class="fbwrap" id="fbwrap">' +
            UI.fb({ hint: '결과물 전체에 대한 의견 한 줄 (선택)' }) +
          '</div>') +

        UI.sec('다시 하기', '',
          '<div class="carry">' + STEPS.filter(function (x) { return x.key !== 'approve'; })
            .map(function (x) {
              return '<div class="carry-r"><span class="carry-n">' + x.no + '</span>' +
                '<span class="carry-k">' + UI.esc(x.name) + '</span>' +
                '<span class="carry-v">' + UI.esc((by[x.key] || {}).label || '-') + '</span>' +
                '<a class="carry-e" href="' + UI.stepUrl(x.key, x.no) + '">고치기</a></div>';
            }).join('') + '</div>') +
      '</div>' +
      UI.actions(
        '<a class="btn" href="/approve.html">← 승인으로</a>' +
        '<span class="act-note">새 글은 소재 선택부터 시작합니다</span>' +
        '<a class="btn primary" href="/">새 글 시작</a>');

    UI.fbWire(UI.$('fbwrap'), function (v) {
      return API.feedback({ step: 'result', option_id: '',
                            verdict: v.verdict, tags: v.tags, note: v.note });
    });

    /* 파일로 내려받기. 복사가 막히는 환경도 있고, CMS 에 붙이기 전에
     * 브라우저로 열어 확인하고 싶을 때도 있다. */
    var dlTitle = (R.out.naver && R.out.naver.title) || '결과물';
    var sdl = $('s-dl');
    if (sdl) sdl.addEventListener('click', function () {
      sync();
      UI.download($('s-html').textContent, UI.safeName(dlTitle, '.html'), 'text/html');
    });
    var ndl = $('n-dl');
    if (ndl) ndl.addEventListener('click', function () {
      sync();
      UI.download($('n-body').textContent, UI.safeName(dlTitle, '.txt'), 'text/plain');
    });

    heroWire();
    shots();
    shopWire();
    illustWire();
    wire();
    UI.title('결과물');
  }

  /* 홈페이지 미리보기 안의 도식마다 저장 버튼을 붙인다.
   *
   * 네이버 에디터는 표·도식을 못 받아서, 지금은 사람이 이 화면을 캡처해
   * 넣는다. 화면에 이미 그려진 것을 그대로 찍으므로 홈페이지에 나가는
   * 모습과 어긋나지 않는다. 파일 이름의 번호는 네이버 탭의 [도식 N] 과 같다.
   */
  /* 네이버 본문에는 도식이 자리표시로만 들어간다. 에디터가 태그를 못 받기
   * 때문이다. 저장할 원본을 여기 따로 그려 둔다 — 본문 자리표시의 번호와
   * 같은 번호를 붙여야 사람이 어느 그림을 어디에 넣을지 안다.
   *
   * 예전에는 홈페이지 미리보기에서 캡처했다. 채널이 갈리면서 네이버
   * 드래프트에는 홈페이지 결과물이 없으므로 백엔드가 같은 figures.py 로
   * 그려서 보낸다. 도식 데이터는 여전히 한 벌이다. */
  /* 붙여넣은 뒤 손볼 것. 본문 데이터에 정렬·간격을 넣지 않고
   * 무엇을 어디서 고치면 되는지만 알려 준다 — 그 서식은 붙여넣기에서
   * 대부분 안 살아남는다. */
  function recipe(rows) {
    if (!rows || !rows.length) return '';
    return block('붙여넣은 뒤', rows.length + '곳', '',
      '<div class="out-b"><ul class="recipe">' +
        rows.map(function (r) {
          return '<li><b>' + UI.esc(r.where) + '</b>' +
                 '<span>' + UI.esc(r.what) + '</span>' +
                 '<em>' + UI.esc(r.why) + '</em></li>';
        }).join('') +
      '</ul></div>');
  }

  /* 본문 그림. 도식과 나란히 두되 만드는 주체가 달라 따로 둔다 —
   * 도식은 코드가 마크업으로 그리고 이건 생성 모델이 그린다.
   * **없어도 글이 나가는 것**이라 실패해도 막지 않는다. */
  function illustShop(plans) {
    var keys = Object.keys(plans || {});
    if (!keys.length) return '';
    var left = keys.filter(function (k) { return !plans[k].made; }).length;
    return block('본문 그림',
      keys.length + '장 · 본문의 [본문 그림 삽입] 자리에 넣습니다',
      (left ? '<button type="button" class="mini" id="il-make">' +
              (keys.length > left ? '남은 것 만들기' : '만들기') + '</button>' : ''),
      '<div class="out-b"><div class="ilrow">' +
        keys.map(function (k) {
          var p = plans[k];
          return '<div class="ilcard">' +
            (p.made
              ? '<img src="/api/draft/illust/' + k + '.png?t=' + Date.now() +
                '" alt="' + UI.esc(p.alt || '') + '">'
              : '<div class="ilslot">아직 없음</div>') +
            '<div class="ilcap"><b>' + k + '번 섹션</b>' +
            UI.esc(p.purpose || '') + '</div>' +
            (p.made ? '<button type="button" class="mini" data-il="' + k +
                      '">저장</button>' : '') +
            '</div>';
        }).join('') +
      '</div></div>');
  }

  function figureShop(figs, css) {
    if (!figs || !figs.length) return '';
    /* **도식 스타일을 여기 함께 넣는다.** 채널을 가르면서 figures.CSS 가
     * 홈페이지 결과물에만 실려서, 네이버는 class 만 있고 규칙이 없었다.
     * 브라우저 기본값으로 그려진 것을 캡처해 그대로 내보내고 있었다. */
    return (css ? '<style>' + css + '</style>' : '') +
      block('도식', figs.length + '개 · 본문의 [도식 N 삽입] 자리에 넣습니다',
      '<button type="button" class="mini" id="f-all">전부 저장</button>',
      '<div class="out-b" id="f-shop">' +
        figs.map(function (f) {
          return '<div class="fig-wrap" data-n="' + f.n + '">' +
                   '<div class="fig-no">도식 ' + f.n + '</div>' + f.html +
                   (f.takeaway ? '<p class="post-takeaway">' + UI.esc(f.takeaway) + '</p>' : '') +
                   '<button type="button" class="mini fig-one">이미지로 저장</button>' +
                 '</div>';
        }).join('') +
      '</div>');
  }

  /* 본문 그림 만들기·저장. 만들기는 몇 초 걸리므로 버튼을 잠근다. */
  function illustWire() {
    var mk = $('il-make');
    if (mk) mk.addEventListener('click', function () {
      run(mk, function () {
        return API.illust().then(function (r) {
          var bad = Object.keys(r.failed || {});
          if (bad.length) UI.toast(bad.length + '장을 못 만들었습니다');
          return load();
        });
      }, '만들었습니다');
    });

    [].slice.call(document.querySelectorAll('[data-il]')).forEach(function (b) {
      b.addEventListener('click', function () {
        var n = b.dataset.il;
        var a = document.createElement('a');
        a.href = '/api/draft/illust/' + n + '.png';
        a.download = '본문그림' + n + '.png';
        a.click();
      });
    });
  }

  function shopWire() {
    var shop = $('f-shop');
    if (!shop) return;
    var wraps = [].slice.call(shop.querySelectorAll('.fig-wrap'));
    var jobs = wraps.map(function (w) {
      var el = w.querySelector('figure.fig');
      return { el: el, name: '도식' + w.dataset.n + '.png' };
    }).filter(function (j) { return j.el; });

    wraps.forEach(function (w, i) {
      var btn = w.querySelector('.fig-one');
      if (!btn || !jobs[i]) return;
      btn.addEventListener('click', function () {
        run(btn, function () { return Shot.png(jobs[i].el, jobs[i].name); }, '저장했습니다');
      });
    });

    var ab = $('f-all');
    if (ab && jobs.length) ab.addEventListener('click', function () {
      run(ab, function () {
        return Shot.all(jobs, function (i, n) { ab.textContent = (i + 1) + ' / ' + n; });
      }, jobs.length + '장 저장했습니다');
    });
  }

  function shots() {
    var prev = $('s-prev');
    if (!prev) return;

    /* 코드 보기를 거쳐 오면 미리보기가 코드에서 다시 만들어지고, 그 코드에는
     * 버튼이 없다. 그래서 다시 붙여야 한다. 먼저 남은 것을 걷어낸다 —
     * 안 그러면 오갈 때마다 겹친다. */
    document.querySelectorAll('.fig-save').forEach(function (el) { el.remove(); });

    var figs = [].slice.call(prev.querySelectorAll('figure.fig'));
    if (!figs.length) return;

    var jobs = figs.map(function (el, i) {
      return { el: el, name: '도식' + (i + 1) + '-' + (el.dataset.fig || '도식') + '.png' };
    });

    figs.forEach(function (el, i) {
      var bar = document.createElement('div');
      bar.className = 'fig-save';
      bar.dataset.ui = '1';          // 결과물 코드에서 걷어낼 표시
      bar.innerHTML = '<span class="fig-no">도식 ' + (i + 1) + '</span>' +
                      '<button type="button" class="mini">이미지로 저장</button>';
      el.insertAdjacentElement('afterend', bar);
      var btn = bar.querySelector('button');
      btn.addEventListener('click', function () {
        run(btn, function () { return Shot.png(el, jobs[i].name); }, '저장했습니다');
      });
    });

    var all = document.createElement('div');
    all.className = 'fig-save all';
    all.dataset.ui = '1';
    all.innerHTML = '<span class="fig-no">도식 ' + figs.length + '장</span>' +
                    '<button type="button" class="mini">전부 저장</button>';
    prev.insertAdjacentElement('afterend', all);
    var ab = all.querySelector('button');
    ab.addEventListener('click', function () {
      run(ab, function () {
        return Shot.all(jobs, function (i, n) { ab.textContent = (i + 1) + ' / ' + n; });
      }, figs.length + '장 저장했습니다');
    });
  }

  /* 버튼 하나를 잠그고 결과를 그 자리에 알린다. 실패하면 이유를 남긴다 —
   * html2canvas 를 못 받는 자리에서 버튼만 죽어 있으면 원인을 알 수 없다. */
  function run(btn, fn, done) {
    var was = btn.textContent;
    btn.disabled = true;
    btn.textContent = '만드는 중…';
    fn().then(function () {
      btn.textContent = done;
    }, function (e) {
      btn.textContent = '실패 · ' + (e && e.message ? e.message : '알 수 없음');
    }).then(function () {
      setTimeout(function () { btn.disabled = false; btn.textContent = was; }, 2000);
    });
  }

  function wire() {
    document.querySelectorAll('.tab').forEach(function (b) {
      b.addEventListener('click', function () {
        document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        document.querySelectorAll('.pane').forEach(function (p) {
          p.hidden = p.dataset.p !== b.dataset.t;
        });
      });
    });

    /* ── 파생 뷰 ─────────────────────────────────────────── */

    /* 서식을 텍스트로.
     *
     * 태그를 보고 옮긴다. 예전에는 <strong> 이 들어 있으면 무조건 "■" 를
     * 붙였는데, 그러면 강조 박스가 소제목처럼 보이고 그 안의 문장이 통째로
     * 사라졌다. 체크 문항에는 "-" 와 "□" 가 겹쳐 붙었다.
     *
     * 이 결과는 text/plain 으로 복사된다. 에디터가 서식을 못 받을 때 쓰는
     * 자리라 여기서 뜻이 빠지면 되돌릴 방법이 없다. */
    function lines(el) {
      /* <br> 와 문단 경계를 줄바꿈으로 살린다. textContent 는 둘 다 그냥
         지운다 — 목록의 "제목설명", 강조 박스의 "핵심도입 준비의" 가
         붙어 나오던 이유다. */
      var t = el.innerHTML
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/(p|li|div|blockquote)>/gi, '\n');
      var box = document.createElement('div');
      box.innerHTML = t;
      return box.textContent.split('\n')
        .map(function (x) { return x.trim(); })
        .filter(Boolean);
    }

    function toText(root) {
      var out = [];

      [].forEach.call(root.children, function (el) {
        var tag = el.tagName;

        if (tag === 'OL') {
          [].forEach.call(el.children, function (li, i) {
            var L = lines(li);
            out.push((i + 1) + '. ' + (L[0] || ''));
            L.slice(1).forEach(function (x) { out.push(x); });
            out.push('');
          });
          return;
        }

        if (tag === 'UL') {
          /* 체크 문항에는 이미 □ 가 붙어 있다. 앞에 기호를 더 붙이지 않는다. */
          [].forEach.call(el.children, function (li) {
            var x = li.textContent.trim();
            out.push(/^[□■▢☐]/.test(x) ? x : '- ' + x);
          });
          out.push('');
          return;
        }

        if (tag === 'BLOCKQUOTE') {
          var head = el.querySelector('strong, b');
          var label = head ? head.textContent.trim() : '';
          var body = lines(el).join(' ');
          /* 라벨과 본문이 한 줄로 붙어 온다. 앞머리를 떼야 "[핵심] 핵심 …"
             처럼 두 번 나오지 않는다. */
          if (label && body.indexOf(label) === 0) {
            body = body.slice(label.length).trim();
          }
          out.push('[' + (label || '핵심') + ']');
          out.push(body);
          out.push('');
          return;
        }

        /* 소제목은 <p> 안이 통째로 <strong> 인 것뿐이다. 문장 일부만 굵은
           것은 소제목이 아니다. */
        var only = el.children.length === 1 &&
                   /^(STRONG|B)$/.test(el.children[0].tagName) &&
                   el.textContent.trim() === el.children[0].textContent.trim();
        if (only) {
          out.push('■ ' + el.textContent.trim());
          out.push('');
          return;
        }

        var L = lines(el);
        L.forEach(function (x) { out.push(x); });
        /* 체크 문항과 도식 표시줄은 이어져야 목록·묶음으로 읽힌다.
           문단마다 빈 줄을 넣으면 낱개로 흩어진다. */
        var tight = L.length === 1 && /^[□■▢☐━─]/.test(L[0]);
        if (!tight) out.push('');
      });

      return out.join('\n').replace(/\n{3,}/g, '\n\n').trim();
    }

    /* 네이버는 늘 서식 → 텍스트 한 방향이다.
       홈페이지는 미리보기와 코드 어느 쪽에서도 고칠 수 있으므로,
       지금 보고 있는 쪽을 원본으로 삼아 반대쪽을 다시 만든다. */
    function derive(dir) {
      var rich = $('n-rich'), text = $('n-body');
      if (rich && text) text.textContent = toText(rich);

      var prev = $('s-prev'), code = $('s-html');
      if (!prev || !code) return;
      if (dir === 'toPrev') { prev.innerHTML = code.textContent; cells(prev); shots(); }
      else { code.textContent = Edit.clean(prev); }
    }

    function sync() {
      var code = $('s-html');
      derive(code && !code.hidden ? 'toPrev' : null);
    }

    /* ── 고치기 ──────────────────────────────────────────── */

    function mark(el) {
      var box = el.closest('.out');
      if (!box) return;
      var host = box.querySelector('[data-edit-in]') || box.querySelector('[data-edit]');
      var dirty = Edit.changed(host);
      box.classList.toggle('dirty', dirty);
      var rv = box.querySelector('.revert');
      if (rv) rv.hidden = !dirty;
    }

    function done(dir) {
      return function (el) { derive(dir); mark(el); };
    }

    function cells(host) { Edit.inside(host, { onDone: done() }); }

    document.querySelectorAll('[data-edit]').forEach(function (el) {
      Edit.snapshot(el);
      Edit.open(el, { onDone: done() });
    });
    document.querySelectorAll('[data-edit-in]').forEach(function (host) {
      cells(host);
      Edit.snapshot(host);              // cell 표시까지 포함한 상태가 원본
    });
    document.querySelectorAll('[data-edit-code]').forEach(function (el) {
      Edit.open(el, { multiline: true, onDone: done('toPrev') });
    });

    document.querySelectorAll('.revert').forEach(function (b) {
      b.addEventListener('click', function () {
        var host = $(b.dataset.for);
        if (!host) return;
        Edit.restore(host);
        if (host.hasAttribute('data-edit-in')) cells(host);
        mark(host);
        derive();
      });
    });

    /* ── 복사 ────────────────────────────────────────────── */

    /* 파일로 내려받기. 복사가 막히는 환경도 있고, CMS 에 붙이기 전에
     * 브라우저로 열어 확인하고 싶을 때도 있다. 화면에서 고친 내용이
     * 반영되도록 복사와 같은 자리에서 sync() 를 먼저 부른다. */
    function dlName(ext) {
      var t = $('n-title');
      return UI.safeName(t ? t.textContent : '', ext);
    }

    /* 내려받는 파일은 브라우저로 열어 확인하는 용도다. 붙여넣기는 복사
     * 버튼이 맡는다.
     *
     * 결과물 코드는 조각이라 그대로 열면 doctype·글자셋·글꼴·본문 폭이 없어
     * 화면과 다르게 보인다. 껍데기를 씌워 내보내되, 어디부터가 붙여넣을
     * 부분인지 주석으로 표시한다. */
    /* 네이버 완성본 한 벌.
     *
     * 제목·본문·태그가 에디터에서 각각 다른 칸에 들어간다. 한 파일에 담되
     * 어느 칸에 넣는지 알아볼 수 있게 나눠 둔다.
     *
     * 본문 스타일은 <style> 로 걸지 않고 인라인으로 준다. 화면에서 드래그해
     * 복사할 때 <style> 은 따라오지 않기 때문이다 — 서식이 살아 있는 채로
     * 붙으려면 태그에 직접 붙어 있어야 한다. 에디터는 어차피 대부분
     * 지우지만, 지워져도 <strong>·<ol>·<blockquote> 는 남는다.
     */
    /* 스타일은 **백엔드가 이미 붙여 놨다**(brand.NAVER). 여기서 덧칠하지
     * 않는다 — 태그 종류만 보고 칠하면 소제목·리드·도식 자리를 구별하지
     * 못하고, 실제로 강조 박스가 브랜드 색 대신 회색(#ddd)으로 나갔다.
     *
     * 여기가 하는 일은 화면 전용 요소를 걷어 내는 것뿐이다. */
    function inlined(host) {
      var box = document.createElement('div');
      box.innerHTML = Edit.clean(host);
      box.querySelectorAll('[data-ui]').forEach(function (el) { el.remove(); });
      return box.innerHTML;
    }

    function naverFile(title, body, tags) {
      var esc = UI.esc;
      return '<!DOCTYPE html>\n<html lang="ko">\n<head>\n' +
        '<meta charset="utf-8">\n' +
        '<title>' + esc(title) + ' — 네이버 블로그용</title>\n' +
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/' +
        'pretendard@v1.3.9/dist/web/static/pretendard.min.css">\n' +
        '<style>\n' +
        'body{font-family:Pretendard,"Noto Sans KR",sans-serif;color:#1a1a1a;\n' +
        ' max-width:760px;margin:36px auto;padding:0 20px}\n' +
        '.lab{margin:28px 0 8px;font-size:12px;font-weight:700;color:#03C75A;\n' +
        ' letter-spacing:.08em}\n' +
        '.box{border:1px solid #e5e5e5;border-radius:6px;padding:18px 20px}\n' +
        '.how{background:#f5f5f5;border-radius:6px;padding:12px 16px;\n' +
        ' font-size:13px;color:#666;line-height:1.7}\n' +
        '</style>\n</head>\n<body>\n\n' +

        '<div class="how">' +
        '아래 <b>세 칸</b>을 네이버 글쓰기 화면의 같은 자리에 넣습니다.<br>' +
        '본문은 상자 안을 <b>드래그해서 복사</b>합니다. ' +
        'Ctrl+A 는 안내 문구까지 잡히니 본문만 끄세요.<br>' +
        '<b>붙여넣은 뒤에는 서식을 확인해 주세요.</b> 브라우저와 에디터 상태에 따라 ' +
        '굵기·목록·인용이 일부만 따라오거나 아예 안 따라올 수 있습니다. ' +
        '네이버는 외부 글을 그대로 붙여넣는 것을 권장하지 않습니다 — ' +
        '서식이 깨지면 메모장을 한 번 거쳐 글자만 붙이고 에디터에서 다시 잡는 편이 빠릅니다.<br>' +
        '<b>[도식 N 삽입]</b> 과 <b>[대표 이미지 삽입]</b> 자리는 저장해 둔 그림으로 바꿔 주세요.' +
        '</div>\n\n' +

        '<div class="lab">제목 칸</div>\n' +
        '<div class="box"><p style="margin:0;font-size:20px;font-weight:700;' +
        'letter-spacing:-0.02em">' + esc(title) + '</p></div>\n\n' +

        '<div class="lab">본문 칸 — 이 상자 안을 드래그해 복사</div>\n' +
        '<div class="box" style="font-size:16px;line-height:1.9">\n' +
        body + '\n</div>\n\n' +

        (tags
          ? '<div class="lab">태그 칸</div>\n' +
            '<div class="box"><p style="margin:0;color:#03C75A">' +
            esc(tags) + '</p></div>\n\n'
          : '') +

        '</body>\n</html>\n';
    }

    function standalone(title, body) {
      return '<!DOCTYPE html>\n<html lang="ko">\n<head>\n' +
        '<meta charset="utf-8">\n' +
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n' +
        '<title>' + UI.esc(title) + '</title>\n' +
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/' +
        'pretendard@v1.3.9/dist/web/static/pretendard.min.css">\n' +
        '<style>\n' +
        'body{font-family:Pretendard,"Noto Sans KR",sans-serif;color:#111827;\n' +
        ' max-width:860px;margin:48px auto;padding:0 24px;line-height:1.7}\n' +
        'h1{font-size:32px;letter-spacing:-0.02em;margin:0 0 20px}\n' +
        'h2{font-size:22px;letter-spacing:-0.02em;margin:44px 0 14px}\n' +
        'p{margin:0 0 18px;color:#374151}\n' +
        '.lead{font-size:18px;color:#4B5563}\n' +
        '</style>\n</head>\n<body>\n\n' +
        '<!-- ↓↓↓ 여기서부터 아래 주석까지가 CMS 에 붙일 부분입니다 ↓↓↓ -->\n\n' +
        body + '\n\n' +
        '<!-- ↑↑↑ 여기까지 ↑↑↑ -->\n\n</body>\n</html>\n';
    }

    var sdl = $('s-dl');
    if (sdl) sdl.addEventListener('click', function () {
      sync();
      var t = $('n-title');
      UI.download(standalone(t ? t.textContent : '결과물', $('s-html').textContent),
                  dlName('.html'), 'text/html');
    });

    var ndl = $('n-dl');
    if (ndl) ndl.addEventListener('click', function () {
      sync();
      UI.download($('n-body').textContent, dlName('.txt'), 'text/plain');
    });

    /* 네이버 완성본을 코드로 받는다.
     *
     * 복사 버튼이 서식을 클립보드에 싣지만, LAN 으로 열면(http://192.168.x.x)
     * 서식 복사가 막히는 브라우저가 있다. 그때는 이 파일을 열어 화면에서
     * 전체 선택해 복사하면 서식이 그대로 따라간다.
     *
     * 에디터가 받는 태그만 담는다. 껍데기의 style 은 <body> 바깥이라
     * 선택 범위에 들어가지 않는다. */
    var nhtml = $('n-html');
    if (nhtml) nhtml.addEventListener('click', function () {
      sync();
      var t = $('n-title');
      var title = t ? t.textContent : '결과물';
      var tags = $('n-tags');
      UI.download(naverFile(title, inlined($('n-rich')), tags ? tags.textContent : ''),
                  UI.safeName(title + '-네이버', '.html'), 'text/html');
    });

    document.querySelectorAll('.copy').forEach(function (b) {
      b.addEventListener('click', function () {
        sync();
        var src = $(b.dataset.src);
        var rich = b.dataset.html ? $(b.dataset.html) : null;
        Edit.copy(b, rich ? Edit.clean(rich) : null, src ? src.textContent : '');
      });
    });

    /* ── 보기 전환 ───────────────────────────────────────── */

    function toggle(btn, a, bEl, labelA, labelB) {
      if (!btn) return;
      btn.addEventListener('click', function () {
        sync();
        var showB = bEl.hidden;
        bEl.hidden = !showB;
        a.hidden = showB;
        btn.textContent = showB ? labelA : labelB;
      });
    }
    toggle($('n-toggle'), $('n-rich'), $('n-body'), '서식으로 보기', '텍스트로 보기');
    toggle($('s-toggle'), $('s-prev'), $('s-html'), '미리보기', '코드 보기');

    derive();
  }

  UI.boot();
  /* 결과물을 받아 그린다. **다시 부를 수 있어야 한다** — 본문 그림을
   * 만들고 나면 화면이 그걸 받아야 하는데, 처음 한 번만 받으면 만든
   * 그림이 계속 "아직 없음" 으로 남는다. */
  function load() {
    return Promise.all([API.steps(), API.result()])
      .then(function (res) {
        if (UI.guard(res[1])) return;
        render(res[0].steps, res[1]);
      });
  }

  load().catch(function (e) { UI.fail(UI.why(e)); });
})();
