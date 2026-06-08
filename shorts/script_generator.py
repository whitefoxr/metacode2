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
너는 유튜브 쇼츠용 동기부여 영상 대본 작가다.
시청자의 마음을 짧고 강하게 울리는 한국어 대본을 작성한다.
규칙:
- 한 문장은 자막 한 줄로 쓰일 만큼 짧고 명확해야 한다 (각 문장 12~28자 권장).
- 과장되거나 상투적인 표현은 피하고, 진심이 느껴지는 담백한 문장을 쓴다.
- 반드시 JSON 객체 하나만 출력한다. 다른 설명/코드블록 금지.
JSON 형식: {"hook": "도입부 한 문장", "lines": ["본문 문장1", "본문 문장2", ...], "cta": "마무리 한 문장"}
"lines" 배열의 길이는 요청된 줄 수와 정확히 같아야 한다.
"""


def _build_with_claude(theme: str, topic: str, tone: str, num_lines: int) -> Script | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        tone_desc = THEME_TONE_PRESETS.get(tone, tone)
        user_prompt = (
            f"주제/테마: {theme}\n"
            f"세부 주제(선택): {topic or '(특별히 없음, 테마에 맞게 자유롭게)'}\n"
            f"톤앤매너: {tone_desc}\n"
            f"본문 문장 개수: {num_lines}\n"
            "위 조건에 맞는 쇼츠 대본을 JSON으로 작성해줘."
        )
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_CLAUDE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in message.content if block.type == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
        data = json.loads(text)

        lines = [str(line).strip() for line in data["lines"] if str(line).strip()]
        if not lines:
            return None
        title = topic.strip() if topic.strip() else theme
        return Script(
            title=title,
            hook=str(data["hook"]).strip(),
            lines=lines,
            cta=str(data["cta"]).strip(),
            source="claude",
        )
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
