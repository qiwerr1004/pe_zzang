import streamlit as st
import json
import os
import time
import io
from PIL import Image
import google.generativeai as genai

# PyMuPDF 라이브러리 (PDF -> 이미지 변환용)
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

st.set_page_config(page_title="정보관리기술사 서브노트", layout="wide")

# 1. Session State 초기화
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = ""

if "editing_topic" not in st.session_state:
    st.session_state.editing_topic = None

# 2. 사이드바 API 키 입력 및 등록
st.sidebar.header("🔑 Gemini API 설정")
api_key_input = st.sidebar.text_input(
    "Gemini API Key", 
    value=st.session_state.gemini_api_key, 
    type="password"
)

if st.sidebar.button("키 등록"):
    if api_key_input.strip():
        st.session_state.gemini_api_key = api_key_input.strip()
        st.sidebar.success("API 키가 성공적으로 등록되었습니다!")
        st.rerun()
    else:
        st.sidebar.error("API Key를 입력해 주세요.")

# 3. API 연동 상태 확인 및 설정
api_status = False
if st.session_state.gemini_api_key:
    try:
        genai.configure(api_key=st.session_state.gemini_api_key)
        api_status = True
    except Exception:
        api_status = False

st.sidebar.header("🔑 API 연동 상태")
if api_status:
    st.sidebar.success("Gemini API 연동 성공 ✅")
else:
    st.sidebar.error("Gemini API 연동 필요 ❌ (API 키를 입력 후 등록하세요)")

# 데이터 저장 경로 설정
DATA_FILE = "subnotes.json"
IMG_DIR = "uploaded_images"

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_uploaded_files(uploaded_files, prefix, topic):
    file_paths = []
    if uploaded_files:
        for idx, file in enumerate(uploaded_files):
            file_path = os.path.join(IMG_DIR, f"{prefix}_{topic}_{idx}_{file.name}")
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            file_paths.append(file_path)
    return file_paths

def get_file_paths(note, list_key, legacy_key):
    paths = note.get(list_key, [])
    if not paths and note.get(legacy_key):
        paths = [note[legacy_key]]
    return [p for p in paths if os.path.exists(p)]

def render_file_list(file_paths, key_prefix=""):
    if not file_paths:
        st.caption("등록된 파일 없음")
        return
    for idx, path in enumerate(file_paths):
        filename = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        if ext in [".png", ".jpg", ".jpeg"]:
            st.image(path, caption=filename, use_container_width=True)
        elif ext == ".pdf":
            st.markdown(f"📄 **{filename}**")
            with open(path, "rb") as f:
                st.download_button(
                    label=f"📥 PDF 열기/다운로드",
                    data=f.read(),
                    file_name=filename,
                    mime="application/pdf",
                    key=f"{key_prefix}_pdf_{idx}_{filename}"
                )

def convert_pdf_to_images(pdf_path):
    images = []
    if HAS_FITZ:
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            images.append(Image.open(io.BytesIO(img_bytes)))
    return images

st.title("📚 정보관리기술사 서브노트 & AI 평가 시스템")

tab1, tab2, tab3 = st.tabs(["📝 토픽 입력", "🔍 토픽 조회", "🎯 AI 셀프테스트 평가"])

# ----------------------------------------------------
# 1. 토픽 신규 입력 탭
# ----------------------------------------------------
with tab1:
    st.subheader("토픽 신규 등록")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        topic = st.text_input("토픽명", key="new_topic")
    with col2:
        subject = st.selectbox("과목", ["경영정보/IT서비스", "프로젝트 관리", "소프트웨어 공학", "데이터베이스", "네트워크", "보안", "CA/OS", "인공지능", "통계"], key="new_subject")
    with col3:
        importance = st.select_slider("중요도", options=["S", "A", "B", "C"], value="A", key="new_importance")

    col_k1, col_k2 = st.columns([1, 2])
    with col_k1:
        acronyms = st.text_input("두음 키워드 (예: 정-수-성-효-유-이)", key="new_acronyms")
    with col_k2:
        keywords = st.text_input("핵심 키워드 (쉼표 구분)", key="new_keywords")

    st.markdown("**서브노트 파일 업로드 (이미지/PDF, 다중 선택 가능)**")
    subnote_files = st.file_uploader("서브노트 파일 업로드", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True, key="new_subnote_files")

    st.markdown("**셀프테스트 답안 입력 방식**")
    test_type = st.radio("입력 방식 선택", ["텍스트", "파일(이미지/PDF)"], horizontal=True, key="new_test_type")

    test_text = ""
    test_files = None

    if test_type == "텍스트":
        test_text = st.text_area("셀프테스트 답안 텍스트", height=150, key="new_test_text")
    else:
        test_files = st.file_uploader("셀프테스트 답안 파일 업로드 (이미지/PDF, 다중 선택 가능)", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True, key="new_test_files")

    if st.button("신규 저장하기", type="primary", key="save_new_topic"):
        subnotes = load_data()
        if not topic:
            st.error("토픽명을 입력해 주세요.")
        elif any(item["topic"] == topic for item in subnotes):
            st.error("이미 존재하는 토픽명입니다. '토픽 조회' 탭에서 수정해 주세요.")
        else:
            subnote_file_paths = save_uploaded_files(subnote_files, "subnote", topic)
            test_file_paths = save_uploaded_files(test_files, "test", topic) if test_type == "파일(이미지/PDF)" else []

            new_record = {
                "topic": topic,
                "subject": subject,
                "importance": importance,
                "acronyms": acronyms,
                "keywords": keywords,
                "subnote_file_paths": subnote_file_paths,
                "test_text": test_text if test_type == "텍스트" else "",
                "test_file_paths": test_file_paths
            }

            subnotes.append(new_record)
            save_data(subnotes)
            st.success(f"'{topic}' 신규 저장 완료!")

# ----------------------------------------------------
# 2. 토픽 조회 및 수정 탭
# ----------------------------------------------------
with tab2:
    subnotes = load_data()

    if not subnotes:
        st.info("등록된 토픽이 없습니다.")
    else:
        if st.session_state.editing_topic is not None:
            target_topic_name = st.session_state.editing_topic
            note = next((item for item in subnotes if item["topic"] == target_topic_name), None)

            if not note:
                st.error("해당 토픽을 찾을 수 없습니다.")
                if st.button("목록으로 돌아가기"):
                    st.session_state.editing_topic = None
                    st.rerun()
            else:
                st.subheader(f"✏️ [{note['topic']}] 수정하기")

                col_e1, col_e2, col_e3 = st.columns([2, 1, 1])
                with col_e1:
                    edit_topic = st.text_input("토픽명", value=note["topic"], key="edit_topic_field")
                with col_e2:
                    subject_options = ["경영정보/IT서비스", "프로젝트 관리", "소프트웨어 공학", "데이터베이스", "네트워크", "보안", "CA/OS", "인공지능", "통계"]
                    subj_idx = subject_options.index(note["subject"]) if note["subject"] in subject_options else 0
                    edit_subject = st.selectbox("과목", subject_options, index=subj_idx, key="edit_subj_field")
                with col_e3:
                    edit_importance = st.select_slider("중요도", options=["S", "A", "B", "C"], value=note.get("importance", "A"), key="edit_imp_field")

                col_ek1, col_ek2 = st.columns([1, 2])
                with col_ek1:
                    edit_acronyms = st.text_input("두음 키워드", value=note.get("acronyms", ""), key="edit_acronyms_field")
                with col_ek2:
                    edit_keywords = st.text_input("핵심 키워드 (쉼표 구분)", value=note.get("keywords", ""), key="edit_kw_field")

                st.markdown("**서브노트 파일 변경 (이미지/PDF, 다중 선택 가능)**")
                existing_sub_paths = get_file_paths(note, "subnote_file_paths", "subnote_img_path")
                if existing_sub_paths:
                    st.caption(f"기존 파일 {len(existing_sub_paths)}개 등록됨")
                edit_subnote_files = st.file_uploader("새 서브노트 파일 업로드 (기존 파일 대체)", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True, key="edit_subnote_files_field")

                st.markdown("**셀프테스트 답안 입력 방식**")
                existing_test_paths = get_file_paths(note, "test_file_paths", "test_img_path")
                default_type_idx = 1 if (existing_test_paths and not note.get("test_text")) else 0
                edit_test_type = st.radio(
                    "입력 방식 선택",
                    ["텍스트", "파일(이미지/PDF)"],
                    index=default_type_idx,
                    horizontal=True,
                    key="edit_test_type_field"
                )

                edit_test_text = ""
                edit_test_files = None

                if edit_test_type == "텍스트":
                    edit_test_text = st.text_area("셀프테스트 답안 텍스트", value=note.get("test_text", ""), height=150, key="edit_test_text_field")
                else:
                    if existing_test_paths:
                        st.caption(f"기존 셀프테스트 파일 {len(existing_test_paths)}개 등록됨")
                    edit_test_files = st.file_uploader("새 셀프테스트 파일 업로드 (기존 파일 대체)", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True, key="edit_test_files_field")

                col_b1, col_b2 = st.columns([1, 5])
                with col_b1:
                    if st.button("수정완료", type="primary", key="save_edit_confirm"):
                        if not edit_topic:
                            st.error("토픽명을 입력해 주세요.")
                        else:
                            if edit_subnote_files:
                                subnote_file_paths = save_uploaded_files(edit_subnote_files, "subnote", edit_topic)
                            else:
                                subnote_file_paths = existing_sub_paths

                            test_text = ""
                            test_file_paths = []

                            if edit_test_type == "텍스트":
                                test_text = edit_test_text
                            else:
                                if edit_test_files:
                                    test_file_paths = save_uploaded_files(edit_test_files, "test", edit_topic)
                                else:
                                    test_file_paths = existing_test_paths

                            updated_record = {
                                "topic": edit_topic,
                                "subject": edit_subject,
                                "importance": edit_importance,
                                "acronyms": edit_acronyms,
                                "keywords": edit_keywords,
                                "subnote_file_paths": subnote_file_paths,
                                "test_text": test_text,
                                "test_file_paths": test_file_paths
                            }

                            all_subnotes = load_data()
                            for i, item in enumerate(all_subnotes):
                                if item["topic"] == note["topic"]:
                                    all_subnotes[i] = updated_record
                                    break

                            save_data(all_subnotes)
                            st.success(f"'{edit_topic}' 수정 완료!")
                            st.session_state.editing_topic = None
                            st.rerun()

                with col_b2:
                    if st.button("취소", key="cancel_edit_btn"):
                        st.session_state.editing_topic = None
                        st.rerun()

        else:
            st.subheader("서브노트 검색 및 조회")
            col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
            with col_f1:
                filter_subject = st.multiselect("과목 필터", options=list(set(item["subject"] for item in subnotes)))
            with col_f2:
                filter_importance = st.multiselect("중요도 필터", options=["S", "A", "B", "C"])
            with col_f3:
                search_query = st.text_input("검색어 (토픽명, 두음, 키워드)")

            filtered_notes = subnotes
            if filter_subject:
                filtered_notes = [n for n in filtered_notes if n["subject"] in filter_subject]
            if filter_importance:
                filtered_notes = [n for n in filtered_notes if n["importance"] in filter_importance]
            if search_query:
                sq = search_query.lower()
                filtered_notes = [
                    n for n in filtered_notes 
                    if sq in n["topic"].lower() or sq in n.get("keywords", "").lower() or sq in n.get("acronyms", "").lower()
                ]

            for idx, note in enumerate(filtered_notes):
                with st.expander(f"[{note['importance']}] {note['topic']} ({note['subject']})"):
                    col_kw, col_edit = st.columns([5, 1])
                    with col_kw:
                        acronym_str = f"`{note['acronyms']}`" if note.get("acronyms") else "미등록"
                        st.markdown(f"**🔤 두음 키워드:** {acronym_str} | **🔑 핵심 키워드:** `{note.get('keywords', '')}`")
                    with col_edit:
                        if st.button("✏️ 수정", key=f"btn_trigger_edit_{idx}", use_container_width=True):
                            st.session_state.editing_topic = note["topic"]
                            st.rerun()

                    st.divider()

                    col_i1, col_i2 = st.columns(2)
                    with col_i1:
                        st.markdown("**📄 원본 서브노트**")
                        sub_paths = get_file_paths(note, "subnote_file_paths", "subnote_img_path")
                        render_file_list(sub_paths, key_prefix=f"sub_{idx}")
                    with col_i2:
                        st.markdown("**✍️ 셀프테스트 결과**")
                        if note.get("test_text"):
                            st.info(note["test_text"])
                        test_paths = get_file_paths(note, "test_file_paths", "test_img_path")
                        if test_paths:
                            render_file_list(test_paths, key_prefix=f"test_{idx}")
                        if not note.get("test_text") and not test_paths:
                            st.caption("등록된 셀프테스트 답안 없음")

# ----------------------------------------------------
# 3. AI 평가 탭
# ----------------------------------------------------
with tab3:
    st.subheader("Gemini 기술사 평가")
    if not api_status:
        st.error("Gemini API 연동 필요: 사이드바에서 API 키를 먼저 등록해 주세요.")
    else:
        subnotes = load_data()
        if not subnotes:
            st.info("평가할 토픽이 없습니다.")
        else:
            st.markdown("##### 🔍 평가 대상 토픽 검색 및 선택")
            col_search1, col_search2, col_eval_period = st.columns([1.5, 2.5, 1.5])

            with col_search1:
                eval_subject_filter = st.selectbox(
                    "과목 필터",
                    ["전체"] + sorted(list(set(item["subject"] for item in subnotes if "subject" in item))),
                    key="eval_subj_filter"
                )

            eval_candidate_notes = subnotes
            if eval_subject_filter != "전체":
                eval_candidate_notes = [n for n in eval_candidate_notes if n.get("subject") == eval_subject_filter]

            topic_options = [n["topic"] for n in eval_candidate_notes]

            with col_search2:
                selected_eval_topic = st.selectbox(
                    "토픽 선택 (키보드로 직접 검색 가능)",
                    options=topic_options,
                    index=0 if topic_options else None,
                    key="eval_topic_select"
                )

            with col_eval_period:
                selected_period = st.selectbox(
                    "시험 교시 선택",
                    ["1교시 (용어/단답형)", "2교시 (논술형)", "3교시 (논술형)", "4교시 (논술형)"],
                    key="eval_period_select"
                )

            eval_note = next((item for item in subnotes if item["topic"] == selected_eval_topic), None) if selected_eval_topic else None

            if eval_note:
                st.markdown(f"**🔤 두음 키워드:** `{eval_note.get('acronyms', '-')}` | **🔑 핵심 키워드:** `{eval_note.get('keywords', '-')}`")
                eval_text = eval_note.get("test_text", "")
                eval_test_paths = get_file_paths(eval_note, "test_file_paths", "test_img_path")

                if st.button("AI 기술사 채점 시작", type="primary"):
                    if not eval_text and not eval_test_paths:
                        st.error("채점할 텍스트 또는 파일 답안이 없습니다.")
                    else:
                        with st.spinner("답안 파일 해석 및 AI 교시별 평가 진행 중..."):
                            try:
                                model = genai.GenerativeModel("gemini-3.6-flash")

                                if "1교시" in selected_period:
                                    period_criteria = """
                                    [1교시 용어/단답형 평가 특성]
                                    - 명확하고 즉각적인 1~2줄 핵심 정의(Definition) 제시 여부
                                    - 짧은 작성 분량(1~1.5페이지) 내 핵심 키워드 및 두음 키워드 활용도
                                    - 개념도/아키텍처 그림(Diagram)의 직관성 및 핵심 구성 요소 정리
                                    - 10분 내 집약적 기술 능력 평가
                                    """
                                else:
                                    period_criteria = f"""
                                    [{selected_period} 서술/논술형 평가 특성]
                                    - 논리적 단락 구성 (1. 개요/배경 -> 2. 상세 기술/메커니즘 -> 3. 비교/고려사항 -> 4. 기술사적 제언)
                                    - 심도 있는 기술적 논거와 실무 구현/도입 전략의 구체성
                                    - 다각도 비교 분석(표/도식) 및 문제 해결 관점의 통찰력
                                    - 기술사로서의 종합적/전략적 시각 및 차별화 포인트 평가
                                    """

                                prompt = f"""
                                당신은 대한민국 정보관리기술사 수석 채점위원입니다. 아래 제출 답안을 {selected_period} 특성에 맞춰 엄격하게 채점해 주세요.

                                [토픽 정보]
                                - 토픽명: {eval_note['topic']}
                                - 과목: {eval_note['subject']}
                                - 두음 키워드: {eval_note.get('acronyms', '없음')}
                                - 필수 키워드: {eval_note.get('keywords', '없음')}
                                - 응시 교시: {selected_period}

                                {period_criteria}

                                [제출 답안 텍스트]
                                {eval_text if eval_text else "(첨부 파일 참조)"}

                                [채점 및 평가 요구사항]
                                1. **점수**: 10점 만점 기준 (소수점 첫째자리까지 표시)
                                2. **키워드 및 두음 검증**: 두음 및 필수 키워드 누락 여부와 용어 사용의 정확성 지적
                                3. **{selected_period} 답안 특성 평가**:
                                   - 단락 구성 및 논리적 흐름
                                   - 시각화(개념도/표) 및 텍스트 구체성
                                   - 강점 및 치명적 보완점
                                4. **합격 합류를 위한 한 줄 제언**: {selected_period}에 맞는 득점 전략 조언
                                """

                                contents = [prompt]

                                for p in eval_test_paths:
                                    if os.path.exists(p):
                                        ext = os.path.splitext(p)[1].lower()
                                        if ext in [".png", ".jpg", ".jpeg"]:
                                            contents.append(Image.open(p))
                                        elif ext == ".pdf":
                                            if HAS_FITZ:
                                                pdf_images = convert_pdf_to_images(p)
                                                contents.extend(pdf_images)
                                            else:
                                                uploaded_pdf = genai.upload_file(p, mime_type="application/pdf")
                                                while uploaded_pdf.state.name == "PROCESSING":
                                                    time.sleep(2)
                                                    uploaded_pdf = genai.get_file(uploaded_pdf.name)
                                                
                                                if uploaded_pdf.state.name == "ACTIVE":
                                                    contents.append(uploaded_pdf)
                                                else:
                                                    st.error(f"PDF 파일 처리 실패: {os.path.basename(p)}")

                                response = model.generate_content(contents)
                                st.success("평가 완료!")
                                st.markdown(response.text)
                            except Exception as e:
                                st.error(f"오류 발생: {e}")
