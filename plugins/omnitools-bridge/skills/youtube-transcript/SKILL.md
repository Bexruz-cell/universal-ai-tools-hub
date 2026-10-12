---
name: youtube-transcript
description: >-
  Extract full video subtitles and transcripts from YouTube video URLs, shorts, and video IDs
  across multiple languages (ru, en). Use this skill when the user asks to summarize, analyze,
  extract key points, or translate a YouTube video or podcast.
---

# YouTube Transcript Skill

The `youtube-transcript` skill provides instant extraction of complete transcripts and subtitles from YouTube videos, podcasts, lectures, and YouTube Shorts without requiring third-party API keys or download tools.

## Architecture & Interfaces

1. **MCP Tool**: `youtube_transcript(video, languages)` via stdio bridge.
2. **REST API**: `POST /tools/youtube` and `GET /api/v1/youtube/transcript?video={video}&languages={languages}`.
3. **Python SDK**: `from src.core.tools import youtube_transcript`.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `video` | string | **Yes** | — | YouTube URL (`youtube.com/watch?v=...`, `youtu.be/...`, `shorts/...`) or 11-char video ID. |
| `languages` | string | No | `"ru,en"` | Comma-separated list of priority language codes (e.g., `"ru,en"`, `"en,es"`, `"de"`). |

## Usage Examples

### 1. Antigravity / Claude / Codex MCP Tool Call
```json
{
  "name": "youtube_transcript",
  "arguments": {
    "video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "languages": "en,ru"
  }
}
```

### 2. HTTP / REST API (ChatGPT Custom Action)
```http
POST /tools/youtube HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "video": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "languages": "en,ru"
}
```
