# BharatAI Platform — Technical Design Document (MVP)

> One shared AI backend. Six Indian-language apps.
> Version 2.0 — MVP-scoped for solo laptop development (RTX 4060, 8GB VRAM)

---

## 1. Purpose

Shared backend powering multiple Indian-language AI apps from one codebase on a local RTX 4060. Each app is a plugin — write ~200 lines of domain code, get voice, LLM, language detection, auth for free.

---

## 2. BasePlugin Contract

Every plugin MUST implement this. Platform refuses to load non-conforming plugins.

```python
# core/api/plugin_registry.py

from abc import ABC, abstractmethod
from fastapi import APIRouter

class BasePlugin(ABC):
    @property
    @abstractmethod
    def app_id(self) -> str:
        """Unique slug: 'asha_health', 'lawyer_ai', etc."""

    @abstractmethod
    def system_prompt(self, language: str, context: dict) -> str:
        """Return domain-specific system prompt.
        language: ISO 639-1 code ('hi', 'mr', 'ta', etc.)
        context: session data, user profile, app state
        """

    @abstractmethod
    def parse_response(self, llm_output: str, context: dict) -> dict:
        """Parse LLM output into structured domain object.
        Return dict is stored and returned to client.
        """

    @abstractmethod
    def router(self) -> APIRouter:
        """Return FastAPI router with app-specific routes.
        Core routes (health, voice, chat) added automatically.
        """

    def on_startup(self) -> None:
        """Optional: called once on platform start."""
        pass

    def on_session_start(self, session: dict) -> dict:
        """Optional: initialise app-specific session state."""
        return session
```

---

## 3. Voice Pipeline (with error handling)

Primary entry point for all user input. Stateless per-request.

```python
# core/voice/pipeline.py

class VoicePipeline:
    MIN_STT_CONFIDENCE = 0.5
    LLM_RETRY_LIMIT = 1

    async def process(self,
        audio: bytes,
        app_id: str,
        session_id: str,
        language_hint: str | None = None
    ) -> VoiceResponse:

        # Step 1 — Transcribe
        transcript = await self.stt.transcribe(audio, language_hint)

        # Step 1b — Reject low confidence
        if transcript.confidence < self.MIN_STT_CONFIDENCE:
            return VoiceResponse(
                error='low_confidence',
                response_text='Sorry, I could not understand. Please speak again.',
                response_audio=await self._safe_tts(
                    'Sorry, please speak again.', language_hint or 'hi'
                ),
            )

        # Step 2 — Detect language
        language = language_hint or await self.detector.detect(transcript.text)

        # Step 3 — Load plugin, build prompt
        plugin = self.registry.get(app_id)
        if not plugin:
            raise HTTPException(404, f'Unknown app: {app_id}')
        session = await self.session_store.get(session_id)
        prompt = plugin.system_prompt(language, session)

        # Step 4 — LLM inference with retry
        parsed = None
        for attempt in range(self.LLM_RETRY_LIMIT + 1):
            try:
                llm_response = await self.llm.chat(
                    system=prompt,
                    user=transcript.text,
                    model=self.model_manager.active_model
                )
                parsed = plugin.parse_response(llm_response.text, session)
                break
            except (json.JSONDecodeError, KeyError):
                if attempt == self.LLM_RETRY_LIMIT:
                    return VoiceResponse(
                        error='parse_failed',
                        transcript=transcript.text,
                        response_text='I understood you but could not process. Please try again.',
                    )

        # Step 5 — TTS with fallback
        audio_out = await self._safe_tts(parsed['response_text'], language)

        return VoiceResponse(
            transcript=transcript.text,
            language=language,
            response_text=parsed['response_text'],
            response_audio=audio_out,
            domain_data=parsed,
        )

    async def _safe_tts(self, text: str, language: str) -> bytes | None:
        try:
            return await self.tts.synthesize(text=text, language=language)
        except Exception:
            return None
```

---

## 4. Model Manager (VRAM Budget)

### VRAM Allocation Table (MVP)

| Model | Purpose | VRAM | Runtime | Loaded When |
|-------|---------|------|---------|-------------|
| IndicWhisper medium | STT | ~1,500 MB | faster-whisper | During STT, unloaded after |
| llama3.2:3b-instruct-q4_0 | LLM | ~2,400 MB | Ollama | Kept warm |
| gTTS | TTS | 0 (CPU) | gTTS lib | Always |
| CUDA overhead | System | ~800-1,000 MB | — | Always |

```python
# core/llm/model_manager.py

VRAM_BUDGET_MB = 7000

MODEL_PROFILES = {
    'llama3.2:3b': {
        'vram_mb': 2400,
        'ollama_tag': 'llama3.2:3b-instruct-q4_0',
        'use': 'default_mvp',
    },
    'llama3.2:8b': {
        'vram_mb': 5200,
        'ollama_tag': 'llama3.2:8b-instruct-q4_0',
        'use': 'post_mvp_cloud',
    },
}

# Keep LLM warm in Ollama. Load/unload Whisper per request (~2s load time).
DEFAULT_MODEL = 'llama3.2:3b'
```

---

## 5. Session Store

Redis-backed, 30-minute TTL.

```python
# Session schema (JSON in Redis)
{
    'session_id': 'uuid',
    'app_id': 'asha_health',
    'worker_id': 'uuid',
    'language': 'hi',
    'conversation_history': [   # max 5 turns
        {'role': 'user', 'text': '...'},
        {'role': 'assistant', 'text': '...'},
    ],
    'app_state': {},
    'created_at': 'ISO timestamp',
    'last_active': 'ISO timestamp',
}
```

---

## 6. API Endpoints (Core — auto-registered for every app)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{app_id}/voice` | POST | Upload audio → text + audio response |
| `/{app_id}/chat` | POST | Text-only input → text response |
| `/{app_id}/session/{id}` | GET | Fetch session state |
| `/{app_id}/session/{id}` | DELETE | Clear session |
| `/health` | GET | Platform health + model status |
| `/models` | GET | Loaded models + VRAM usage |
| `/admin/load-model` | POST | Load model into VRAM (admin) |

### Voice Request

```
POST /asha_health/voice
Content-Type: multipart/form-data
X-API-Key: <key>

Fields:
  audio:          WAV or OGG, max 10MB, max 60 seconds
  session_id:     UUID
  language_hint:  optional ISO code ('hi', 'mr', 'ta')
```

### Voice Response

```json
{
  "session_id": "uuid",
  "transcript": "राम 45 साल बुखार है",
  "language": "hi",
  "response_text": "मैंने राम का दौरा दर्ज किया...",
  "response_audio_url": "/audio/abc123.ogg",
  "domain_data": {
    "patient_name": "राम",
    "patient_age": 45,
    "complaint": "बुखार",
    "temperature": null,
    "referral_needed": false,
    "visit_id": "uuid",
    "sync_status": "pending"
  },
  "confidence": 0.91,
  "processing_ms": 1840,
  "error": null
}
```

---

## 7. ASHA Health Plugin

### System Prompt

```python
# apps/asha_health/prompts.py

SYSTEM_PROMPT = """
You are a health data assistant for ASHA workers in rural India.
The worker will describe a patient visit in Hindi or their local language.

Extract these fields:
- patient_name (string)
- patient_age (integer)
- gender (male/female/other)
- complaint (string)
- temperature (float, Celsius — only if mentioned)
- weight (float, kg — only if mentioned)
- visit_date (date — today if not mentioned)
- referral_needed (boolean — true if 'refer' or 'hospital')
- notes (string — anything else relevant)

RULES:
- Respond ONLY in JSON. No explanation.
- Use null for fields not mentioned.
- confirmation_message: 1 sentence in {language} summarising what you recorded.

OUTPUT FORMAT:
{{
  "patient_name": "...",
  "patient_age": ...,
  "gender": "...",
  "complaint": "...",
  "temperature": null,
  "weight": null,
  "visit_date": "YYYY-MM-DD",
  "referral_needed": false,
  "notes": null,
  "confirmation_message": "..."
}}
"""
```

### Database Schema

```sql
CREATE SCHEMA asha_health;

CREATE TABLE asha_health.workers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(15) UNIQUE NOT NULL,
    name VARCHAR(100),
    district VARCHAR(100),
    language VARCHAR(10) DEFAULT 'hi',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE asha_health.visits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID REFERENCES asha_health.workers(id),
    patient_name VARCHAR(100),
    patient_age INTEGER,
    gender VARCHAR(10),
    complaint TEXT,
    temperature DECIMAL(4,1),
    weight DECIMAL(5,2),
    visit_date DATE DEFAULT CURRENT_DATE,
    referral_needed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    raw_transcript TEXT,
    sync_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON asha_health.visits (worker_id, visit_date);
CREATE INDEX ON asha_health.visits (sync_status);
```

---

## 8. Test Cases

### 8.1 STT Service

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| STT-001 | Hindi transcription | WAV: 'मरीज़ का नाम राम है' | text matches, lang='hi', confidence > 0.85 |
| STT-002 | Bhojpuri audio | WAV: Bhojpuri speech | Transcribed (likely as Hindi), no crash |
| STT-003 | Empty audio | Silent WAV 0.5s | Empty transcript, no exception |
| STT-004 | Noisy background | WAV with 40dB noise | Transcription attempted, confidence < 0.5 |
| STT-005 | Unsupported language | WAV: French | Transcribed, lang detected |

### 8.2 LLM Inference

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| LLM-001 | Hindi JSON extraction | ASHA prompt + 'राम 45 साल, बुखार है' | Valid JSON, name=राम, age=45 |
| LLM-002 | JSON format enforced | Valid ASHA input | Parseable JSON, no markdown |
| LLM-003 | Missing fields = null | Only name + complaint | Unmentioned fields are null |
| LLM-004 | Referral detection | 'hospital bhejo, serious hai' | referral_needed: true |
| LLM-005 | Timeout handling | Ollama timeout >30s | 503 with retry-after |
| LLM-006 | Model not loaded | Request before warm-up | 503, triggers async load |
| LLM-007 | Invalid JSON retry | LLM returns markdown JSON | Retry once, parse succeeds |

### 8.3 Language Detection

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| LANG-001 | Hindi | Devanagari text | 'hi', confidence > 0.9 |
| LANG-002 | Marathi vs Hindi | 'माझे नाव...' | 'mr', not 'hi' |
| LANG-003 | Hinglish | 'patient ka fever hai' | 'hi', mixed_script: true |
| LANG-004 | Tamil | Tamil script | 'ta' |
| LANG-005 | Single word | 'हाँ' | Returns result, no exception |

### 8.4 Voice Pipeline (Integration)

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| VP-001 | Full pipeline Hindi | WAV: Hindi patient desc | JSON + audio in Hindi |
| VP-002 | Full pipeline Marathi | WAV: Marathi speech | JSON + audio in Marathi |
| VP-003 | Session continuity | Two requests, same session | Second has first's context |
| VP-004 | Invalid app_id | app_id: 'nonexistent' | 404 |
| VP-005 | Oversized audio | WAV > 10MB | 413 |
| VP-006 | Low confidence STT | Heavy noise WAV | 'please repeat', no LLM call |
| VP-007 | Bad LLM JSON | Valid audio, LLM fails | Retry once, then error |
| VP-008 | TTS failure | Valid pipeline, TTS throws | Text response, audio=null |

### 8.5 ASHA Health Plugin

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| ASHA-001 | Basic visit | 'राम, 45 साल, बुखार है' | name=राम, age=45, complaint=बुखार |
| ASHA-002 | Age with suffix | 'रमा देवी, पचास साल की, खांसी' | name=रमा देवी, age=50 |
| ASHA-003 | Referral trigger | 'bahut serious, hospital bhejo' | referral_needed=true |
| ASHA-004 | Temperature F→C | 'bukhaar hai, 103 degree' | temperature=39.4 |
| ASHA-005 | Response language | Hindi input | confirmation in Hindi |
| ASHA-006 | Save to DB | Valid visit | Row in visits, sync='pending' |
| ASHA-007 | Offline queue | NHM unavailable | Saved locally, no error |
| ASHA-008 | Duplicate prevention | Same worker+patient+day | Warns, asks confirm |

### 8.6 Auth & Tenancy

| ID | Description | Input | Expected |
|----|-------------|-------|----------|
| AUTH-001 | Valid key | Correct X-API-Key | Proceeds |
| AUTH-002 | Missing key | No auth header | 401 |
| AUTH-003 | Cross-app access | lawyer_ai requesting asha data | 403 |
| AUTH-004 | Rate limit | 120 req/60s | 121st returns 429 |
| AUTH-005 | Expired JWT | Expired token | 401 + refresh hint |

---

## 9. Development Phases

### Phase 1 — Environment (Day 1)
- Install Ollama, pull `llama3.2:3b-instruct-q4_0`
- Install faster-whisper, download IndicWhisper medium via HuggingFace
- FastAPI project with /health endpoint
- PostgreSQL + Redis via Docker Compose
- Pass: STT-001, STT-002, LLM-001
- Verify VRAM with nvidia-smi

### Phase 2 — Core Services (Days 2-4)
- stt.py (faster-whisper wrapper)
- client.py (Ollama HTTP client)
- detector.py (language detection)
- prompt_builder.py
- BasePlugin + plugin_registry.py
- Pass: STT-001→005, LLM-001→007, LANG-001→005

### Phase 3 — Voice Pipeline (Days 5-6)
- VoicePipeline with error handling
- TTS via gTTS
- Session store (Redis)
- API gateway + static API key auth
- Pass: VP-001→008, AUTH-001→005

### Phase 4 — ASHA Plugin (Days 7-10)
- ASHA system prompt
- Response parser with JSON validation
- DB schema + SQLAlchemy models
- NHM offline queue
- ASHA routes
- Pass: ASHA-001→008

### Phase 5 — WhatsApp (Days 11-13)
- Twilio sandbox webhook
- Voice message → /voice bridge
- Text fallback
- E2E test with real WhatsApp voice message

### Phase 6 — Second Plugin (Days 14-17)
- Lawyer AI plugin (same BasePlugin)
- Verify zero core/ changes needed
- Architecture validation complete
