/* 2~7단계. 단계마다 다른 건 백엔드가 주는 선택지뿐이다. */
(function () {
  var app = UI.$('app');
  var key = UI.query('s') || 'reader';
  var D, STEPS, DOCS = [];

  function render() {
    var s = D.step;
    var prev = STEPS[s.no - 2];
    var canWrite = s.custom !== false;

    var opts = D.options.length
      ? '<div class="list">' + D.options.map(function (o) {
          return UI.card({
            id: o.id, name: 'choice', value: o.id, multi: s.multi,
            /* 백엔드가 정한다. 화면이 상태를 보고 다시 판단하지 않는다. */
            selectable: o.selectable,
            /* 첫 후보가 추천이다. 백엔드가 메타 앞에 "추천 · 이유" 를
             * 붙여 두므로 화면은 그 글자로 알아본다 — 규칙을 두 곳에
             * 두지 않는다. */
            pick: (o.meta || '').indexOf('추천 · ') === 0 ||
                  (o.meta || '') === '추천',
            sel: D.selected.indexOf(o.id) >= 0,
            title: UI.esc(o.title), summary: o.summary, meta: UI.esc(o.meta),
            detail: Shape.detail(s.key, o.payload),
            copy: Shape.text(s.key, o.payload),
            edit: canWrite && Shape.text(s.key, o.payload) != null,
            foot: UI.fb({ hint: '이 후보를 어떻게 봤는지 한 줄 (선택)' })
          });
        }).join('') + '</div>'
      : '<div class="empty"><div class="empty-t">고를 게 없습니다</div>' +
        '<div class="empty-s">' +
        (canWrite ? '아래에 직접 써 주세요.' : '선택지를 불러오지 못했습니다.') +
        '</div></div>';

    app.innerHTML =
      '<div class="page">' +
        UI.stepbar(STEPS, s.key, D.done.map(function (x) { return x.key; })) +
        '<div class="eyebrow">' + UI.esc(s.eyebrow) + '</div>' +
        '<div class="h1">' + UI.esc(s.h1) + '</div>' +
        (D.done.length
          ? UI.sec('지금까지 정한 것', D.done.length + '개', UI.carry(D.done)) : '') +
        /* 고르기 전에 알아야 할 것. 결과물을 만든 뒤에 알면 늦다. */
        (D.warn ? '<div class="warn-bar">' + UI.esc(D.warn) + '</div>' : '') +
        (D.mock
          ? '<div class="mock-bar">개발용 견본입니다 · ' +
            'OPENAI_API_KEY 가 없어 실제 후보를 만들지 않았습니다</div>' : '') +
        (s.upload
          ? UI.sec('자료 올리기', DOCS.length ? DOCS.length + '건' : '',
                   UI.uploader(DOCS)) : '') +
        UI.sec('고르기', s.multi ? '여러 개 고를 수 있습니다' : '하나만', opts) +
        (canWrite ? UI.sec('직접 쓰기',
              s.multi ? '고른 것과 함께 담깁니다' : '', UI.write(D.hint, D.written)) : '') +
      '</div>' +
      UI.actions(
        '<a class="btn" href="' + UI.stepUrl(prev.key, prev.no) + '">← 이전</a>' +
        '<span class="act-note" id="note"></span>' +
        '<button type="button" class="btn primary" id="next">다음 →</button>');

    /* 여러 개를 담는 단계는 고른 것과 쓴 것이 함께 확정된다(both). 하나만
     * 고르는 단계는 둘 중 하나다 — 독자도 각도도 제목도 하나여야 한다. */
    var pick = UI.picker({
      name: 'choice', multi: !!s.multi, both: !!s.multi,
      message: function (typed, on) {
        var lines = typed ? typed.split('\n').filter(function (x) {
          return x.trim();
        }).length : 0;

        if (s.multi) {
          if (!on.length && !lines) return '고르거나 직접 써야 다음으로 넘어갑니다';
          var parts = [];
          if (on.length) parts.push('선택 ' + on.length + '건');
          if (lines) parts.push('직접 쓴 것 ' + lines + '건');
          return parts.join(' · ') + ' — 모두 담깁니다';
        }

        if (typed) return '직접 쓴 내용으로 진행합니다';
        if (!on.length && !canWrite) return '하나를 골라야 다음으로 넘어갑니다';
        if (on.length === 1) return '선택: ' +
          on[0].closest('.card').querySelector('.card-t').textContent.trim();
        return '고르거나 직접 써야 다음으로 넘어갑니다';
      }
    });

    /* 펼침 영역이 있는 카드에 펼치기·복사를 붙인다. 복사할 문자열은 HTML 에
     * 심지 않고 여기서 들고 있는다 — 심으면 줄바꿈이 살아남지 못한다. */
    var texts = {};
    D.options.forEach(function (o) {
      var t = Shape.text(s.key, o.payload);
      if (t != null) texts[o.id] = t;
    });

    /* 고쳐 쓰기 — 카드 내용을 직접 쓰기 칸에 넣는다. 넣으면 UI.picker 가
     * 카드 선택을 알아서 풀고, 그 뒤로는 쓴 내용이 확정값이 된다. */
    UI.expand(texts, function (t) {
      var dw = UI.$('dw');
      if (!dw) return;
      dw.value = t;
      dw.dispatchEvent(new Event('input', { bubbles: true }));
      dw.focus();
      dw.setSelectionRange(t.length, t.length);
      dw.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    /* 칸 아래 넣기 버튼과 실시간 결과. 파서가 있는 단계에만 붙는다. */
    if (canWrite) Shape.setup(s.key, UI.$('dw'));

    /* 파일을 받는 단계면 상자에 동작을 붙인다. 목록이 바뀌면 후보도 달라지므로
     * 화면 전체를 다시 받는다 — 올린 문서가 카드로도 나타나야 한다. */
    if (s.upload) UI.upWire(reload);

    /* 후보마다 붙는 좋음·별로. 이유 칩은 아직 없다 — 무엇이 반복되는
     * 이유인지는 메모가 쌓여야 알 수 있다. 표시 상태는 저장하지 않는다. */
    pick.cards().forEach(function (card) {
      UI.fbWire(card, function (v) {
        return API.feedback({ step: s.key, option_id: card.dataset.id,
                              verdict: v.verdict, tags: v.tags, note: v.note });
      });
    });

    UI.$('next').addEventListener('click', function () {
      var typed = pick.text().trim();
      // 직접 쓴 값은 확정할 때 프롬프트가 한 번 더 돈다. 기다린다고 알려 준다.
      var undo = UI.busy(this, typed ? '정리하는 중…' : '넘어가는 중…');
      if (!undo) return;                       // 이미 누른 상태면 무시

      function stop(msg) { undo(); UI.$('note').textContent = msg; }

      API.confirm(s.key, { choice: pick.values(), custom: pick.text() })
        .then(function (r) {
          if (r.ok) UI.go(UI.stepUrl(r.next, s.no + 1));   // 넘어가니 되돌리지 않는다
          else stop(r.detail || (canWrite
            ? '고르거나 직접 써야 다음으로 넘어갑니다'
            : '하나를 골라야 다음으로 넘어갑니다'));
        })
        .catch(function () { stop('저장하지 못했습니다. 다시 눌러 주세요.'); });
    });

    UI.title(s.h1);
  }

  /* 단계 화면 한 벌을 받아 그린다. 파일을 받는 단계면 문서 목록도 같이 받는다. */
  function load() {
    var jobs = [API.step(key)];
    return Promise.all(jobs).then(function (r) {
      D = r[0];
      if (UI.guard(D)) return null;
      if (!D.step.upload) { DOCS = []; return D; }
      return API.docs().then(function (u) {
        DOCS = (u && u.ok) ? u.docs : [];
        return D;
      });
    });
  }

  /* 다시 그리다 터지면 **화면이 그대로 멈춘다.** 올린 뒤 아무 변화가
   * 없어 보이는 것이 그 자리였다 — 사람은 업로드가 실패한 줄 안다. */
  function reload() {
    return load()
      .then(function (d) { if (d) render(); })
      .catch(function (e) { UI.fail(UI.why(e)); });
  }

  UI.boot();
  API.steps()
    .then(function (r) { STEPS = r.steps; return load(); })
    .then(function (d) { if (d) render(); })
    .catch(function (e) { UI.fail(UI.why(e)); });
})();
