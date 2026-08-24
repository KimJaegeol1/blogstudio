/* 백엔드와 이야기하는 유일한 파일.
 *
 * 화면 코드는 fetch 를 직접 부르지 않는다. 여기 함수만 부른다.
 * 백엔드 주소나 응답 모양이 바뀌면 이 파일만 고친다.
 */
window.API = (function () {

  async function call(method, path, body) {
    var opt = { method: method, credentials: 'same-origin' };
    if (body !== undefined) {
      opt.headers = { 'Content-Type': 'application/json' };
      opt.body = JSON.stringify(body);
    }
    var res = await fetch(path, opt);
    if (!res.ok) {
      /* **거절 사유를 몸통에서 꺼낸다.** 상태 코드만 던지면 "왜" 가
       * 화면까지 안 간다 — PDF 를 올려 둔 사람에게 "빈 입력" 이라고
       * 말하는 것과 아무것도 안 한 사람에게 그러는 것은 다르다. */
      var why = null;
      try { why = await res.json(); } catch (e) { /* 본문이 없을 수 있다 */ }
      var err = new Error((why && (why.detail || why.reason))
        || (method + ' ' + path + ' → ' + res.status));
      err.reason = why && why.reason;
      throw err;
    }
    return res.json();
  }

  var get = function (p) { return call('GET', p); };
  var post = function (p, b) { return call('POST', p, b || {}); };

  return {
    steps:      function ()            { return get('/api/steps'); },

    topics:     function (state)       { return get('/api/topics?state=' + encodeURIComponent(state || 'normal')); },
    pickTopic:  function (body)        { return post('/api/topics/pick', body); },

    /* 소재·단계 후보·결과물 평가가 모두 여기로 간다. body: {step, option_id, verdict, tags, note} */
    feedback:   function (body)        { return post('/api/feedback', body); },

    draft:      function ()            { return get('/api/draft'); },

    /* 본문 작성. 프롬프트가 한 번 도므로 오래 걸린다. */
    write:      function ()            { return post('/api/draft/write'); },
    step:       function (key)         { return get('/api/draft/' + encodeURIComponent(key)); },
    confirm:    function (key, body)   { return post('/api/draft/' + encodeURIComponent(key), body); },
    result:     function ()            { return get('/api/draft/result'); },

    /* 근거 문서. 업로드는 multipart 라 call() 을 안 쓴다 — 브라우저가
     * Content-Type 에 boundary 를 직접 붙여야 하므로 헤더를 지정하면 깨진다. */
    docs:       function ()            { return get('/api/draft/upload'); },
    docDelete:  function (id)          { return call('DELETE', '/api/draft/upload/' + encodeURIComponent(id)); },
    docUpload:  function (fileObj) {
      var body = new FormData();
      body.append('file', fileObj);
      return fetch('/api/draft/upload', { method: 'POST', body: body, credentials: 'same-origin' })
        .then(function (res) { return res.json(); });
    },
    hero:       function ()            { return post('/api/draft/hero', {}); },
    illust:     function ()            { return post('/api/draft/illust', {}); }
  };
})();
