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
    page_title="AI Quiz - Trích xuất đề trắc nghiệm",
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
    text = ""
    if name.endswith(".txt") or name.endswith(".md"):
        text = raw.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        if PdfReader is None:
            raise ValueError("Thiếu thư viện pypdf. Hãy cài requirements.txt.")
        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
    elif name.endswith(".docx"):
        if Document is None:
            raise ValueError("Thiếu thư viện python-docx. Hãy cài requirements.txt.")
        doc = Document(BytesIO(raw))
        full_text = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    full_text.append(row_text)
        text = "\n".join(full_text)
    else:
        raise ValueError("Định dạng chưa hỗ trợ. Hãy tải lên PDF, DOCX, TXT hoặc MD.")
    
    # Làm sạch khoảng trắng thừa để tiết kiệm token
    text = re.sub(r'\n\s*\n', '\n', text)
    return text

def clean_json(text):
    if not text or not text.strip():
        raise ValueError("AI trả về phản hồi trống.")
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        json_str = text[start:end + 1]
    else:
        json_str = text
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Lỗi đọc dữ liệu JSON từ AI: {e}")

def make_quiz(source_text, count, difficulty, topic, model):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Chưa có Groq API key trong code.")
    client = Groq(api_key=api_key)
    
    source_text = source_text[:35000]
    
    prompt = f"""
Tài liệu dưới đây là một ngân hàng câu hỏi trắc nghiệm. 
Nhiệm vụ của bạn là đọc và TRÍCH XUẤT chính xác **{count} câu hỏi trắc nghiệm** (có đủ 4 lựa chọn A, B, C, D) từ tài liệu này. 

QUY TẮC BẮT BUỘC:
1. Trích xuất đúng số lượng {count} câu hỏi (hoặc tối đa có thể dựa trên tài liệu nếu tài liệu ít hơn).
2. Định dạng bắt buộc: Trắc nghiệm 4 lựa chọn (A, B, C, D).
3. Về đáp án đúng (`answer`): Nếu tài liệu có chỉ định sẵn đáp án, hãy sử dụng đáp án đó. Nếu tài liệu không ghi rõ đáp án, hãy tự động phân tích nội dung câu hỏi và chọn ra đáp án đúng nhất (A, B, C hoặc D) dựa trên kiến thức chuẩn xác, không được để trống.
4. Độ khó: {difficulty}.
5. Chủ đề: {topic or 'Tự xác định theo tài liệu'}.

Chỉ trả về JSON hợp lệ, đúng cấu trúc sau:
{{
  "title": "Đề trắc nghiệm trích xuất từ tài liệu",
  "questions": [
    {{
      "question": "Nội dung câu hỏi trắc nghiệm",
      "options": {{"A":"...", "B":"...", "C":"...", "D":"..."}},
      "answer": "A",
      "explanation": "Giải thích ngắn gọn cho đáp án"
    }}
  ]
}}

TÀI LIỆU:
---
{source_text}
---
"""
    dynamic_max_tokens = min(8192, int(count) * 160 + 1000)
    
    result = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia trích xuất đề thi. Hãy lấy chính xác các câu hỏi trắc nghiệm, tự điền đáp án chuẩn xác nếu file chưa có, và trả về JSON chuẩn."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=dynamic_max_tokens,
        response_format={"type": "json_object"},
    )
    raw_content = result.choices[0].message.content or ""
    data = clean_json(raw_content)
    
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("AI không trích xuất được câu hỏi nào từ tài liệu.")
    
    valid = []
    for q in questions:
        question_text = q.get("question")
        opts = q.get("options", {})
        answer = str(q.get("answer", "")).strip().upper()
        explanation = str(q.get("explanation", ""))
        
        if question_text and all(k in opts for k in ("A", "B", "C", "D")) and answer in ("A", "B", "C", "D"):
            valid.append({
                "question": str(question_text),
                "options": {k: str(opts[k]) for k in ("A", "B", "C", "D")},
                "answer": answer,
                "explanation": explanation
            })
            
    if not valid:
        raise ValueError("Dữ liệu câu hỏi AI trả về không đúng định dạng yêu cầu.")
    return {"title": str(data.get("title", "Đề trắc nghiệm AI")), "questions": valid}

def check_answer(q, chosen):
    if chosen is None:
        return False
    return str(chosen).strip().upper() == str(q["answer"]).strip().upper()

st.markdown("""
<div class="hero">
  <h1>🧠 AI Trích Xuất Đề Trắc Nghiệm</h1>
  <div>Hệ thống quét, lấy trọn vẹn câu hỏi và tự động gán đáp án chính xác từ file của bạn</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Cài đặt đề")
    question_count = st.number_input("Số lượng câu hỏi muốn lấy", min_value=5, max_value=150, value=30, step=5)
    difficulty = st.selectbox("Độ khó", ["Giữ nguyên như tài liệu", "Cơ bản", "Trung bình", "Nâng cao"])
    topic = st.text_input("Chủ đề (không bắt buộc)", placeholder="Ví dụ: Bài 1 - 4")
    model = st.text_input("Groq model", value=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    st.info("💡 **Mẹo:** Nếu file của bạn chưa có sẵn đáp án, AI sẽ tự động phân tích và tìm ra đáp án đúng nhất cho từng câu.")

tab_create, tab_quiz, tab_history = st.tabs(["📚 Tạo đề", "✍️ Làm bài", "📊 Lịch sử phiên"])

with tab_create:
    st.subheader("Trích xuất đề từ tài liệu có sẵn")
    st.write("Tải lên file Word/PDF chứa bộ câu hỏi. Hệ thống sẽ quét, trích xuất đúng số lượng câu và xác định đáp án.")
    uploaded = st.file_uploader("Chọn tài liệu", type=["pdf", "docx", "txt", "md"])
    pasted = st.text_area("Hoặc dán nội dung tài liệu vào đây", height=180, placeholder="Dán nội dung câu hỏi...")
    
    if st.button("✨ Tiến hành trích xuất đề", type="primary", use_container_width=True):
        try:
            source = pasted.strip()
            if uploaded is not None:
                extracted = extract_text(uploaded).strip()
                if extracted:
                    source = (source + "\n\n" + extracted).strip() if source else extracted
            if len(source) < 50:
                st.error("Tài liệu quá ngắn. Hãy tải file hoặc dán ít nhất vài đoạn nội dung.")
            else:
                with st.spinner(f"AI đang quét file và trích xuất {int(question_count)} câu hỏi trắc nghiệm..."):
                    quiz = make_quiz(source, int(question_count), difficulty, topic, model.strip())
                st.session_state.quiz = quiz
                st.session_state.answers = {}
                st.session_state.submitted = False
                st.success(f"Đã trích xuất thành công {len(quiz['questions'])} câu hỏi trắc nghiệm! Mở tab “Làm bài” để bắt đầu.")
        except Exception as exc:
            st.error(f"Không trích xuất được đề: {exc}")
            st.info("Kiểm tra lại kết nối mạng, API key hoặc định dạng file tài liệu.")

with tab_quiz:
    quiz = st.session_state.quiz
    if not quiz:
        st.info("Chưa có đề. Sang tab “Tạo đề” để tải tài liệu và tạo đề trước.")
    else:
        st.subheader(quiz["title"])
        st.caption(f"{len(quiz['questions'])} câu hỏi trắc nghiệm · Hoàn thành các câu hỏi bên dưới và bấm Nộp bài.")
        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Câu {i + 1}.** {q['question']}")
                current = st.session_state.answers.get(str(i), None)
                
                opts_list = ["A", "B", "C", "D"]
                default_idx = opts_list.index(current) if current in opts_list else 0
                
                choice = st.radio(
                    f"Chọn đáp án câu {i + 1}",
                    options=opts_list,
                    format_func=lambda key, opts=q["options"]: f"{key}. {opts[key]}",
                    index=default_idx,
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
                if check_answer(q, st.session_state.answers.get(str(i)))
            )
            score = round(correct / len(quiz["questions"]) * 10, 2)
            st.session_state.history.insert(0, {
                "title": quiz["title"], "correct": correct,
                "total": len(quiz["questions"]), "score": score
            })
            
        if st.session_state.submitted:
            correct = sum(
                1 for i, q in enumerate(quiz["questions"])
                if check_answer(q, st.session_state.answers.get(str(i)))
            )
            total = len(quiz["questions"])
            st.success(f"Kết quả: {correct}/{total} câu đúng — {correct / total * 10:.2f}/10 điểm")
            
            for i, q in enumerate(quiz["questions"]):
                chosen = st.session_state.answers.get(str(i), "Chưa chọn")
                is_correct = check_answer(q, chosen)
                
                st.markdown(f"**Câu {i + 1}:** {'✅ Đúng' if is_correct else '❌ Sai'}")
                st.write(f"Đáp án của bạn: {chosen}")
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

st.caption("Lưu ý: Hệ thống trích xuất hoàn toàn bám sát các câu hỏi trắc nghiệm có sẵn trong tài liệu.")
