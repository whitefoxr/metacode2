"""대본 줄과 타이밍 정보로 쇼츠용 자막 클립을 생성한다."""
import glob

from .visuals import HEIGHT, WIDTH

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
    # 한글 글리프를 포함하는 폰트 (Noto/Nanum이 없을 때의 대비책)
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _resolve_font() -> str | None:
    for candidate in _FONT_CANDIDATES:
        matches = glob.glob(candidate)
        if matches:
            return matches[0]
    fallback = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    return fallback[0] if fallback else None


FONT_PATH = _resolve_font()

_GAP = 0.12  # 자막 줄 사이 미세한 공백 (초)
_FADE = 0.18


def build_subtitle_clips(lines: list[str], line_durations: list[float]):
    """각 자막 줄을 화면 중앙 하단에 띄우는 TextClip 리스트를 만든다."""
    from moviepy import TextClip, vfx

    clips = []
    t = 0.0
    for line, dur in zip(lines, line_durations):
        visible = max(dur - _GAP, 0.4)
        clip = (
            TextClip(
                font=FONT_PATH,
                text=line,
                font_size=64,
                color="white",
                stroke_color="black",
                stroke_width=3,
                method="caption",
                size=(int(WIDTH * 0.84), None),
                text_align="center",
            )
            .with_start(t)
            .with_duration(visible)
            .with_position(("center", int(HEIGHT * 0.62)))
            .with_effects([vfx.CrossFadeIn(_FADE), vfx.CrossFadeOut(_FADE)])
        )
        clips.append(clip)
        t += dur
    return clips


def total_duration(line_durations: list[float]) -> float:
    return sum(line_durations)
