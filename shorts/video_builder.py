"""대본 + 내레이션 + 배경(생성 이미지 또는 프로시저럴) + 자막을 하나의 쇼츠 mp4로 합성한다."""
import os
from dataclasses import dataclass

from PIL import Image

from . import subtitles, tts, visuals
from .script_generator import Script


@dataclass
class BuildResult:
    video_path: str
    duration: float
    narration_engine: str
    script: Script
    used_generated_images: bool


def build_short(
    script: Script,
    *,
    theme_color: str,
    voice_label: str,
    work_dir: str,
    seed: int = 0,
    images: list[Image.Image | None] | None = None,
    narration: tts.Narration | None = None,
    progress_cb=None,
) -> BuildResult:
    """완성된 쇼츠 mp4를 생성하고 결과 정보를 반환한다.

    - images: 문단별로 생성된 배경 이미지 목록 (None이거나 일부 항목이 None이면
      해당 부분은 프로시저럴 그라디언트 배경으로 대체된다).
    - narration: 미리 합성해 둔 내레이션이 있으면 재사용한다 (대본/이미지 미리보기
      단계에서 이미 합성한 경우 중복 호출을 피하기 위함).
    - progress_cb(stage: str, fraction: float) 콜백으로 진행 상황을 알릴 수 있다.
    """
    from moviepy import AudioFileClip, CompositeVideoClip

    os.makedirs(work_dir, exist_ok=True)

    def report(stage, frac):
        if progress_cb:
            progress_cb(stage, frac)

    lines = script.all_lines()

    if narration is None:
        report("내레이션 음성 합성 중...", 0.1)
        narration = tts.synthesize(lines, voice_label, work_dir)

    report("배경 영상 구성 중...", 0.4)
    background, used_generated = _build_background(
        lines, narration.line_durations, images, theme_color, narration.duration, seed
    )

    report("자막 합성 중...", 0.6)
    subtitle_clips = subtitles.build_subtitle_clips(lines, narration.line_durations)

    layers = [background, *subtitle_clips]
    composite = CompositeVideoClip(layers, size=(visuals.WIDTH, visuals.HEIGHT)).with_duration(narration.duration)

    if narration.audio_path and narration.engine != "silent":
        audio = AudioFileClip(narration.audio_path)
        composite = composite.with_audio(audio)

    report("최종 영상 렌더링 중...", 0.75)
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
        used_generated_images=used_generated,
    )


def _build_background(lines, line_durations, images, theme_color, total_duration, seed):
    has_any_image = bool(images) and len(images) == len(lines) and any(img is not None for img in images)
    if has_any_image:
        filled = _fill_missing_images(images, theme_color, seed)
        return visuals.make_image_sequence_clip(filled, line_durations, seed=seed), True

    return visuals.make_background_clip(theme_color, duration=total_duration, seed=seed), False


def _fill_missing_images(images, theme_color, seed):
    """일부 줄의 이미지 생성이 실패했을 때 정지 그라디언트 이미지로 대체한다."""
    filled = []
    for i, img in enumerate(images):
        filled.append(img if img is not None else visuals.make_still_background(theme_color, seed=seed + i))
    return filled
