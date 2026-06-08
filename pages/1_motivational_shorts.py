# --------------------------------------------
# 동기부여 유튜브 쇼츠 자동 제작 에이전트
# 대본 생성 -> 음성 합성(TTS) -> 배경 영상 생성 -> 자막 합성 -> mp4 출력
# --------------------------------------------
import os
import tempfile

import streamlit as st

from shorts import script_generator, video_builder, visuals
from shorts.tts import VOICES

st.set_page_config(page_title="동기부여 쇼츠 에이전트", page_icon="🎬", layout="centered")

st.title("🎬 동기부여 쇼츠 제작 에이전트")
st.markdown(
    "주제만 고르면 **대본 → 내레이션 → 배경 영상 → 자막**까지 자동으로 합성해 "
    "9:16 세로형 쇼츠 mp4를 만들어 드립니다."
)

if "script" not in st.session_state:
    st.session_state.script = None
if "build_result" not in st.session_state:
    st.session_state.build_result = None

st.subheader("1. 대본 설정")

col1, col2 = st.columns(2)
with col1:
    theme = st.selectbox("주제(테마)", script_generator.available_themes())
    tone = st.selectbox("톤앤매너", script_generator.available_tones())
with col2:
    topic = st.text_input("세부 주제 (선택)", placeholder="예: 월요일 아침, 취업 준비, 운동 시작…")
    num_lines = st.slider("본문 문장 수", min_value=2, max_value=6, value=4)

seed = st.number_input("랜덤 시드 (같은 값이면 같은 결과 재현)", min_value=0, max_value=9999, value=0, step=1)

if st.session_state.get("anthropic_notice") is None:
    st.session_state.anthropic_notice = bool(os.environ.get("ANTHROPIC_API_KEY"))

if st.session_state.anthropic_notice:
    st.caption("✅ Claude API로 주제에 맞는 대본을 생성합니다 (실패 시 큐레이션 템플릿으로 대체).")
else:
    st.caption("ℹ️ ANTHROPIC_API_KEY가 설정되어 있지 않아 큐레이션된 템플릿 대본을 사용합니다.")

if st.button("✍️ 대본 생성하기", use_container_width=True):
    with st.spinner("대본을 생성하는 중..."):
        st.session_state.script = script_generator.generate_script(
            theme=theme, topic=topic, tone=tone, num_lines=num_lines, seed=int(seed)
        )
    st.session_state.build_result = None

script = st.session_state.script
if script:
    st.subheader("2. 대본 확인 및 수정")
    source_label = "Claude 생성" if script.source == "claude" else "템플릿 조합"
    st.caption(f"생성 방식: {source_label}")

    hook = st.text_area("후크 (도입부)", value=script.hook, height=70)
    body_text = st.text_area(
        "본문 (한 줄에 한 문장)",
        value="\n".join(script.lines),
        height=150,
    )
    cta = st.text_area("마무리 문구 (CTA)", value=script.cta, height=70)

    edited_lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    script.hook = hook.strip()
    script.lines = edited_lines
    script.cta = cta.strip()

    st.subheader("3. 영상 스타일 설정")
    col3, col4 = st.columns(2)
    with col3:
        color_theme = st.selectbox("배경 색감 테마", visuals.available_themes())
    with col4:
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
                progress_cb=on_progress,
            )
            st.session_state.build_result = result
        except Exception as e:
            st.error(f"영상 생성 중 오류가 발생했습니다: {e}")

result = st.session_state.build_result
if result:
    st.subheader("4. 결과 미리보기 및 다운로드")

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
        1. **대본 생성**: `ANTHROPIC_API_KEY`가 설정되어 있으면 Claude가 주제에 맞는 대본을 작성하고,
           그렇지 않으면 큐레이션된 템플릿 문구를 조합합니다.
        2. **내레이션 합성(TTS)**: edge-tts → gTTS → 무음 트랙 순서로 시도하며, 사용 가능한
           엔진으로 자동 대체됩니다.
        3. **배경 영상 생성**: 외부 영상/이미지 없이 코드로 그라디언트와 보케 애니메이션을
           만들어 9:16 세로 영상을 구성합니다.
        4. **자막 합성**: 각 문장의 길이와 음성 길이에 맞춰 타이밍을 계산하고, 페이드 인/아웃
           효과가 있는 자막을 입힙니다.
        5. 모든 요소를 합성해 최종 mp4 파일로 내보냅니다.
        """
    )
