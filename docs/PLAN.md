# SubAIagents-tool — 개발 계획

## 1. 목표

Windows 환경의 **Claude Code**(별도 프로그램 터미널이 아닌, Claude Code가 직접 호출하는 방식)에서:

1. **ADB(Android Debug Bridge)를 잘 활용**하여 연결된 안드로이드 기기를 제어한다.
2. **ChatGPT(OpenAI API)를 서브에이전트**로 활용하여, 부가/보일러플레이트성 코딩을 위임함으로써 **Claude 토큰 부담을 줄인다.**

## 2. 아키텍처 선택

Claude Code는 **MCP(Model Context Protocol) 서버**를 통해 외부 도구를 직접 호출할 수 있다.
따라서 "프로그램 터미널을 따로 열지 않고" Claude Code 안에서 ADB와 ChatGPT를 쓰려면
**MCP 서버 1개**로 두 기능(ADB 도구 + ChatGPT 서브에이전트 도구)을 노출하는 것이 가장 적합하다.

```
┌──────────────────────┐        stdio (MCP)        ┌───────────────────────────┐
│   Claude Code (CLI)  │  <──────────────────────> │  subaiagents MCP server   │
│   Windows            │                            │  (Python)                 │
└──────────────────────┘                            │                           │
                                                    │  ├─ adb.*  도구 그룹       │
                                                    │  │    └─ adb.exe subprocess│──> 연결된 안드로이드 기기
                                                    │  │                         │
                                                    │  └─ chatgpt.* 도구 그룹    │
                                                    │       └─ OpenAI API        │──> ChatGPT (부가 코딩)
                                                    └───────────────────────────┘
```

### 왜 MCP 서버인가
- Claude Code가 **툴콜로 직접** ADB를 호출 → 사용자가 터미널을 따로 열 필요 없음.
- 결과가 **구조화**되어 반환 → Claude가 다음 행동을 정확히 결정.
- ChatGPT 위임을 **툴 하나**로 만들면, Claude는 "이 부분은 ChatGPT에게 맡겨"라고 판단만 하고
  실제 대량 코드 생성/설명은 ChatGPT가 처리 → **Claude 컨텍스트/토큰 절약.**

## 3. 구성 요소

### 3.1 ADB 도구 그룹 (`src/subaiagents/adb.py`)
`adb.exe`를 subprocess로 감싸는 안전한 래퍼.

| 도구 | 설명 |
|------|------|
| `adb_devices` | 연결된 기기 목록 + 상태 |
| `adb_shell` | 기기에서 shell 명령 실행 |
| `adb_install` / `adb_uninstall` | APK 설치/삭제 |
| `adb_push` / `adb_pull` | 파일 전송 |
| `adb_logcat` | 로그 조회(필터/라인 수 제한) |
| `adb_screenshot` | 스크린샷 캡처(로컬 저장) |
| `adb_input` | tap/swipe/text/keyevent UI 입력 |
| `adb_packages` | 설치된 패키지 목록 |
| `adb_current_app` | 현재 포그라운드 앱/액티비티 |
| `adb_reboot` | 기기 재부팅 |
| `adb_connect` / `adb_disconnect` | 네트워크(무선) 기기 연결 |

특징:
- **기기 선택**: `serial` 인자로 특정 기기 지정, 미지정 시 기본 기기.
- **Windows 대응**: `ADB_PATH` 환경변수 → PATH → 일반 설치 경로 순으로 `adb.exe` 자동 탐색.
- **타임아웃/에러 처리**: 모든 호출에 타임아웃, stdout/stderr/returncode 구조화 반환.

### 3.2 실시간 로그 모니터링 도구 그룹 (`src/subaiagents/logmon.py`)
MCP는 요청/응답이라 서버가 클라이언트로 로그를 계속 푸시할 수 없다.
따라서 **백그라운드 logcat 세션**으로 실시간 모니터링을 구현한다.

- 세션 시작 시 `adb logcat`을 백그라운드 프로세스로 띄우고, 별도 스레드가 stdout을
  **링 버퍼**(기본 5000줄)에 계속 적재.
- Claude는 다음 도구로 실시간 로그를 다룬다:

| 도구 | 설명 |
|------|------|
| `adb_logcat_start` | 백그라운드 로그 세션 시작 → `session_id` |
| `adb_logcat_read` | 직전 읽은 이후의 **새 로그만** 반환(커서 전진) |
| `adb_logcat_tail` | 커서 이동 없이 최근 N줄 엿보기 |
| `adb_logcat_watch` | 정규식 패턴이 뜰 때까지 대기(크래시 감시 등, 타임아웃 상한) |
| `adb_logcat_analyze` | **최근 로그를 GPT가 읽고 판단** (심각도/요약/원인/다음조치) |
| `adb_logcat_stop` / `adb_logcat_list` | 세션 종료 / 목록 |

**GPT 로그 판단 연계**: `adb_logcat_analyze`는 세션 버퍼의 최근 로그를
ChatGPT 서브에이전트(`chatgpt.analyze_logs`)에 넘겨 **읽고 판단**하게 한다.
Claude에는 원문 로그가 아니라 **압축된 결론만** 돌아와 토큰을 크게 절약한다.
세션과 무관한 임의 로그 텍스트는 `chatgpt_analyze_logs`로 직접 분석 가능.

### 3.3 ChatGPT 서브에이전트 도구 그룹 (`src/subaiagents/chatgpt.py`)
OpenAI API를 감싼 위임 도구.

| 도구 | 설명 |
|------|------|
| `chatgpt_code` | 부가/보일러플레이트 코딩 작업을 ChatGPT에 위임하고 코드만 반환 |
| `chatgpt_ask` | 일반 질의(설명/리서치)를 ChatGPT에 위임 |
| `chatgpt_review` | 코드 스니펫 리뷰/개선 위임 |
| `chatgpt_analyze_logs` | 임의 로그 텍스트를 GPT가 읽고 판단 |

특징:
- 기본 모델은 **비용 효율 모델**(`gpt-4o-mini`, 환경변수로 변경 가능).
- **토큰 절약 원리**: Claude는 "무엇을 맡길지"만 판단, 실제 긴 출력은 ChatGPT가 생성 →
  Claude 컨텍스트에 최소한의 결과만 유입.
- `OPENAI_API_KEY` 미설정 시 명확한 안내 메시지 반환(서버는 죽지 않음).

### 3.4 설정 (`src/subaiagents/config.py`)
환경변수 중앙 관리: `ADB_PATH`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`,
`ADB_DEFAULT_SERIAL`, `SUBAI_TIMEOUT`, `SUBAI_SCREENSHOT_DIR`,
`SUBAI_LOG_BUFFER_LINES`, `SUBAI_LOG_WATCH_MAX_TIMEOUT`.

### 3.5 MCP 서버 엔트리 (`src/subaiagents/server.py`)
`FastMCP`로 위 도구들을 등록하고 stdio로 실행.

### 3.6 진단 스크립트 (`scripts/doctor.py`)
adb 탐색, 기기 연결, OpenAI 키 설정 여부를 점검 → 셋업 문제를 빠르게 진단.

## 4. Claude Code 등록 방법 (Windows)

`.mcp.json` 또는 `claude mcp add` 로 등록:

```json
{
  "mcpServers": {
    "subaiagents": {
      "command": "python",
      "args": ["-m", "subaiagents.server"],
      "env": { "OPENAI_API_KEY": "sk-...", "ADB_PATH": "C:\\platform-tools\\adb.exe" }
    }
  }
}
```

## 5. 검증 계획
- 단위 테스트: adb 명령 조립 로직 / 탐색 로직(실제 기기 없이 검증) — `tests/`.
- `python -m subaiagents.server` 임포트/기동 스모크 테스트.
- `scripts/doctor.py`로 실사용 환경 점검.

## 6. 산출물
- 실행 가능한 MCP 서버(Python), 등록 예시, 진단 스크립트, 테스트, 한글 README.
