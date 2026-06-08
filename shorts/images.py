"""대본 문단별로 어울리는 배경 이미지를 생성한다.

Google Gemini의 이미지 생성 모델 "나노바나나"(gemini-2.5-flash-image)를 사용한다.
GEMINI_API_KEY(또는 GOOGLE_API_KEY)가 없거나 생성에 실패하면 None을 반환하며,
호출 측에서는 프로시저럴 그라디언트 배경으로 자동 대체한다.
"""
import os
from io import BytesIO

from PIL import Image

from .visuals import HEIGHT, WIDTH

_MODEL = "gemini-2.5-flash-image"

_last_error: str | None = None


def get_last_error() -> str | None:
    """가장 최근 이미지 생성 실패의 원인 메시지를 반환한다 (진단용)."""
    return _last_error

_STYLE_SUFFIX = (
    "세로형(9:16) 영상의 배경으로 쓸 시네마틱한 이미지. "
    "사람의 얼굴이 두드러지게 나오거나, 글자/텍스트/로고가 들어가지 않도록 해줘. "
    "화면 중앙 아래쪽에 자막이 올라갈 것을 감안해서 하단부는 비교적 단순하고 "
    "차분한 영역으로 구성해줘."
)


def is_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def generate_image_for_line(line: str, mood_hint: str = "") -> Image.Image | None:
    """대본 한 줄의 정서/분위기에 어울리는 9:16 배경 이미지를 생성한다.

    실패하거나 API 키가 없으면 None을 반환한다.
    """
    global _last_error

    if not is_available():
        _last_error = "GEMINI_API_KEY(또는 GOOGLE_API_KEY)가 설정되어 있지 않습니다."
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        mood_part = f"전체적인 영상의 무드: {mood_hint}\n" if mood_hint else ""
        prompt = (
            f'다음 동기부여 문구가 자막으로 나오는 장면의 배경 이미지를 만들어줘: "{line}"\n'
            f"{mood_part}"
            "이 문장이 주는 감정과 이미지를 은유적으로 표현하는 풍경/사물/추상적 비주얼로 그려줘.\n"
            f"{_STYLE_SUFFIX}"
        )
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="9:16"),
            ),
        )
        candidates = response.candidates or []
        if not candidates:
            _last_error = f"응답에 이미지 후보가 없습니다. (finish_reason: {getattr(response, 'prompt_feedback', None)})"
            return None
        for part in candidates[0].content.parts:
            if part.inline_data is not None:
                img = Image.open(BytesIO(part.inline_data.data)).convert("RGB")
                if img.size != (WIDTH, HEIGHT):
                    img = img.resize((WIDTH, HEIGHT))
                _last_error = None
                return img
        _last_error = "응답에 이미지 데이터가 포함되어 있지 않습니다 (텍스트 응답만 반환됨)."
        return None
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        return None


def generate_images_for_script(lines: list[str], mood_hint: str = "") -> list[Image.Image | None]:
    """대본의 각 줄에 대해 이미지를 생성한다. 실패한 줄은 None으로 채워진다."""
    return [generate_image_for_line(line, mood_hint) for line in lines]
