# 서버에 올리기

8004 포트로 띄우는 순서다. 우분투 기준.

## 알아 둘 것 먼저

**이 앱에는 로그인이 없다.** 사내에서 쓸 것을 전제로 만들었다.

- 주소만 알면 누구나 들어온다
- `.env` 의 API 키로 남이 GPT·Gemini·Tavily 를 쓴다. **결과물을 한 번 만들 때마다 실제로 돈이 나간다.** 근거 검색이 붙으면서 글 한 편의 호출 수가 늘었다 — 명제마다 검색하고 본문을 가져오고 대조한다
- 세션은 메모리라 서버를 다시 띄우면 작업 중이던 글이 사라진다

**공개 IP 에 그대로 두면 안 된다.** 아래 5번을 건너뛰지 않는다.

## 1. 올리고 풀기

```bash
scp blogstudio.zip ubuntu@서버주소:~/
ssh ubuntu@서버주소
unzip blogstudio.zip && cd blogstudio
```

## 2. 파이썬 환경

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 키 넣기

`.env` 는 이미 들어 있다. 키 **세 줄**을 채운다.

```bash
nano .env
```

```
OPENAI_API_KEY=여기에-키를-넣으세요      ← sk-... 로 바꾼다
GEMINI_API_KEY=여기에-키를-넣으세요      ← AIza... 로 바꾼다
TAVILY_API_KEY=여기에-키를-넣으세요      ← tvly-... 로 바꾼다
```

**`TAVILY_API_KEY` 를 안 넣으면 근거 검색이 통째로 꺼진다.** 앱은 그대로
돌지만 명제가 전부 "확인 필요" 로 남고, 본문에 인용할 원문이 사람이 올린
PDF 밖에 없다. 오류가 안 나므로 **안 넣었다는 것을 눈치채기 어렵다.**

넣었는지 확인하는 법은 아래 4번에 있다.

나머지는 그대로 두면 된다.

```
OPENAI_MODEL=gpt-5.6-luna
OPENAI_MODEL_STRONG=gpt-5.6-terra
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
BS_ENV=server
PORT=8004
```

```bash
chmod 600 .env      # 다른 사용자가 못 읽게
```

**자리표시를 그대로 두면 키가 없는 것으로 본다.** 없는 키를 들고 호출하다
401 을 받는 대신, 뜰 때 콘솔에 알린다.

## 4. 먼저 확인

```bash
python test.py
```

`실패 0` 이 나와야 한다. 통과 수는 버전마다 늘어나므로 **실패가 0 인지만**
본다. 여기서 실패하면 코드 문제이므로 서버 설정을 만지기 전에 그것부터 본다.

```bash
python run.py
```

포트와 실행 방식은 `.env` 에 있으므로 그대로 부르면 된다.

뜰 때 이렇게 나온다.

```
  코드      ff41dd4c
  프롬프트   8f9b5cd4
  주소      http://0.0.0.0:8004
  로그 폴더   feedback · choice · response
```

`[!] OPENAI_API_KEY 가 없습니다` 가 뜨면 `.env` 를 못 읽은 것이다.

### 키가 다 들어갔는지 한 번에 보기

```bash
curl -s localhost:8004/api/health
```

```json
{"ok": true, "llm": true, "imagen": true, "search": true, ...}
```

**셋 다 `true` 여야 한다.**

| | 거짓이면 |
|---|---|
| `llm` | 후보가 가짜 데이터로 나온다 |
| `imagen` | 대표 이미지를 못 만든다 |
| `search` | **근거 검색이 꺼진다.** 명제가 전부 미확인으로 남는다 |

## 5. 열 사람만 열기 — 건너뛰지 않는다

셋 중 하나는 한다.

**(가) 방화벽에서 사무실 IP 만** — 제일 확실하다

네이버 클라우드면 ACG 규칙에 8004 을 **사무실 공인 IP 에만** 연다.
`0.0.0.0/0` 으로 열지 않는다.

**(나) 아이디·비번**

```bash
sudo apt install -y nginx apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd 아이디
```

`/etc/nginx/sites-available/blogstudio` 에

```nginx
server {
    listen 80;
    server_name 서버주소;

    location / {
        auth_basic "blogstudio";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 본문 작성이 30~40초, 근거 단계는 검색·대조까지 하느라 몇 분 걸릴
        # 수 있다. 기본값 60초로는 끊긴다.
        proxy_read_timeout 600s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/blogstudio /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

이때 `run.py` 는 `HOST=127.0.0.1` 로 띄운다. 바깥에서 8004 에 바로 못 닿게.

**(다) VPN 안에만 둔다**

## 6. 상시로 띄우기

**켜고 끄는 명령은 `deploy/운영.md` 에 모아 뒀다.** 아래는 처음 한 번 하는 설정이다.

```bash
sudo cp deploy/blogstudio.service /etc/systemd/system/
sudo nano /etc/systemd/system/blogstudio.service
```

`User` · `WorkingDirectory` · `ExecStart` 세 줄의 경로를 실제에 맞춘다.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now blogstudio
systemctl status blogstudio
journalctl -u blogstudio -f
```

## 7. 새 버전을 올릴 때

```bash
sudo systemctl stop blogstudio
cd ~ && mv blogstudio blogstudio_old
unzip blogstudio.zip && cd blogstudio

cp ../blogstudio_old/.env .
cp -r ../blogstudio_old/{response,choice,feedback,images,uploads} . 2>/dev/null

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python test.py

sudo systemctl start blogstudio
```

**덮어쓰지 않고 새 폴더에 푼다.** 파이썬이 `__pycache__` 의 옛 바이트코드를
쓸 수 있고, 지워진 파일이 남아 있으면 어느 것이 도는지 알기 어렵다.

`/api/health` 의 `code` 가 `python test.py` 가 찍은 값과 같은지 확인한다.
다르면 옛 코드가 돌고 있는 것이다.

## 로그와 파일

로그가 셋으로 갈려 있다. 성격이 다르고 보는 사람이 다르다.

```
response/   AI 가 내놓은 것     하루 한 파일. 제일 크다
choice/     사람이 고른 것 · 올린 문서
feedback/   사람이 남긴 평가
images/     만들어진 대표 이미지
uploads/    사람이 올린 PDF     세션별 하위 폴더
```

전부 `.gitignore` 에 있고 **새 버전을 올릴 때 옮겨 와야 한다**(7번 참고).

`response/` 는 글 한 편에 30~60KB 쌓인다. 근거 검색이 붙으면서 대조 결과가
행마다 남기 때문이다. 오래 두면 가끔 지운다.

**`uploads/` 와 `images/` 는 아무도 안 치운다.** 세션이 끝나도 파일은 남는다.
지금 규모에서는 문제가 아니지만, 몇 달 뒤에는 한 번 봐야 한다. 어느 파일이
무엇이었는지는 로그로 안다.

```bash
curl -s 'localhost:8004/api/logs?kind=uploaded'
```

## 무엇이 잘 돌고 있는지 보기

```bash
# 근거 검색이 실제로 돌았나
curl -s 'localhost:8004/api/logs?step=search&limit=5'

# 원문 대조가 어떻게 나왔나 (supported → invalid_check 가 잦으면 프롬프트 문제)
curl -s 'localhost:8004/api/logs?step=check&limit=10'

# 어떤 문서를 넣었을 때 무엇이 나왔나
curl -s 'localhost:8004/api/logs?doc=6f4c74505c81'
```
