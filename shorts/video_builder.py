"""대본 + 내레이션 + 배경 + 자막을 하나의 쇼츠 mp4로 합성한다."""
import os
from dataclasses import dataclass

from . import subtitles, tts, visuals
from .script_generator import Script


@dataclass
class BuildResult:
    video_path: str
    duration: float
    narration_engine: str
    script: Script


def build_short(
    script: Script,
    *,
    theme_color: str,
    voice_label: str,
    work_dir: str,
    seed: int = 0,
    progress_cb=None,
) -> BuildResult:
    """완성된 쇼츠 mp4를 생성하고 결과 정보를 반환한다.

    progress_cb(stage: str, fraction: float) 콜백으로 진행 상황을 알릴 수 있다.
    """
    from moviepy import AudioFileClip, CompositeVideoClip

    os.makedirs(work_dir, exist_ok=True)

    def report(stage, frac):
        if progress_cb:
            progress_cb(stage, frac)

    lines = script.all_lines()

    report("내레이션 음성 합성 중...", 0.1)
    narration = tts.synthesize(lines, voice_label, work_dir)

    report("배경 영상 생성 중...", 0.3)
    background = visuals.make_background_clip(theme_color, duration=narration.duration, seed=seed)

    report("자막 합성 중...", 0.55)
    subtitle_clips = subtitles.build_subtitle_clips(lines, narration.line_durations)

    layers = [background, *subtitle_clips]
    composite = CompositeVideoClip(layers, size=(visuals.WIDTH, visuals.HEIGHT)).with_duration(narration.duration)

    if narration.audio_path and narration.engine != "silent":
        audio = AudioFileClip(narration.audio_path)
        composite = composite.with_audio(audio)

    report("최종 영상 렌더링 중...", 0.7)
    out_path = os.path.join(work_dir, "motivational_short.mp4")
    composite.write_videofile(
        out_path,
        codec="libx264",
        audio_codec="aac",
        fps=visuals.FPS,
        preset="medium",
        threads=2,
        logger=None,
    )

    report("완료", 1.0)
    return BuildResult(
        video_path=out_path,
        duration=narration.duration,
        narration_engine=narration.engine,
        script=script,
    )
