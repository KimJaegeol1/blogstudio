/* 더블클릭해서 그 자리에서 고치기 + 클립보드.
 *
 * 어느 화면에 붙어도 되게 만들었다. 무엇을 고칠 수 있는지, 고친 뒤
 * 무엇을 다시 만들지는 부르는 쪽이 정한다.
 */
window.Edit = (function () {

  /* 편집용 표시는 결과물에 나가면 안 된다. 사본에서 걷어낸다. */
  /* 미리보기 DOM 에서 결과물 코드를 만든다.
   *
   * 화면에만 있는 조각을 걷어내야 한다. 도식마다 붙는 [이미지로 저장] 버튼이
   * 미리보기 안에 꽂히는데, 그대로 두면 복사한 HTML 과 내려받은 파일에
   * 버튼 마크업이 그대로 실려 나간다. 실제로 그렇게 나갔다.
   *
   * data-ui 를 단 것은 전부 화면용이다. 새 조각을 붙일 때 이 표시만 달면
   * 여기를 다시 고칠 일이 없다. */
  function clean(host) {
    var c = host.cloneNode(true);
    c.querySelectorAll('[data-ui]').forEach(function (el) { el.remove(); });
    c.querySelectorAll('.cell').forEach(function (el) {
      el.classList.remove('cell');
      el.removeAttribute('contenteditable');
      if (!el.getAttribute('class')) el.removeAttribute('class');
    });
    return c.innerHTML.trim();
  }

  function open(el, opt) {
    opt = opt || {};
    el.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      el.contentEditable = 'true';
      el.classList.add('editing');
      el.focus();
    });
    el.addEventListener('blur', function () {
      el.removeAttribute('contenteditable');
      el.classList.remove('editing');
      if (opt.onDone) opt.onDone(el);
    });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); el.blur(); return; }
      /* 코드는 줄바꿈이 필요하다. 문단·소제목은 Enter 로 끝낸다. */
      if (e.key === 'Enter' && !opt.multiline) { e.preventDefault(); el.blur(); }
    });
    /* 붙여넣기는 서식 없이 — 다른 데서 복사한 스타일이 딸려오면 지저분해진다 */
    el.addEventListener('paste', function (e) {
      e.preventDefault();
      var t = (e.clipboardData || window.clipboardData).getData('text/plain');
      document.execCommand('insertText', false, opt.multiline ? t : t.replace(/\n+/g, ' '));
    });
    return el;
  }

  /* 안쪽 요소를 하나씩 연다. 소제목을 고치면 굵은 채로 써지고,
     태그 밖으로 나갈 일이 없다. */
  var LEAF = 'p, strong, b, li, h1, h2, h3, a, span';

  function inside(host, opt) {
    host.querySelectorAll(LEAF).forEach(function (el) {
      if (el.children.length) return;        // 안에 또 요소가 있으면 그건 그릇이다
      if (!el.textContent.trim()) return;
      el.classList.add('cell');
      open(el, opt);
    });
    return host;
  }

  /* 되돌릴 수 있게 원본을 들고 있는다 */
  function snapshot(host) { host.dataset.orig = host.innerHTML; }
  function changed(host) { return host.innerHTML.trim() !== (host.dataset.orig || '').trim(); }
  function restore(host) { host.innerHTML = host.dataset.orig; }

  /* ── 클립보드 ────────────────────────────────────────────── */

  function flash(b) {
    b.classList.add('ok');
    setTimeout(function () { b.classList.remove('ok'); }, 900);
  }

  function selectCopy(html, b) {
    var box = document.createElement('div');
    box.innerHTML = html;
    box.setAttribute('style', 'position:fixed;left:-9999px;top:0;');
    document.body.appendChild(box);
    var sel = window.getSelection(), r = document.createRange();
    r.selectNodeContents(box);
    sel.removeAllRanges(); sel.addRange(r);
    try { document.execCommand('copy'); flash(b); } catch (e) {}
    sel.removeAllRanges();
    document.body.removeChild(box);
  }

  /* 서식과 텍스트를 함께 싣는다. 받는 쪽이 서식을 못 받으면 텍스트로 떨어진다. */
  function copy(btn, html, text) {
    if (html) {
      if (navigator.clipboard && window.ClipboardItem && window.isSecureContext) {
        navigator.clipboard.write([new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([text], { type: 'text/plain' })
        })]).then(function () { flash(btn); })
          .catch(function () { selectCopy(html, btn); });
      } else {
        selectCopy(html, btn);
      }
      return;
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { flash(btn); });
    } else {
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); flash(btn); } catch (e) {}
      document.body.removeChild(ta);
    }
  }

  return { clean: clean, open: open, inside: inside,
           snapshot: snapshot, changed: changed, restore: restore, copy: copy };
})();
