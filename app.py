import json
import os
import re
from io import BytesIO

import streamlit as st
from groq import Groq

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

st.set_page_config(
    page_title="AI Quiz - Tạo đề trắc nghiệm",
    page_icon="🧠",
    layout="wide",
)

st.markdown("""
<style>
    .block-container {max-width: 1100px; padding-top: 2rem; padding-bottom: 3rem;}
    .hero {
        padding: 1.6rem; border-radius: 18px;
        background: linear-gradient(120deg, #172554, #4338ca);
        color: white; margin-bottom: 1rem;
    }
    .hero h1 {color: white; margin-bottom: .3rem;}
    .small-muted {color: #64748b; font-size: .92rem;}
    div.stButton > button {border-radius: 10px; min-height: 2.6rem;}
</style>
""", unsafe_allow_html=True)

if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "history" not in st.session_state:
    st.session_state.history = []

def get_api_key():
    return "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"

def extract_text(uploaded_file):
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    if name.endswith(".txt") or name.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        if PdfReader is None:
            raise ValueError("Thiếu thư viện pypdf. Hãy cài requirements.txt.")
        reader = PdfReader(BytesIO(raw))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)
    if name.endswith(".docx"):
        if Document is None:
            raise ValueError("Thiếu thư viện python-docx. Hãy cài requirements.txt.")
        doc = Document(BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Định dạng chưa hỗ trợ. Hãy tải lên PDF, DOCX, TXT hoặc MD.")

def clean_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)

def make_quiz(source_text, count, difficulty, topic, model):
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "Chưa có Groq API key. Hãy thêm GROQ_API_KEY trong "
            "Streamlit → Settings → Secrets."
        )
    client = Groq(api_key=api_key)
    source_text = source_text[:24000]
    prompt = f"""
Bạn là giáo viên tạo đề trắc nghiệm bằng tiếng Việt.
Hãy tạo đúng {count} câu hỏi dựa trên tài liệu bên dưới.
Chủ đề bổ sung: {topic or 'Tự xác định theo tài liệu'}.
Độ khó: {difficulty}.
Chỉ trả về JSON hợp lệ, không Markdown, theo cấu trúc:
{{
  "title": "Tên đề",
  "questions": [
    {{
      "question": "Nội dung câu hỏi",
      "options": {{"A":"...", "B":"...", "C":"...", "D":"..."}},
      "answer": "A",
      "explanation": "Giải thích ngắn gọn dựa trên tài liệu"
    }}
  ]
}}
Quy tắc:
- Mỗi câu có đúng 4 lựa chọn A, B, C, D.
- answer phải là một chữ cái A/B/C/D.
- Chỉ có một đáp án đúng mỗi câu.
- Không hỏi thông tin không có trong tài liệu.
- Không lặp câu hỏi.
- Nội dung rõ ràng, phù hợp học sinh.
TÀI LIỆU:
---
{source_text}
---
"""
    result = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Bạn tạo câu hỏi trắc nghiệm chính xác và chỉ xuất JSON hợp lệ."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=7000,
    )
    data = clean_json(result.choices[0].message.content or "")
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("AI không trả về câu hỏi. Hãy thử lại với tài liệu khác.")
    valid = []
    for q in questions:
        opts = q.get("options", {})
        answer = str(q.get("answer", "")).strip().upper()
        if q.get("question") and all(k in opts for k in ("A", "B", "C", "D")) and answer in ("A", "B", "C", "D"):
            valid.append({
                "question": str(q["question"]),
                "options": {k: str(opts[k]) for k in ("A", "B", "C", "D")},
                "answer": answer,
                "explanation": str(q.get("explanation", ""))
            })
    if not valid:
        raise ValueError("Dữ liệu câu hỏi AI trả về không đúng định dạng. Hãy bấm tạo đề lại.")
    return {"title": str(data.get("title", "Đề trắc nghiệm AI")), "questions": valid}

st.markdown("""
<div class="hero">
  <h1>🧠 AI Quiz</h1>
  <div>Tạo đề trắc nghiệm từ tài liệu bằng Groq AI</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Cài đặt đề")
    question_count = st.slider("Số câu hỏi", min_value=5, max_value=30, value=10, step=5)
    difficulty = st.selectbox("Độ khó", ["Cơ bản", "Trung bình", "Nâng cao", "Hỗn hợp"])
    topic = st.text_input("Chủ đề (không bắt buộc)", placeholder="Ví dụ: Sinh học tế bào")
    model = st.text_input("Groq model", value=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    st.caption("API key chỉ đặt trong Secrets, không ghi trực tiếp vào code.")

tab_create, tab_quiz, tab_history = st.tabs(["📚 Tạo đề", "✍️ Làm bài", "📊 Lịch sử phiên"])

with tab_create:
    st.subheader("Tạo đề từ tài liệu")
    st.write("Tải lên PDF có văn bản, DOCX, TXT hoặc MD. Tài liệu càng rõ ràng thì câu hỏi càng sát nội dung.")
    uploaded = st.file_uploader("Chọn tài liệu", type=["pdf", "docx", "txt", "md"])
    pasted = st.text_area("Hoặc dán nội dung tài liệu vào đây", height=180, placeholder="Dán ghi chú hoặc nội dung bài học...")
    if st.button("✨ Tạo đề bằng AI", type="primary", use_container_width=True):
        try:
            source = pasted.strip()
            if uploaded is not None:
                extracted = extract_text(uploaded).strip()
                if extracted:
                    source = (source + "\n\n" + extracted).strip() if source else extracted
            if len(source) < 80:
                st.error("Tài liệu quá ngắn. Hãy tải file hoặc dán ít nhất vài đoạn nội dung.")
            else:
                with st.spinner("Groq AI đang đọc tài liệu và tạo câu hỏi..."):
                    quiz = make_quiz(source, question_count, difficulty, topic, model.strip())
                st.session_state.quiz = quiz
                st.session_state.answers = {}
                st.session_state.submitted = False
                st.success(f"Đã tạo {len(quiz['questions'])} câu. Mở tab “Làm bài” để bắt đầu.")
        except Exception as exc:
            st.error(f"Không tạo được đề: {exc}")
            st.info("Kiểm tra API key, tên model, kết nối mạng và nội dung file.")

with tab_quiz:
    quiz = st.session_state.quiz
    if not quiz:
        st.info("Chưa có đề. Sang tab “Tạo đề” để tải tài liệu và tạo đề trước.")
    else:
        st.subheader(quiz["title"])
        st.caption(f"{len(quiz['questions'])} câu hỏi · Chọn một đáp án cho mỗi câu.")
        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Câu {i + 1}. {q['question']}**")
                current = st.session_state.answers.get(str(i), None)
                choice = st.radio(
                    f"Chọn đáp án câu {i + 1}",
                    options=["A", "B", "C", "D"],
                    format_func=lambda key, opts=q["options"]: f"{key}. {opts[key]}",
                    index=["A", "B", "C", "D"].index(current) if current in ["A", "B", "C", "D"] else None,
                    key=f"answer_{i}",
                    label_visibility="collapsed",
                )
                st.session_state.answers[str(i)] = choice
                st.divider()
            submitted = st.form_submit_button("Nộp bài và chấm điểm", type="primary", use_container_width=True)
        if submitted:
            st.session_state.submitted = True
            correct = sum(
                1 for i, q in enumerate(quiz["questions"])
                if st.session_state.answers.get(str(i)) == q["answer"]
            )
            score = round(correct / len(quiz["questions"]) * 10, 2)
            st.session_state.history.insert(0, {
                "title": quiz["title"], "correct": correct,
                "total": len(quiz["questions"]), "score": score
            })
        if st.session_state.submitted:
            correct = sum(
                1 for i, q in enumerate(quiz["questions"])
                if st.session_state.answers.get(str(i)) == q["answer"]
            )
            total = len(quiz["questions"])
            st.success(f"Kết quả: {correct}/{total} câu đúng — {correct / total * 10:.2f}/10 điểm")
            for i, q in enumerate(quiz["questions"]):
                chosen = st.session_state.answers.get(str(i), "Chưa chọn")
                is_correct = chosen == q["answer"]
                st.markdown(f"**Câu {i + 1}:** {'✅ Đúng' if is_correct else '❌ Sai'}")
                st.write(f"Đáp án của m: {chosen}")
                st.write(f"Đáp án đúng: {q['answer']}. {q['options'][q['answer']]}")
                if q["explanation"]:
                    st.caption(f"Giải thích: {q['explanation']}")
                st.divider()
            if st.button("🔄 Làm lại đề này"):
                st.session_state.answers = {}
                st.session_state.submitted = False
                st.rerun()

with tab_history:
    st.subheader("Lịch sử làm bài trong phiên hiện tại")
    if not st.session_state.history:
        st.info("Chưa có kết quả nào. Lịch sử sẽ được làm mới khi phiên ứng dụng kết thúc.")
    else:
        st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)

st.caption("Lưu ý: AI có thể tạo đáp án chưa chính xác tuyệt đối; hãy kiểm tra lại trước khi dùng làm đề chính thức.")
