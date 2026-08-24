/* 1단계 소재 선택 */
(function () {
  var app = UI.$('app');
  var state = UI.query('state') || 'normal';
  var D, STEPS, pick;

  function topicCard(t, rec) {
    var badge = rec && rec.topic_id === t.topic_id ? '<span class="badge">추천</span>' : '';
    return UI.card({
      id: t.topic_id, name: 'topic', value: t.topic_id,
      sel: t.topic_id === D.selected, down: t.verdict === 'down',
      title: UI.esc(t.topic_title) + badge,
      summary: t.topic_summary,
      meta: UI.esc(t.collected_date) + ' · 근거기사 ' + t.sources.length + '건 · ' +
        '<span class="score">점수 ' + t.final_score.toFixed(2) + '</span> ' +
        '<span class="sub">(연관 ' + t.business_relevance.toFixed(2) +
        ' / 수요 ' + t.search_demand.toFixed(2) + ')</span>',
      extra:
        '<span class="reason">' + UI.esc(t.rationale) + '</span>' +
        '<span class="srcs">' + t.sources.map(function (s) {
          return '<div><a href="' + UI.esc(s.url) + '" target="_blank" rel="noopener">' +
            UI.esc(s.press) + '「' + UI.esc(s.headline) + '」↗</a></div>';
        }).join('') + '</span>',
      foot: UI.fb({ verdict: t.verdict, note: t.note,
                    tags: D.down_tags, on: t.tags })
    });
  }

  function list(rec) {
    if (D.error) return '<div class="err">' +
      '<div class="err-t">소재 파일을 읽지 못했습니다</div>' +
      '<div class="err-s">파일이 제자리에 있는지, 엑셀에서 열어 둔 채로 두지 않았는지 확인해 주세요.<br>' +
      '엑셀이 열려 있으면 파일이 잠겨 읽히지 않습니다.</div>' +
      '<div class="err-btns">' +
        '<button type="button" class="mini solid" id="retry">다시 시도</button>' +
        '<button type="button" class="mini" id="tolead">직접 쓰기로 시작</button>' +
      '</div><details><summary>자세히</summary><pre>' + UI.esc(D.error) + '</pre></details></div>';

    if (!D.topics.length) return '<div class="empty">' +
      '<div class="empty-t">새로 들어온 소재가 없습니다</div>' +
      '<div class="empty-s">' + UI.esc(D.loaded_at) +
      '에 마지막으로 불러왔습니다. 직접 주제를 쓰거나 지난주 소재를 다시 볼 수 있습니다.</div></div>';

    return '<div class="list" id="list">' +
      D.topics.map(function (t) { return topicCard(t, rec); }).join('') +
      '</div><div class="list-foot" id="listfoot"></div>';
  }

  function render() {
    var rec = D.recommended;
    var cnt = D.error ? '불러오지 못함'
            : D.topics.length ? UI.esc(D.loaded_at) + ' · ' + D.topics.length + '건'
            : UI.esc(D.loaded_at) + ' 마지막 확인';

    app.innerHTML =
      '<div class="page">' +
        UI.stepbar(STEPS, 'topic', []) +
        '<div class="eyebrow">SOURCE</div><div class="h1">소재 선택</div>' +
        UI.sec(D.is_last ? '지난주 소재' : '불러온 소재', cnt,
          (D.is_last ? '<div class="note-bar">지난주에 불러온 소재입니다. 새 소재는 <a href="/">여기</a>에서 확인하세요.</div>' : '') +
          list(rec)) +
        UI.sec('직접 쓰기', '',
          UI.write('주제를 한 줄로. 예) DPP 시행 앞두고 기업이 준비할 것', D.custom,
                   { head: '쓰고 싶은 주제가 따로 있다면', lead: !D.topics.length,
                     hint: '여기에 쓰면 위에서 고른 카드는 무시됩니다.',
                     buttons: '<button type="button" class="mini solid" id="start">이걸로 시작</button>' }) +
          (!D.topics.length && !D.error
            ? '<div class="relink"><a href="/?state=last">지난주 소재 다시 보기</a></div>' : '')) +
      '</div>' +
      UI.actions('<span class="act-note" id="note"></span>' +
                 '<button type="button" class="btn primary" id="next">다음 →</button>');

    var foot = UI.scrollFoot('list', 'listfoot');

    pick = UI.picker({
      name: 'topic', multi: false, after: foot,
      message: function (typed, on) {
        if (typed) return '직접 쓴 주제로 진행합니다';
        if (on.length) return '선택: ' + on[0].closest('.card')
          .querySelector('.card-t').textContent.trim().replace(/\s*추천$/, '');
        if (rec) return '선택 없음 — 추천 소재 「' + rec.topic_title + '」로 진행합니다';
        return '고를 소재가 없습니다. 직접 써 주세요.';
      }
    });

    feedback();
    UI.$('next').addEventListener('click', start);
    var s = UI.$('start'); if (s) s.addEventListener('click', start);
    var r = UI.$('retry'); if (r) r.addEventListener('click', function () { location.reload(); });
    var l = UI.$('tolead'); if (l) l.addEventListener('click', function () { UI.$('dw').focus(); });
  }

  /* 소재마다 붙는 좋음·별로·이유. 별로를 누르면 선택도 풀고 카드를 흐리게 한다. */
  function feedback() {
    pick.cards().forEach(function (card) {
      UI.fbWire(card, function (v) {
        return API.feedback({ step: 'topic', option_id: card.dataset.id,
                              verdict: v.verdict, tags: v.tags, note: v.note });
      }, {
        onDown: function (down) {
          card.classList.toggle('down', down);
          if (down) pick.unset(card);
          pick.refresh();
        }
      });
    });
  }

  function start(e) {
    var undo = UI.busy(e.currentTarget, '시작하는 중…');
    if (!undo) return;                         // 이미 누른 상태면 무시

    function stop(msg) { undo(); UI.$('note').textContent = msg; }

    API.pickTopic({ topic_id: pick.values()[0] || null, custom: pick.text() })
      .then(function (r) {
        if (r.ok) UI.go(UI.stepUrl(r.next, 2));
        else stop('고를 소재가 없습니다. 직접 써 주세요.');
      })
      .catch(function () { stop('시작하지 못했습니다. 다시 눌러 주세요.'); });
  }

  UI.boot();
  UI.title('소재 선택');
  Promise.all([API.steps(), API.topics(state)])
    .then(function (res) { STEPS = res[0].steps; D = res[1]; render(); })
    .catch(function (e) { UI.fail(e.message); });
})();
