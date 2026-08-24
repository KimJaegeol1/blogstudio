/* 8단계 최종 확인 */
(function () {
  UI.boot();
  Promise.all([API.steps(), API.step('approve')])
    .then(function (res) {
      var STEPS = res[0].steps, D = res[1];
      if (UI.guard(D)) return;

      var s = D.step, by = {};
      D.done.forEach(function (x) { by[x.key] = x; });
      var label = function (k) { return UI.esc((by[k] || {}).label); };

      var chips = ((by.outline || {}).detail || '').split('→')
        .map(function (x) { return x.trim() ? '<span>' + UI.esc(x.trim()) + '</span>' : ''; })
        .join('');

      UI.$('app').innerHTML =
        '<div class="page">' +
          UI.stepbar(STEPS, 'approve', D.done.map(function (x) { return x.key; })) +
          '<div class="eyebrow">' + UI.esc(s.eyebrow) + '</div>' +
          '<div class="h1">' + UI.esc(s.h1) + '</div>' +
          UI.sec('정한 것 전부', D.done.length + '개', UI.carry(D.done, { big: true })) +
          UI.sec('이렇게 나갑니다', '',
            '<div class="write lead">' +
              '<div class="pv-t">' + label('title') + '</div>' +
              '<div class="pv-m">' + label('type') + ' · ' + label('reader') +
                ' 대상 · ' + label('outline') + ' · 근거 ' + label('evidence') + '</div>' +
              '<div class="pv-s">' + chips + '</div></div>') +
        '</div>' +
        UI.actions(
          '<a class="btn" href="/step.html?s=evidence">← 이전</a>' +
          '<span class="act-note" id="note">확인했으면 글을 만듭니다</span>' +
          '<button type="button" class="btn primary" id="make">이대로 만들기</button>');

      /* 여기서 본문 프롬프트가 한 번 돈다. 30초 넘게 걸리므로 버튼을 잠근다 —
         잠그지 않으면 안 눌린 줄 알고 다시 눌러 같은 프롬프트가 두 번 돈다. */
      UI.$('make').addEventListener('click', function () {
        var undo = UI.busy(this, '글을 쓰는 중…');
        if (!undo) return;
        UI.$('note').textContent = '한참 걸립니다. 창을 닫지 마세요.';

        API.write()
          .then(function (r) {
            if (r.ok) UI.go('/result.html');       // 넘어가니 되돌리지 않는다
            else { undo(); UI.$('note').textContent = r.detail || r.reason; }
          })
          .catch(function () {
            undo();
            UI.$('note').textContent = '만들지 못했습니다. 다시 눌러 주세요.';
          });
      });

      UI.title(s.h1);
    })
    .catch(function (e) { UI.fail(e.message); });
})();
