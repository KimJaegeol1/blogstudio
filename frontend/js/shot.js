/* 화면에 그려진 것을 그림 파일로 저장한다.
 *
 * 홈페이지 쪽 도식은 HTML 마크업이라 그대로 붙이면 되지만, 네이버 에디터는
 * 표와 도식을 받지 않는다. 그래서 지금은 사람이 홈페이지 탭을 열어 화면을
 * 캡처하고 크기를 맞춰 넣는다 — 글 한 편에 도식 수만큼 반복된다.
 *
 * 새로 그리지 않고 이미 렌더된 DOM 을 찍는다. 같은 데이터로 두 번 그리면
 * 홈페이지에 나가는 모습과 네이버에 붙는 그림이 서로 어긋난다.
 *
 * html2canvas 는 필요할 때 CDN 에서 받아 온다. 처음 버튼을 누르기 전에는
 * 내려받지 않는다. 못 받으면 버튼이 죽은 채로 남지 않게 이유를 알린다.
 */
window.Shot = (function () {

  var CDN = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
  var pending = null;

  function lib() {
    if (window.html2canvas) return Promise.resolve(window.html2canvas);
    if (pending) return pending;
    pending = new Promise(function (ok, no) {
      var done = false;
      function settle(fn, v) { if (!done) { done = true; fn(v); } }

      var s = document.createElement('script');
      s.src = CDN;
      s.onload = function () {
        window.html2canvas ? settle(ok, window.html2canvas)
                           : settle(no, new Error('받았지만 비어 있습니다'));
      };
      s.onerror = function () { settle(no, new Error('내려받지 못했습니다')); };
      document.head.appendChild(s);

      // onerror 가 안 오는 경우가 있다. 사내망 프록시가 응답을 물고 있으면
      // 성공도 실패도 아닌 채로 남아 버튼이 "만드는 중…" 에서 멈춘다.
      setTimeout(function () {
        settle(no, new Error('시간 초과 · 인터넷 연결을 확인하세요'));
      }, 8000);
    });
    return pending.catch(function (e) { pending = null; throw e; });
  }

  /* 캡처할 때 쓰는 고정 폭과 여백.
   *
   * 미리보기 영역 폭을 그대로 찍으면 창을 좁혔을 때 좁은 이미지가 나온다.
   * 블로그에 올릴 그림은 창 크기와 무관해야 하므로 화면 밖에 고정 폭으로
   * 다시 그려 놓고 찍는다. 여백을 두르는 것은 다른 이미지와 나란히 놓였을 때
   * 도식만 가장자리에 붙어 보이지 않게 하려는 것이다. */
  /* 폭·글자 크기·여백은 채널마다 다르다. 네이버는 휴대폰에서 읽히므로
   * 폭이 좁고 글자가 크다. 값은 백엔드가 준다(data/channels.py 의 CAPTURE) —
   * 여기 박아 두면 화면과 서버 두 곳을 맞춰야 한다.
   *
   * 값이 안 오면 홈페이지 기준으로 떨어진다. */
  var STYLE = { width: 900, font_size: 16, padding: 24 };

  function setStyle(s) {
    if (s && s.width) STYLE = s;
  }

  /* 캡처 상자에만 거는 덧씌우기. 화면의 미리보기는 건드리지 않는다 —
   * 미리보기는 홈페이지에 나갈 모습이고, 네이버용 배치는 찍는 순간에만
   * 필요하다. 상자 안으로 범위를 좁혀야 미리보기가 안 흔들린다. */
  function styleTag() {
    if (!STYLE.css) return null;
    var st = document.createElement('style');
    st.textContent = STYLE.css.replace(/^\s*\./gm, '.bs-shot .');
    return st;
  }

  /* 도식은 본문보다 넓게 찍는다. 같은 680px 로 찍으면 4열 대조표의 열이
   * 짓눌려 낱말 가운데서 줄이 바뀐다. 캡처본은 네이버 본문에서 화면 폭에
   * 맞춰 줄어드니 원본을 넓게 찍어도 최종 크기는 같다. */
  function widthOf(el) {
    var w = STYLE.figure_widths || {};
    var fig = el.matches && el.matches('[data-fig]')
      ? el : (el.querySelector ? el.querySelector('[data-fig]') : null);
    var kind = fig && fig.getAttribute('data-fig');
    return (kind && w[kind]) || STYLE.width;
  }

  function framed(el) {
    var WIDTH = widthOf(el), PAD = STYLE.padding;
    var box = document.createElement('div');
    /* id 가 아니라 class 다. 한 번에 하나만 만들지만, id 로 두면
     * 미리보기처럼 여러 개를 나란히 둘 때 문서에 같은 id 가 둘
     * 생기고 querySelector 가 첫 것만 잡는다. */
    box.className = 'bs-shot';
    box.style.cssText =
      'position:fixed;left:-99999px;top:0;background:#FFFFFF;' +
      'font-size:' + STYLE.font_size + 'px;' +
      'width:' + WIDTH + 'px;padding:' + PAD + 'px;box-sizing:border-box';
    var clone = el.cloneNode(true);
    clone.style.margin = '0';
    clone.style.maxWidth = 'none';
    box.appendChild(clone);
    var st = styleTag();
    if (st) box.appendChild(st);
    document.body.appendChild(box);
    return box;
  }

  /* 요소 하나를 PNG 로 내려받는다. scale 2 는 블로그에 올렸을 때
   * 글자가 뭉개지지 않게 하려는 것이다. */
  function png(el, name) {
    var box = null;
    return lib()
      .then(function (h2c) {
        box = framed(el);
        var w = widthOf(el);
        return h2c(box, { backgroundColor: '#FFFFFF', scale: 2, logging: false,
                          width: w, windowWidth: w });
      })
      .then(function (canvas) {
        if (box) { box.remove(); box = null; }
        return new Promise(function (ok, no) {
          canvas.toBlob(function (blob) {
            blob ? (save(blob, name), ok(name)) : no(new Error('그림으로 못 바꿨습니다'));
          }, 'image/png');
        });
      })
      .catch(function (e) {
        if (box) { box.remove(); box = null; }
        throw e;
      });
  }

  /* 이미 있는 이미지를 정사각으로 잘라 내려받는다.
   *
   * 대표 이미지는 16:9 로 만든다. 홈페이지는 그대로 쓰지만 네이버 목록은
   * 정사각이라 가로가 잘린다. 가운데를 남기고 자른 판을 따로 준다. */
  function square(img, name) {
    return new Promise(function (ok, no) {
      var side = Math.min(img.naturalWidth, img.naturalHeight);
      if (!side) return no(new Error('이미지를 아직 못 읽었습니다'));

      var c = document.createElement('canvas');
      c.width = c.height = side;
      c.getContext('2d').drawImage(
        img,
        (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side,
        0, 0, side, side);

      c.toBlob(function (blob) {
        blob ? (save(blob, name), ok(name)) : no(new Error('그림으로 못 바꿨습니다'));
      }, 'image/png');
    });
  }

  function save(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /* 여러 장을 이어서 내려받는다. 한꺼번에 부르면 브라우저가 두 번째부터
   * 막으므로 간격을 둔다. */
  function all(jobs, each) {
    return jobs.reduce(function (chain, j, i) {
      return chain.then(function () {
        if (each) each(i, jobs.length);
        return png(j.el, j.name);
      }).then(function () {
        return new Promise(function (r) { setTimeout(r, 400); });
      });
    }, Promise.resolve());
  }

  return { png: png, setStyle: setStyle, all: all, square: square, lib: lib };
})();
