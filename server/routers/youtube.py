from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import re
from youtube_transcript_api import YouTubeTranscriptApi

router = APIRouter(prefix="/youtube", tags=["YouTube Tools"])

class TranscriptSegment(BaseModel):
    text: str
    start: float
    duration: float

class YouTubeTranscriptResponse(BaseModel):
    video_id: str
    total_segments: int
    full_text: str
    segments: List[TranscriptSegment]

def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'shorts\/([0-9A-Za-z_-]{11})'
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    return url_or_id

@router.get("/transcript", response_model=YouTubeTranscriptResponse, summary="Extract transcript from any YouTube video")
def get_transcript(
    video: str = Query(..., description="YouTube video URL or 11-character video ID"),
    languages: Optional[str] = Query("ru,en", description="Comma-separated language priority (e.g. 'ru,en')")
):
    """
    Extracts complete text transcript and subtitles from a YouTube video
    for summarization, analysis, or question-answering in ChatGPT.
    """
    video_id = extract_video_id(video)
    lang_list = [l.strip() for l in languages.split(",") if l.strip()]

    try:
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_list)
    except Exception as e:
        # Fallback to any available transcript
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript(['ru', 'en']) or transcript_list.find_generated_transcript(['ru', 'en'])
            transcript_data = transcript.fetch()
        except Exception as inner_e:
            raise HTTPException(status_code=404, detail=f"No subtitles/transcript found for video {video_id}: {str(inner_e)}")

    full_text = " ".join([item["text"] for item in transcript_data])
    segments = [
        TranscriptSegment(text=item["text"], start=item["start"], duration=item["duration"])
        for item in transcript_data
    ]

    return YouTubeTranscriptResponse(
        video_id=video_id,
        total_segments=len(segments),
        full_text=full_text,
        segments=segments[:100]  # Return first 100 segments to keep payload clean
    )
