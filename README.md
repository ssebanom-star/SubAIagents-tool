# SubAIagents-tool

Windows의 **Claude Code**에서 (별도 프로그램 터미널 없이) **ADB로 연결된 안드로이드 기기를 제어**하고,
**ChatGPT를 서브에이전트로 활용**해 부가 코딩을 위임함으로써 **Claude 토큰 부담을 줄이는** MCP 서버입니다.

> 자세한 설계 배경은 [`docs/PLAN.md`](docs/PLAN.md) 참고.

## 핵심 아이디어

- Claude Code는 **MCP 서버**의 도구를 직접 툴콜로 호출합니다 → 터미널을 따로 열 필요가 없습니다.
- 이 서버는 두 종류의 도구를 노출합니다.
  - **`adb_*`** : 연결된 기기 제어(shell, 설치, 파일전송, 로그, 스크린샷, UI 입력 등)
  - **`chatgpt_*`** : 부가/보일러플레이트 코딩·리서치를 ChatGPT에 위임 → Claude는 "무엇을 맡길지"만 판단하고 긴 출력은 ChatGPT가 생성 → **토큰 절약**

## 요구 사항

- Python 3.10 이상
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (`adb.exe`)
- (선택) OpenAI API 키 — ChatGPT 서브에이전트 사용 시

## 설치

```bash
git clone https://github.com/ssebanom-star/subaiagents-tool.git
cd subaiagents-tool
pip install -r requirements.txt
# 또는 편집 가능 설치:  pip install -e .
```

## Claude Code에 등록 (Windows)

### 방법 A — CLI

```powershell
claude mcp add subaiagents -- python -m subaiagents.server
```

### 방법 B — 설정 파일 직접 편집

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
| `OPENAI_API_KEY` | ChatGPT 서브에이전트 키 | (없으면 chatgpt_* 도구가 안내 메시지 반환) |
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

### ChatGPT 서브에이전트
- `chatgpt_code(task, context="", language="", model="")` — 부가 코딩 위임(코드만 반환)
- `chatgpt_ask(prompt, model="")` — 일반 질의/리서치 위임
- `chatgpt_review(code_snippet, focus="", model="")` — 코드 리뷰 위임

## 사용 예 (Claude Code에서 자연어로)

- "연결된 기기 목록 보여줘" → `adb_devices`
- "com.example.app 로그 최근 100줄 봐줘" → `adb_logcat`
- "지금 화면 스크린샷 찍어줘" → `adb_screenshot`
- "이 반복적인 파서 함수는 ChatGPT한테 파이썬으로 짜달라고 해" → `chatgpt_code`

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
