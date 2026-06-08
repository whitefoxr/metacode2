# --------------------------------------------
# 동기부여 유튜브 쇼츠 자동 제작 에이전트
# 대본 생성(텍스트/이미지) -> 배경 이미지 생성 -> 음성 합성(TTS) -> 자막 합성 -> mp4 출력
# --------------------------------------------
import os
import tempfile

import streamlit as st

from shorts import images as image_gen
from shorts import script_generator, video_builder, visuals
from shorts.tts import VOICES

st.set_page_config(page_title="동기부여 쇼츠 에이전트", page_icon="🎬", layout="centered")

st.title("🎬 동기부여 쇼츠 제작 에이전트")
st.markdown(
    "주제만 고르면 **대본 → 배경 이미지 → 내레이션 → 자막**까지 자동으로 합성해 "
    "9:16 세로형 쇼츠 mp4를 만들어 드립니다."
)

for key, default in (
    ("script", None),
    ("script_images", None),
    ("build_result", None),
    ("uploaded_image_bytes", None),
):
    if key not in st.session_state:
        st.session_state[key] = default

ANTHROPIC_AVAILABLE = bool(os.environ.get("ANTHROPIC_API_KEY"))
IMAGE_GEN_AVAILABLE = image_gen.is_available()

# --------------------------------------------
# 1. 대본 설정
# --------------------------------------------
st.subheader("1. 대본 만들기")

mode = st.radio(
    "대본 생성 방식",
    ["주제로 생성하기", "이미지로 생성하기"],
    horizontal=True,
    help="이미지 업로드 모드는 Claude Vision을 사용해 이미지 속 글자/분위기를 바탕으로 대본을 작성합니다.",
)

col1, col2 = st.columns(2)
with col1:
    theme = st.selectbox("주제(테마)", script_generator.available_themes())
    tone = st.selectbox("톤앤매너", script_generator.available_tones())
with col2:
    topic = st.text_input("세부 주제 (선택)", placeholder="예: 월요일 아침, 취업 준비, 운동 시작…")
    num_lines = st.slider("본문 문장 수", min_value=2, max_value=6, value=4)

uploaded_file = None
if mode == "이미지로 생성하기":
    uploaded_file = st.file_uploader("대본의 소재가 될 이미지를 업로드하세요", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="업로드한 이미지", width=240)
    if not ANTHROPIC_AVAILABLE:
        st.warning("⚠️ 이미지 기반 대본 생성에는 ANTHROPIC_API_KEY가 필요합니다.")

seed = st.number_input("랜덤 시드 (같은 값이면 같은 결과 재현)", min_value=0, max_value=9999, value=0, step=1)

if ANTHROPIC_AVAILABLE:
    st.caption("✅ Claude API로 후킹 도입부 → 빠른 전개 → 여운 있는 마무리 구조의 대본을 생성합니다.")
else:
    st.caption("ℹ️ ANTHROPIC_API_KEY가 없어 큐레이션된 템플릿 대본을 사용합니다.")


def _generate_script():
    if mode == "이미지로 생성하기":
        if uploaded_file is None:
            st.warning("이미지를 먼저 업로드해주세요.")
            return
        image_bytes = uploaded_file.getvalue()
        with st.spinner("이미지를 분석해 대본을 작성하는 중..."):
            script = script_generator.generate_script_from_image(
                image_bytes=image_bytes,
                media_type=uploaded_file.type or "image/png",
                theme=theme,
                tone=tone,
                num_lines=num_lines,
            )
        if script is None:
            st.error("이미지 기반 대본 생성에 실패했습니다 (API 키를 확인하거나 다시 시도해주세요). 주제 기반으로 생성합니다.")
            script = script_generator.generate_script(theme=theme, topic=topic, tone=tone, num_lines=num_lines, seed=int(seed))
    else:
        with st.spinner("대본을 생성하는 중..."):
            script = script_generator.generate_script(theme=theme, topic=topic, tone=tone, num_lines=num_lines, seed=int(seed))

    st.session_state.script = script
    st.session_state.script_images = None
    st.session_state.build_result = None


gen_col1, gen_col2 = st.columns([1, 1])
with gen_col1:
    if st.button("✍️ 대본 생성하기", use_container_width=True):
        _generate_script()
with gen_col2:
    if st.session_state.script is not None:
        if st.button("🔁 다른 버전으로 다시 생성", use_container_width=True):
            st.session_state.seed_bump = int(seed) + 1 + st.session_state.get("seed_bump", 0)
            seed = st.session_state.seed_bump
            _generate_script()

script = st.session_state.script

# --------------------------------------------
# 2. 대본 확인 및 수정
# --------------------------------------------
if script:
    st.subheader("2. 대본 확인 및 수정")
    source_label = "Claude 생성" if script.source == "claude" else "템플릿 조합"
    st.caption(f"생성 방식: {source_label} · 마음에 들지 않으면 위에서 다시 생성하거나 아래에서 직접 수정하세요.")

    hook = st.text_area("후크 (도입부 — 시청자의 시선을 붙잡는 한 문장)", value=script.hook, height=70)
    body_text = st.text_area(
        "본문 (한 줄에 한 문장 — 빠른 호흡으로 이어지도록)",
        value="\n".join(script.lines),
        height=160,
    )
    cta = st.text_area("마무리 문구 (여운/깨달음 — 댓글을 유도하는 한 문장)", value=script.cta, height=70)

    edited_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    if (script.hook, script.lines, script.cta) != (hook.strip(), edited_lines, cta.strip()):
        script.hook = hook.strip()
        script.lines = edited_lines
        script.cta = cta.strip()
        st.session_state.script_images = None  # 대본이 바뀌면 이미지 미리보기 초기화
        st.session_state.build_result = None

    # --------------------------------------------
    # 3. 배경 이미지 생성 및 확인
    # --------------------------------------------
    st.subheader("3. 배경 이미지 생성 및 확인")

    color_theme = st.selectbox("배경 색감/분위기 테마 (이미지 생성의 무드 힌트로도 사용됨)", visuals.available_themes())

    if not IMAGE_GEN_AVAILABLE:
        st.info(
            "ℹ️ GEMINI_API_KEY(나노바나나)가 설정되어 있지 않아 문단별 이미지 대신 "
            "코드로 생성한 그라디언트 배경이 사용됩니다. 키를 설정하면 각 문장의 분위기에 "
            "어울리는 이미지를 자동 생성할 수 있습니다."
        )
    else:
        all_lines = script.all_lines()

        if st.button("🖼️ 문단별 배경 이미지 생성하기", use_container_width=True):
            progress = st.progress(0.0, text="이미지 생성 준비 중...")
            generated = []
            for i, line in enumerate(all_lines):
                progress.progress(i / len(all_lines), text=f"({i + 1}/{len(all_lines)}) 이미지 생성 중: {line[:20]}…")
                generated.append(image_gen.generate_image_for_line(line, mood_hint=color_theme))
            progress.progress(1.0, text="완료")
            st.session_state.script_images = generated

        images = st.session_state.script_images
        if images:
            st.caption("각 문장의 배경 이미지입니다. 마음에 들지 않으면 해당 이미지만 다시 생성할 수 있어요.")
            for i, (line, img) in enumerate(zip(all_lines, images)):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if img is not None:
                        st.image(img, use_container_width=True)
                    else:
                        st.warning("생성 실패 — 최종 영상에서는 그라디언트 배경으로 대체됩니다.")
                with c2:
                    st.markdown(f"**{line}**")
                    if st.button("🔁 이 이미지만 다시 생성", key=f"regen_img_{i}"):
                        with st.spinner("다시 생성하는 중..."):
                            new_img = image_gen.generate_image_for_line(line, mood_hint=color_theme)
                        st.session_state.script_images[i] = new_img
                        st.rerun()

    # --------------------------------------------
    # 4. 음성 설정 및 영상 생성
    # --------------------------------------------
    st.subheader("4. 내레이션 설정 및 영상 생성")
    voice_label = st.selectbox("내레이션 음성", list(VOICES.keys()))

    if st.button("🎬 쇼츠 영상 생성하기", type="primary", use_container_width=True):
        progress = st.progress(0.0, text="준비 중...")

        def on_progress(stage, frac):
            progress.progress(min(max(frac, 0.0), 1.0), text=stage)

        work_dir = os.path.join(tempfile.gettempdir(), "motivational_shorts")
        try:
            result = video_builder.build_short(
                script,
                theme_color=color_theme,
                voice_label=voice_label,
                work_dir=work_dir,
                seed=int(seed),
                images=st.session_state.script_images,
                progress_cb=on_progress,
            )
            st.session_state.build_result = result
        except Exception as e:
            st.error(f"영상 생성 중 오류가 발생했습니다: {e}")

# --------------------------------------------
# 5. 결과 미리보기 및 다운로드
# --------------------------------------------
result = st.session_state.build_result
if result:
    st.subheader("5. 결과 미리보기 및 다운로드")

    if result.narration_engine == "silent":
        st.warning(
            "⚠️ 현재 환경에서 음성 합성(TTS) 서비스에 접속할 수 없어 무음 내레이션으로 제작되었습니다. "
            "인터넷 연결이 가능한 환경에서 실행하면 실제 음성 내레이션이 포함됩니다. "
            "(자막은 정상적으로 표시됩니다.)"
        )
    elif result.narration_engine == "gtts":
        st.info("ℹ️ gTTS 엔진으로 음성을 합성했습니다. 자막 타이밍은 추정치 기반입니다.")
    else:
        st.success("✅ 고품질 음성 합성(edge-tts) 엔진으로 내레이션을 생성했습니다.")

    if result.used_generated_images:
        st.caption("🖼️ 문단별 생성 이미지를 배경으로 사용했습니다.")
    else:
        st.caption("🎨 코드로 생성한 그라디언트 배경을 사용했습니다.")

    st.video(result.video_path)
    st.caption(f"길이: 약 {result.duration:.1f}초 · 해상도: 1080×1920 (9:16)")

    with open(result.video_path, "rb") as f:
        st.download_button(
            "⬇️ mp4 파일 다운로드",
            data=f.read(),
            file_name="motivational_short.mp4",
            mime="video/mp4",
            use_container_width=True,
        )

st.divider()
with st.expander("ℹ️ 작동 방식"):
    st.markdown(
        """
        1. **대본 생성**: 주제 기반(Claude 또는 템플릿) 또는 이미지 업로드 기반(Claude Vision)으로
           "후킹 도입 → 빠른 전개 → 여운 있는 마무리(댓글 유도)" 구조의 대본을 만듭니다.
           마음에 들지 않으면 다시 생성하거나 직접 수정할 수 있습니다.
        2. **배경 이미지 생성**: GEMINI_API_KEY가 있으면 Google의 이미지 생성 모델("나노바나나")로
           각 문장의 분위기에 어울리는 9:16 이미지를 만들고, 마음에 안 드는 이미지는 개별적으로
           다시 생성할 수 있습니다. 키가 없으면 코드로 생성한 그라디언트 배경을 사용합니다.
        3. **내레이션 합성(TTS)**: edge-tts → gTTS → 무음 트랙 순서로 자동 대체됩니다.
        4. **자막 합성**: 한글 폰트를 저장소에 내장해 어떤 환경에서도 깨지지 않으며,
           각 문장의 길이와 음성 길이에 맞춰 타이밍을 계산하고 페이드 효과를 입힙니다.
        5. 모든 요소를 합성해 최종 mp4 파일로 내보냅니다.
        """
    )
