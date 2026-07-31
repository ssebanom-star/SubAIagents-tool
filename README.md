# SubAIagents-tool

Windows의 **Claude Code**에서 (별도 프로그램 터미널 없이) **ADB로 연결된 안드로이드 기기를 제어**하고,
**ChatGPT를 서브에이전트로 활용**해 부가 코딩을 위임함으로써 **Claude 토큰 부담을 줄이는** MCP 서버입니다.

> 자세한 설계 배경은 [`docs/PLAN.md`](docs/PLAN.md) 참고.

## 핵심 아이디어

- Claude Code는 **MCP 서버**의 도구를 직접 툴콜로 호출합니다 → 터미널을 따로 열 필요가 없습니다.
- 이 서버는 세 종류의 도구를 노출합니다.
  - **`adb_*`** : 연결된 기기 제어(shell, 설치, 파일전송, 로그, 스크린샷, UI 입력 등)
  - **`adb_logcat_*`** : **실시간 로그 모니터링** — 백그라운드 세션으로 로그를 계속 수집하고, 새 로그만 읽기/패턴 감시/**GPT에게 분석·판단 위임**
  - **`chatgpt_*`** : 부가/보일러플레이트 코딩·리서치·로그분석을 ChatGPT에 위임 → Claude는 "무엇을 맡길지"만 판단하고 긴 출력은 ChatGPT가 생성 → **토큰 절약**

### 서브에이전트 백엔드 (비용)

| 백엔드 | 인증 | 비용 |
|--------|------|------|
| **Codex CLI** (권장, 기본) | `codex login` → **ChatGPT 구독 로그인** | **API 과금 없음** (구독 요금제 사용) |
| OpenAI API | `OPENAI_API_KEY` | 토큰당 과금 |

`codex` 명령이 있으면 자동으로 Codex CLI를 씁니다(=이미 구독 중인 앱 활용, 추가 비용 없음).
`SUBAI_GPT_BACKEND` 로 강제 지정 가능(`auto`/`codex`/`api`).

## 요구 사항

- Python 3.10 이상
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (`adb.exe`)
- (선택) ChatGPT 서브에이전트를 쓰려면 둘 중 하나:
  - **Codex CLI** (`npm install -g @openai/codex` 후 `codex login`) — **구독으로 동작, API 비용 없음** ← 권장
  - 또는 OpenAI API 키 (`OPENAI_API_KEY`) — 토큰당 과금

## 설치

```bash
git clone https://github.com/ssebanom-star/subaiagents-tool.git
cd subaiagents-tool
pip install -r requirements.txt
# 또는 편집 가능 설치:  pip install -e .
```

## Claude Code에 등록 (Windows)

### 방법 A — 자동 셋업 (권장, 경로 직접 안 만짐)

아래 한 줄이 **python·adb·codex·프로젝트 경로를 전부 자동으로 찾아** 동작하는 `.mcp.json`을 생성합니다.

```powershell
python scripts/setup.py
```

- **Claude 데스크톱 앱**을 쓰면 `--claude-desktop` 추가 → 앱 설정에 자동 등록:
  `python scripts/setup.py --claude-desktop` (등록 후 앱을 **트레이에서 완전히 종료 후 재실행**)
- `codex` 명령이 있으면 자동으로 **구독 기반(무과금)** 백엔드로 설정됩니다 (먼저 `codex login` 한 번)
- API를 쓰려면: `python scripts/setup.py --openai-key sk-...`
- adb를 자동으로 못 찾으면 `--adb-path C:\platform-tools\adb.exe` 로 지정
- 환경변수까지 영구 저장하려면 `--persist` 추가 (Windows `setx`)
- 파일 안 쓰고 확인만: `--print-only`

> **Claude Code(CLI)** 와 **Claude 데스크톱 앱** 둘 다 MCP 클라이언트라 이 서버를 그대로 씁니다.
> CLI는 `.mcp.json`(프로젝트 폴더) 또는 `claude mcp add`, 앱은 `--claude-desktop` 로 등록하세요.

생성된 `.mcp.json`에는 절대경로가 채워지고 `PYTHONPATH`까지 지정되어 **PATH 설정 없이도** 동작합니다.
실행 후 Claude Code를 재시작하고 `/mcp`로 확인하세요.

### 방법 B — CLI 직접

```powershell
claude mcp add subaiagents -- python -m subaiagents.server
```

### 방법 C — 설정 파일 직접 편집

프로젝트 루트에 `.mcp.json`을 만들고 아래를 넣습니다. (키/경로는 본인 환경에 맞게)

```json
{
  "mcpServers": {
    "subaiagents": {
      "command": "python",
      "args": ["-m", "subaiagents.server"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "OPENAI_MODEL": "gpt-4o-mini",
        "ADB_PATH": "C:\\platform-tools\\adb.exe"
      }
    }
  }
}
```

> `pip install -e .` 로 설치하지 않았다면, `args`를 `["-m", "subaiagents.server"]` 대신
> `["경로/src/subaiagents/server.py"]`로 지정하거나 `PYTHONPATH`에 `src`를 추가하세요.

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SUBAI_GPT_BACKEND` | 서브에이전트 백엔드 `auto`/`codex`/`api` | `auto` (codex 있으면 codex) |
| `SUBAI_CODEX_CMD` | Codex CLI 실행 파일 | `codex` |
| `SUBAI_CODEX_ARGS` | Codex 호출 인자(프롬프트 앞) | `exec` |
| `OPENAI_API_KEY` | (API 백엔드용) ChatGPT 키 | (없어도 codex로 동작 가능) |
| `OPENAI_MODEL` | 위임 모델 | `gpt-4o-mini` |
| `OPENAI_BASE_URL` | 커스텀/Azure 엔드포인트 | (선택) |
| `OPENAI_MAX_TOKENS` | 위임 출력 상한 | `2048` |
| `ADB_PATH` | `adb.exe` 경로(미지정 시 자동 탐색) | 자동 |
| `ADB_DEFAULT_SERIAL` | 기본 기기 시리얼 | (없음) |
| `SUBAI_TIMEOUT` | adb 호출 타임아웃(초) | `60` |
| `SUBAI_SCREENSHOT_DIR` | 스크린샷 저장 폴더 | `./adb_screenshots` |

`.env.example`을 참고하세요.

## 제공 도구

### ADB
`adb_devices`, `adb_shell`, `adb_install`, `adb_uninstall`, `adb_push`, `adb_pull`,
`adb_logcat`, `adb_packages`, `adb_current_app`, `adb_screenshot`,
`adb_tap`, `adb_swipe`, `adb_input_text`, `adb_keyevent`, `adb_reboot`,
`adb_connect`, `adb_disconnect`

모든 도구는 선택적 `serial` 인자로 기기를 지정할 수 있습니다(미지정 시 기본 기기).

### ADB 자동화 / 반복 실행
- `adb_wait_for_device(timeout=60, wait_for_boot=False)` — 기기 연결(및 부팅완료)까지 대기 (재부팅 후 자동화에 필수)
- `adb_start_app(package, activity="")` — 앱 실행(LAUNCHER 인텐트 또는 특정 액티비티)
- `adb_stop_app(package)` — 앱 강제 종료
- `adb_clear_app(package)` — 앱 데이터 초기화(반복 테스트마다 초기 상태)
- `adb_getprop(prop="")` — 시스템 속성 조회
- `adb_repeat_shell(command, times=3, interval_sec=1.0, stop_on_error=False)` — shell 명령 반복 실행 + 결과 수집(폴링/플레이키 확인)
- `adb_screenrecord(seconds=10, filename="")` — 화면 녹화 후 호스트로 저장

### 백그라운드 명령 (오래 걸리는 작업 짬처리)
MCP 도구는 요청/응답이라 오래 걸리는 명령은 도구 호출을 막습니다. 백그라운드로 던져두고 나중에 확인합니다.

- `bg_run(command, use_shell=False, cwd="")` — 임의 명령을 백그라운드로 시작 → `job_id`
- `bg_output(job_id, max_lines=500)` — 직전 이후 새 출력만
- `bg_wait(job_id, timeout=30)` — 완료까지 대기(상한 `SUBAI_BG_WAIT_MAX_TIMEOUT`)
- `bg_list()` / `bg_stop(job_id)` — 목록 / 중지

### 실시간 로그 모니터링
백그라운드에서 `adb logcat`을 계속 돌리며 로그를 버퍼에 수집합니다. MCP는 스트리밍 푸시가 안 되므로
"세션 시작 → 폴링/감시/분석" 방식으로 실시간 로그를 다룹니다.

- `adb_logcat_start(filter_spec="", serial=None, clear_first=True)` — 백그라운드 로그 세션 시작 → `session_id` 반환
- `adb_logcat_read(session_id, max_lines=500)` — **직전 읽은 이후의 새 로그만** 반환(커서 자동 전진)
- `adb_logcat_tail(session_id, lines=100)` — 커서 이동 없이 최근 N줄 엿보기
- `adb_logcat_watch(session_id, pattern, timeout=30)` — 정규식 패턴이 뜰 때까지 대기(예: 크래시 감시)
- `adb_logcat_analyze(session_id, question="", lines=300, model="")` — **최근 로그를 GPT가 읽고 판단**(심각도·요약·원인·다음 조치)
- `adb_logcat_stop(session_id)` / `adb_logcat_list()` — 세션 종료 / 목록

버퍼 크기는 `SUBAI_LOG_BUFFER_LINES`(기본 5000), 감시 최대 대기시간은 `SUBAI_LOG_WATCH_MAX_TIMEOUT`(기본 300초)로 조정합니다.

### ChatGPT 서브에이전트
- `chatgpt_code(task, context="", language="", model="")` — 부가 코딩 위임(코드만 반환)
- `chatgpt_ask(prompt, model="")` — 일반 질의/리서치 위임
- `chatgpt_review(code_snippet, focus="", model="")` — 코드 리뷰 위임
- `chatgpt_analyze_logs(logs, question="", model="")` — 임의의 로그 텍스트를 GPT가 읽고 판단(세션 무관)
- `chatgpt_set_model(model)` / `chatgpt_get_model()` — **응답 모델 지정**/조회

모든 `chatgpt_*` 도구는 **`timeout`(초) 인자**를 받습니다. AI가 작업 크기에 맞춰 직접 지정하며,
`0`이면 기본값(`SUBAI_CODEX_TIMEOUT`, 기본 300초)을 쓰고 상한은 `SUBAI_CODEX_MAX_TIMEOUT`(기본 1800초)입니다.
무거운 작업이면 `timeout=900`처럼 크게 주면 됩니다.

#### 응답 모델 지정
Codex 백엔드 기본 모델은 **`gpt-5.6-luna`**(빠르고 저렴한 GPT-5.6 등급)로 고정돼 있습니다.
모델 우선순위: **호출별 `model=` 인자 > `chatgpt_set_model` 런타임 설정 > `SUBAI_CODEX_MODEL` 환경변수 > 기본값(gpt-5.6-luna)**.

- 세션 중 바꾸기(재시작 불필요): Claude에게 *"모델을 gpt-5-codex로 바꿔줘"* → `chatgpt_set_model("gpt-5-codex")`
- 한 번만 다른 모델로: 각 도구의 `model=` 인자 사용
- 항상 특정 모델로: 환경변수 `SUBAI_CODEX_MODEL`(codex 백엔드) 또는 `OPENAI_MODEL`(api 백엔드)
- Codex는 `-m <model>`로, API는 OpenAI 모델 id로 전달됩니다.

## 사용 예 (Claude Code에서 자연어로)

- "연결된 기기 목록 보여줘" → `adb_devices`
- "com.example.app 로그 최근 100줄 봐줘" → `adb_logcat`
- "지금 화면 스크린샷 찍어줘" → `adb_screenshot`
- "이 반복적인 파서 함수는 ChatGPT한테 파이썬으로 짜달라고 해" → `chatgpt_code`
- "지금부터 로그 실시간으로 감시하다가 크래시 뜨면 알려줘" → `adb_logcat_start` + `adb_logcat_watch`
- "방금 쌓인 로그 GPT한테 왜 앱이 죽었는지 분석시켜줘" → `adb_logcat_analyze`

#### 실시간 모니터링 흐름 예시
1. `adb_logcat_start(filter_spec="*:E")` → `session_id` 획득
2. 앱에서 문제 재현
3. `adb_logcat_watch(session_id, pattern="FATAL EXCEPTION", timeout=60)` — 크래시 대기
4. `adb_logcat_analyze(session_id, question="크래시 원인과 해결책은?")` — **GPT가 로그를 읽고 판단** (Claude 토큰 절약)
5. `adb_logcat_stop(session_id)`

## 진단

셋업이 잘 되었는지 점검:

```bash
python scripts/doctor.py
```

adb 탐색 결과, 연결된 기기, OpenAI 키/패키지 상태를 한눈에 보여줍니다.

## 테스트

```bash
pip install pytest
python -m pytest tests/ -q
```

기기 없이도 실행되는 단위 테스트(명령 조립·파싱 로직 검증)를 제공합니다.

## 라이선스

MIT
