"""모티베이션 쇼츠 대본 생성기.

ANTHROPIC_API_KEY가 설정되어 있으면 Claude로 주제에 맞는 대본을 생성하고,
없거나 호출에 실패하면 큐레이션된 템플릿 뱅크에서 조합해 대본을 만든다.
"""
import json
import os
import random
from dataclasses import dataclass, field


@dataclass
class Script:
    title: str
    hook: str
    lines: list[str]
    cta: str
    source: str = "template"  # "claude" | "template"

    def all_lines(self) -> list[str]:
        return [self.hook, *self.lines, self.cta]


# 주제별 후크 / 본문 / 마무리 문구 뱅크 (한국어)
THEME_BANKS = {
    "성공과 도전": {
        "hooks": [
            "아직 늦지 않았습니다.",
            "당신의 1분이 오늘을 바꿉니다.",
            "이 영상을 본 당신에게 건네는 한마디.",
        ],
        "lines": [
            "실패는 끝이 아니라 다음 시도를 위한 데이터일 뿐입니다.",
            "오늘의 작은 행동이 내일의 결과를 만듭니다.",
            "남들과 비교하지 마세요. 어제의 나와 비교하세요.",
            "포기하고 싶은 순간이 바로 성장의 신호입니다.",
            "준비되지 않아도 일단 한 걸음 내딛으세요.",
            "당신이 멈추지 않는 한, 길은 계속됩니다.",
        ],
        "ctas": [
            "오늘도 한 걸음, 당신은 해낼 수 있습니다.",
            "지금 이 순간이 시작입니다.",
            "당신의 다음 도전을 응원합니다.",
        ],
    },
    "끈기와 인내": {
        "hooks": [
            "포기하기엔 아직 이릅니다.",
            "버티는 사람이 결국 웃습니다.",
            "지금 힘든 당신에게.",
        ],
        "lines": [
            "가장 어두운 밤도 결국 해가 뜨며 끝납니다.",
            "느려도 괜찮습니다. 멈추지만 않으면 됩니다.",
            "오늘 흘린 땀은 내일의 자신감이 됩니다.",
            "버티는 것 자체가 이미 용기입니다.",
            "지금의 고비는 성장의 다른 이름입니다.",
            "조금만 더 견디면, 풍경이 달라집니다.",
        ],
        "ctas": [
            "끝까지 가본 사람만이 정상을 봅니다.",
            "당신의 인내는 헛되지 않습니다.",
            "오늘 하루도 묵묵히 버텨낸 당신, 멋집니다.",
        ],
    },
    "자존감과 자기확신": {
        "hooks": [
            "당신은 충분히 소중한 사람입니다.",
            "거울 속 당신에게 해주고 싶은 말.",
            "스스로를 의심하는 당신에게.",
        ],
        "lines": [
            "당신의 속도로 가도 괜찮습니다.",
            "완벽하지 않아도 당신은 가치 있는 존재입니다.",
            "타인의 기준이 아닌, 나만의 기준으로 살아도 됩니다.",
            "오늘의 당신은 어제보다 분명히 성장했습니다.",
            "스스로에게 조금 더 다정해져도 괜찮습니다.",
            "당신을 가장 잘 응원할 사람은 바로 당신입니다.",
        ],
        "ctas": [
            "당신은 이미 충분히 잘하고 있습니다.",
            "오늘 하루도 자신을 믿어주세요.",
            "당신 자신을 사랑하는 하루 보내세요.",
        ],
    },
    "아침 동기부여": {
        "hooks": [
            "오늘 하루를 시작하는 당신에게.",
            "눈을 뜬 지금, 새로운 기회가 시작됩니다.",
            "좋은 아침입니다. 오늘도 함께 시작해봐요.",
        ],
        "lines": [
            "오늘은 아직 아무도 살아보지 않은 새로운 하루입니다.",
            "작은 습관 하나가 하루의 분위기를 바꿉니다.",
            "어제의 실수는 어제에 두고, 오늘을 새로 그려보세요.",
            "햇살처럼 가볍게, 오늘을 시작해봐요.",
            "지금 떠오르는 그 다짐, 오늘 한번 실천해보세요.",
            "당신의 하루가 활기차게 시작되길 바랍니다.",
        ],
        "ctas": [
            "오늘도 좋은 하루 되세요.",
            "당신의 하루를 응원합니다.",
            "활기찬 하루의 시작, 함께해요.",
        ],
    },
    "실패와 극복": {
        "hooks": [
            "넘어져 본 사람만 아는 이야기.",
            "오늘 무너진 것 같은 당신에게.",
            "다시 일어서는 법에 대하여.",
        ],
        "lines": [
            "넘어진 것이 아니라, 다시 일어서는 법을 배우는 중입니다.",
            "실수는 당신이 도전했다는 증거입니다.",
            "지금의 좌절은 다음 성공의 재료가 됩니다.",
            "완벽한 길이 아니어도, 당신만의 길이 됩니다.",
            "다시 시작할 용기가 있다면, 이미 절반은 성공입니다.",
            "넘어진 자리에서, 다시 한 번 일어나 보세요.",
        ],
        "ctas": [
            "다시 일어서는 당신을 응원합니다.",
            "오늘의 실패가 내일의 디딤돌이 될 거예요.",
            "당신은 다시 일어설 힘이 있습니다.",
        ],
    },
}

THEME_TONE_PRESETS = {
    "잔잔하고 따뜻하게": "차분하고 다정한 톤으로, 위로를 건네듯",
    "강렬하고 힘있게": "에너지 넘치고 단호한 톤으로, 동기를 부여하듯",
    "담백하고 차분하게": "군더더기 없이 담백하고 차분한 톤으로",
}


def available_themes() -> list[str]:
    return list(THEME_BANKS.keys())


def available_tones() -> list[str]:
    return list(THEME_TONE_PRESETS.keys())


def _build_with_template(theme: str, topic: str, num_lines: int, rng: random.Random) -> Script:
    bank = THEME_BANKS.get(theme, next(iter(THEME_BANKS.values())))
    hook = rng.choice(bank["hooks"])
    body = rng.sample(bank["lines"], k=min(num_lines, len(bank["lines"])))
    cta = rng.choice(bank["ctas"])

    title = topic.strip() if topic.strip() else theme
    return Script(title=title, hook=hook, lines=body, cta=cta, source="template")


_CLAUDE_SYSTEM_PROMPT = """\
너는 유튜브 쇼츠 동기부여 영상의 대본을 쓰는 전문 작가다.
목표는 "끝까지 보고, 댓글을 남기고 싶게 만드는" 30~50초 분량의 한국어 대본이다.

구조와 규칙:
1. hook (후크, 도입부 1문장)
   - 영상 시작 1~2초 안에 시청자의 시선을 붙잡아야 한다.
   - "혹시 ~한 적 있나요?", "이 말을 들어야 할 사람", "아무도 말해주지 않은 사실" 처럼
     궁금증을 자극하거나 자신의 이야기처럼 느끼게 만드는 문장으로 시작한다.
   - 뻔한 인사말("안녕하세요", "오늘은...")로 시작하지 않는다.
2. lines (본문)
   - 각 문장은 자막 한 줄 분량으로 짧고 명확해야 한다 (12~28자 권장).
   - 문장마다 새로운 정보·관점·이미지를 던져 호흡을 빠르게 이어가고, 같은 말을 반복하지 않는다.
   - 지루하지 않도록 문장 길이와 리듬에 변주를 준다 (단문 - 약간 긴 문장 - 단문 순서 등).
   - 과장되거나 상투적인 표현은 피하고 진심이 느껴지는 담백한 문장을 쓴다.
3. cta (마무리, 1문장)
   - 결론을 다 말해주지 말고, 시청자가 스스로 생각해보게 만드는 "여운 있는 깨달음"으로 끝낸다.
   - 자연스럽게 댓글을 남기고 싶어지도록 질문형이거나, 자신의 이야기를 떠올리게 하는 문장이 좋다.
   - 직접적으로 "댓글 달아주세요", "구독하세요" 같은 요청 문구는 쓰지 않는다 (어색하고 진부함).

반드시 JSON 객체 하나만 출력한다. 다른 설명, 마크다운, 코드블록은 절대 포함하지 않는다.
JSON 형식: {"hook": "도입부 한 문장", "lines": ["본문 문장1", "본문 문장2", ...], "cta": "마무리 한 문장"}
"lines" 배열의 길이는 요청된 줄 수와 정확히 같아야 한다.
"""


def _parse_script_json(text: str, title: str) -> Script | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    data = json.loads(text)

    lines = [str(line).strip() for line in data["lines"] if str(line).strip()]
    if not lines:
        return None
    return Script(
        title=title,
        hook=str(data["hook"]).strip(),
        lines=lines,
        cta=str(data["cta"]).strip(),
        source="claude",
    )


def _call_claude(system_prompt: str, content) -> str:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def _build_with_claude(theme: str, topic: str, tone: str, num_lines: int) -> Script | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    try:
        tone_desc = THEME_TONE_PRESETS.get(tone, tone)
        user_prompt = (
            f"주제/테마: {theme}\n"
            f"세부 주제(선택): {topic or '(특별히 없음, 테마에 맞게 자유롭게)'}\n"
            f"톤앤매너: {tone_desc}\n"
            f"본문 문장 개수: {num_lines}\n"
            "위 조건에 맞는 쇼츠 대본을 JSON으로 작성해줘."
        )
        text = _call_claude(_CLAUDE_SYSTEM_PROMPT, user_prompt)
        title = topic.strip() if topic.strip() else theme
        return _parse_script_json(text, title)
    except Exception:
        return None


_EXTRACT_SYSTEM_PROMPT = """\
너는 이미지 속 텍스트와 메시지를 정확히 읽어내는 전문가다.
이미지에서 발견한 글자(문구, 명언, 메모, 손글씨 등)를 가능한 그대로 옮기고,
글자가 없다면 이미지가 전하는 분위기·감정·핵심 메시지를 한두 문장으로 요약한다.
군더더기 설명 없이, 추출/요약한 내용만 간결하게 출력한다.
"""


def extract_image_message(image_bytes: bytes, media_type: str) -> str | None:
    """이미지 속 글자나 핵심 메시지를 추출한다 (Claude Vision 사용).

    ANTHROPIC_API_KEY가 없거나 호출에 실패하면 None을 반환한다.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    try:
        import base64

        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        user_content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            },
            {
                "type": "text",
                "text": "이 이미지에서 글자나 핵심 메시지를 추출(또는 분위기를 요약)해줘.",
            },
        ]
        text = _call_claude(_EXTRACT_SYSTEM_PROMPT, user_content)
        text = text.strip()
        return text or None
    except Exception:
        return None


def generate_script_like(
    reference_text: str,
    theme: str,
    tone: str = "잔잔하고 따뜻하게",
    num_lines: int = 4,
) -> Script | None:
    """주어진 글(레퍼런스)과 비슷한 결의 새로운 동기부여 쇼츠 대본을 생성한다.

    이미지에서 추출한 문구를 그대로 베끼는 대신, 같은 정서·메시지 방향을
    살린 새로운 대본을 작성한다. ANTHROPIC_API_KEY가 없으면 None을 반환한다.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    try:
        tone_desc = THEME_TONE_PRESETS.get(tone, tone)
        user_prompt = (
            f"아래는 참고할 글(이미지에서 추출한 문구 또는 분위기 요약)이야:\n"
            f"---\n{reference_text}\n---\n\n"
            "이 글이 전하는 메시지와 정서의 '결'을 살려서, 그대로 베끼지 말고 "
            "새로운 동기부여 쇼츠 대본을 작성해줘.\n"
            f"- 전체적인 주제/테마: {theme}\n"
            f"- 톤앤매너: {tone_desc}\n"
            f"- 본문 문장 개수: {num_lines}"
        )
        text = _call_claude(_CLAUDE_SYSTEM_PROMPT, user_prompt)
        return _parse_script_json(text, title=theme)
    except Exception:
        return None


def generate_script(
    theme: str,
    topic: str = "",
    tone: str = "잔잔하고 따뜻하게",
    num_lines: int = 4,
    seed: int | None = None,
) -> Script:
    """동기부여 쇼츠 대본을 생성한다.

    Claude API 사용이 가능하면 이를 우선 사용하고, 실패 시 템플릿 뱅크로 대체한다.
    """
    script = _build_with_claude(theme, topic, tone, num_lines)
    if script is not None:
        return script

    rng = random.Random(seed)
    return _build_with_template(theme, topic, num_lines, rng)
