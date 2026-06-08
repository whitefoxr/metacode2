"""쇼츠용 세로 배경 영상을 코드로 생성한다 (외부 소스 영상/이미지 불필요).

부드럽게 움직이는 그라디언트 + 떠다니는 보케(bokeh) 원으로 구성된
9:16 배경 애니메이션을 만든다.
"""
import math

import numpy as np
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 1080, 1920
FPS = 30

COLOR_THEMES = {
    "새벽 노을": [(255, 154, 92), (255, 94, 98), (90, 60, 120)],
    "깊은 밤하늘": [(15, 32, 70), (40, 60, 110), (90, 50, 140)],
    "푸른 새벽": [(20, 90, 130), (60, 150, 180), (190, 230, 220)],
    "보랏빛 몽환": [(60, 30, 90), (120, 60, 150), (220, 140, 190)],
    "초록 숲속": [(20, 70, 50), (60, 120, 80), (170, 210, 140)],
}


def available_themes() -> list[str]:
    return list(COLOR_THEMES.keys())


def _lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _vertical_gradient(colors, phase: float) -> np.ndarray:
    """3색 그라디언트를 phase(0~1)에 따라 위아래로 천천히 흐르게 만든다."""
    n = len(colors)
    # phase 만큼 색상 정지점을 회전시켜 흐르는 느낌을 준다
    positions = [(i / n + phase) % 1.0 for i in range(n)]
    order = np.argsort(positions)
    sorted_positions = [positions[i] for i in order]
    sorted_colors = [colors[i] for i in order]

    ys = np.linspace(0, 1, HEIGHT)
    gradient = np.zeros((HEIGHT, 3), dtype=np.uint8)

    ext_positions = [p - 1 for p in sorted_positions] + sorted_positions + [p + 1 for p in sorted_positions]
    ext_colors = sorted_colors * 3

    for i in range(len(ext_positions) - 1):
        p0, p1 = ext_positions[i], ext_positions[i + 1]
        if p1 <= 0 or p0 >= 1:
            continue
        mask = (ys >= p0) & (ys <= p1)
        if not mask.any():
            continue
        local_t = np.clip((ys[mask] - p0) / max(p1 - p0, 1e-6), 0, 1)
        c0 = np.array(ext_colors[i])
        c1 = np.array(ext_colors[i + 1])
        gradient[mask] = (c0[None, :] + (c1 - c0)[None, :] * local_t[:, None]).astype(np.uint8)

    return np.repeat(gradient[:, None, :], WIDTH, axis=1)


def _make_particles(rng: np.random.Generator, count: int = 14):
    particles = []
    for _ in range(count):
        particles.append({
            "x": rng.uniform(0.05, 0.95) * WIDTH,
            "y": rng.uniform(0.05, 0.95) * HEIGHT,
            "r": rng.uniform(40, 140),
            "speed": rng.uniform(0.02, 0.06),
            "phase": rng.uniform(0, 2 * math.pi),
            "alpha": rng.uniform(0.06, 0.18),
            "drift_x": rng.uniform(-30, 30),
        })
    return particles


def make_background_clip(theme_name: str, duration: float, seed: int = 0):
    """주어진 테마/길이에 맞는 배경 VideoClip을 생성한다."""
    from moviepy import VideoClip

    colors = COLOR_THEMES.get(theme_name, next(iter(COLOR_THEMES.values())))
    rng = np.random.default_rng(seed)
    particles = _make_particles(rng)

    cycle = max(duration, 1.0)

    def make_frame(t):
        phase = (t / (cycle * 2.2)) % 1.0
        base = _vertical_gradient(colors, phase)
        img = Image.fromarray(base, mode="RGB").convert("RGBA")
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for p in particles:
            wobble = math.sin(t * p["speed"] * 2 * math.pi + p["phase"])
            cx = p["x"] + wobble * p["drift_x"]
            cy = (p["y"] - t * p["speed"] * HEIGHT * 0.6) % HEIGHT
            r = p["r"]
            alpha = int(255 * p["alpha"])
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=(255, 255, 255, alpha),
            )

        composed = Image.alpha_composite(img, overlay).convert("RGB")
        return np.array(composed)

    return VideoClip(make_frame, duration=duration).with_fps(FPS)


def make_still_background(theme_name: str, seed: int = 0) -> Image.Image:
    """단일 정지 그라디언트+보케 이미지를 만든다 (생성 이미지가 없을 때의 대체용)."""
    colors = COLOR_THEMES.get(theme_name, next(iter(COLOR_THEMES.values())))
    base = _vertical_gradient(colors, phase=0.0)
    img = Image.fromarray(base, mode="RGB").convert("RGBA")

    rng = np.random.default_rng(seed)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for p in _make_particles(rng, count=10):
        r = p["r"]
        alpha = int(255 * p["alpha"])
        draw.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=(255, 255, 255, alpha))

    return Image.alpha_composite(img, overlay).convert("RGB")


def _ken_burns_clip(image: Image.Image, duration: float, zoom_in: bool):
    """이미지를 천천히 확대/축소하며 보여주는 클립을 만든다 (정적인 느낌을 줄여줌)."""
    from moviepy import ImageClip

    start_scale, end_scale = (1.0, 1.08) if zoom_in else (1.08, 1.0)
    duration = max(duration, 0.1)

    clip = ImageClip(np.array(image)).with_duration(duration)

    def scale_at(t):
        ratio = min(t / duration, 1.0)
        return start_scale + (end_scale - start_scale) * ratio

    return clip.resized(scale_at).with_position("center")


def make_image_sequence_clip(images: list[Image.Image], durations: list[float], seed: int = 0):
    """문단별 이미지를 순서대로 이어 붙여 켄 번즈 효과가 있는 배경 영상을 만든다."""
    from moviepy import CompositeVideoClip

    rng = np.random.default_rng(seed)
    clips = []
    t = 0.0
    for img, dur in zip(images, durations):
        zoom_in = bool(rng.integers(0, 2))
        clip = _ken_burns_clip(img, dur, zoom_in=zoom_in).with_start(t)
        clips.append(clip)
        t += dur

    return CompositeVideoClip(clips, size=(WIDTH, HEIGHT)).with_duration(t)
