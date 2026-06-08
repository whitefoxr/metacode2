"""대본 텍스트를 음성으로 변환한다.

여러 TTS 엔진을 순서대로 시도하고, 모두 실패하면 무음 트랙으로 대체한다
(자막은 추정 타이밍으로 계속 표시됨).
"""
import asyncio
import os
import wave
from dataclasses import dataclass

VOICES = {
    "한국어 - 여성 (선희)": "ko-KR-SunHiNeural",
    "한국어 - 남성 (인준)": "ko-KR-InJoonNeural",
    "영어 - 여성 (Aria)": "en-US-AriaNeural",
}

# 단어/글자 수 기반으로 줄 길이를 추정할 때 쓰는 평균 발화 속도 (글자/초)
_FALLBACK_CHARS_PER_SEC = 5.5


@dataclass
class Narration:
    audio_path: str | None
    duration: float
    line_durations: list[float]
    engine: str  # "edge-tts" | "gtts" | "silent"


def _estimate_line_durations(lines: list[str], total_duration: float | None = None) -> list[float]:
    weights = [max(len(line), 1) for line in lines]
    total_weight = sum(weights)
    if total_duration is not None and total_duration > 0:
        return [total_duration * w / total_weight for w in weights]
    return [w / _FALLBACK_CHARS_PER_SEC for w in weights]


def _try_edge_tts(lines: list[str], voice: str, out_path: str) -> Narration | None:
    try:
        import edge_tts
    except ImportError:
        return None

    full_text = " ".join(lines)

    async def _run():
        communicate = edge_tts.Communicate(full_text, voice)
        boundaries = []
        with open(out_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    boundaries.append(chunk)
        return boundaries

    try:
        boundaries = asyncio.run(_run())
    except Exception:
        if os.path.exists(out_path):
            os.remove(out_path)
        return None

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        return None

    duration = _audio_duration_seconds(out_path)
    line_durations = _split_boundaries_into_lines(boundaries, lines, duration)
    return Narration(audio_path=out_path, duration=duration, line_durations=line_durations, engine="edge-tts")


def _split_boundaries_into_lines(boundaries: list[dict], lines: list[str], total_duration: float) -> list[float]:
    """단어 경계 타임스탬프를 각 자막 줄의 길이에 비례 배분해 줄별 구간을 추정한다."""
    if not boundaries or total_duration <= 0:
        return _estimate_line_durations(lines, total_duration)

    word_ends_100ns = [b["offset"] + b["duration"] for b in boundaries]
    word_ends_sec = [t / 10_000_000 for t in word_ends_100ns]

    word_counts = [max(len(line.split()), 1) for line in lines]
    total_words = sum(word_counts)
    if total_words != len(word_ends_sec):
        # 단어 수가 어긋나면 비율 기반으로 균등 배분
        return _estimate_line_durations(lines, total_duration)

    durations = []
    prev_end = 0.0
    idx = 0
    for count in word_counts:
        idx += count
        end = word_ends_sec[idx - 1]
        durations.append(max(end - prev_end, 0.1))
        prev_end = end
    return durations


def _try_gtts(lines: list[str], out_path: str) -> Narration | None:
    try:
        from gtts import gTTS
    except ImportError:
        return None

    full_text = " ".join(lines)
    try:
        tts = gTTS(full_text, lang="ko")
        tts.save(out_path)
    except Exception:
        if os.path.exists(out_path):
            os.remove(out_path)
        return None

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        return None

    duration = _audio_duration_seconds(out_path)
    line_durations = _estimate_line_durations(lines, duration)
    return Narration(audio_path=out_path, duration=duration, line_durations=line_durations, engine="gtts")


def _make_silent_track(lines: list[str], out_path: str) -> Narration:
    line_durations = _estimate_line_durations(lines)
    total_duration = sum(line_durations) + 0.6
    sample_rate = 24000
    n_frames = int(total_duration * sample_rate)

    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)

    return Narration(audio_path=out_path, duration=total_duration, line_durations=line_durations, engine="silent")


def _audio_duration_seconds(path: str) -> float:
    from moviepy import AudioFileClip

    clip = AudioFileClip(path)
    try:
        return float(clip.duration)
    finally:
        clip.close()


def synthesize(lines: list[str], voice_label: str, work_dir: str) -> Narration:
    """대본 줄들을 하나의 내레이션 오디오로 합성한다.

    edge-tts → gTTS → 무음 트랙 순서로 시도한다.
    """
    os.makedirs(work_dir, exist_ok=True)
    voice = VOICES.get(voice_label, VOICES["한국어 - 여성 (선희)"])

    edge_path = os.path.join(work_dir, "narration_edge.mp3")
    result = _try_edge_tts(lines, voice, edge_path)
    if result is not None:
        return result

    gtts_path = os.path.join(work_dir, "narration_gtts.mp3")
    result = _try_gtts(lines, gtts_path)
    if result is not None:
        return result

    silent_path = os.path.join(work_dir, "narration_silent.wav")
    return _make_silent_track(lines, silent_path)
