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

def make_quiz(source_text, count, difficulty, topic, model, question_types):
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "Chưa có Groq API key. Hãy thêm GROQ_API_KEY trong "
            "Streamlit → Settings → Secrets."
        )
    client = Groq(api_key=api_key)
    source_text = source_text[:40000]
    
    types_desc = ", ".join(question_types)
    prompt = f"""
Bạn là giáo viên tạo đề kiểm tra bằng tiếng Việt.
QUY TẮC BẮT BUỘC: 100% câu hỏi, đáp án và thông tin phải được lấy TRỰC TIẾP và HOÀN TOÀN từ phần "TÀI LIỆU" được cung cấp bên dưới. 
- Tuyệt đối KHÔNG được tự bịa đặt thông tin.
- Tuyệt đối KHÔNG được dùng kiến thức bên ngoài tài liệu.
- Mọi dữ liệu phải tuân thủ đúng nội dung tài liệu, không thêm bớt hoặc suy diễn sai lệch ý nghĩa của tài liệu gốc.

Hãy tạo đúng {count} câu hỏi dựa trên tài liệu trên.
Các định dạng câu hỏi được phép sử dụng: {types_desc}. Hãy phân bổ đều các định dạng được chọn nếu có thể.
Chủ đề bổ sung: {topic or 'Tự xác định theo tài liệu'}.
Độ khó: {difficulty}.
Chỉ trả về JSON hợp lệ, không Markdown, theo cấu trúc sau:
{{
  "title": "Tên đề",
  "questions": [
    {{
      "type": "multiple_choice",
      "question": "Nội dung câu hỏi trắc nghiệm lấy sát tài liệu",
      "options": {{"A":"...", "B":"...", "C":"...", "D":"..."}},
      "answer": "A",
      "explanation": "Giải thích ngắn gọn dựa hoàn toàn trên tài liệu"
    }},
    {{
      "type": "true_false",
      "question": "Nội dung câu hỏi đúng sai lấy sát tài liệu",
      "options": {{"Đúng": "Đúng", "Sai": "Sai"}},
      "answer": "Đúng",
      "explanation": "Giải thích ngắn gọn dựa hoàn toàn trên tài liệu"
    }},
    {{
      "type": "short_answer",
      "question": "Nội dung câu hỏi trả lời ngắn lấy sát tài liệu",
      "answer": "Từ khóa chính xác có trong tài liệu",
      "explanation": "Giải thích ngắn gọn dựa hoàn toàn trên tài liệu"
    }}
  ]
}}
Quy tắc bổ sung:
- Chỉ sử dụng các định dạng thuộc danh sách: {types_desc}.
- multiple_choice bắt buộc có đủ 4 lựa chọn, đáp án đúng phải căn cứ chính xác vào tài liệu.
- true_false có options Đúng/Sai dựa hoàn toàn vào dữ liệu tài liệu.
- short_answer có đáp án là từ khóa/cụm từ chuẩn xác xuất hiện trong tài liệu.
- Không lặp câu hỏi.
TÀI LIỆU:
---
{source_text}
---
"""
    result = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Bạn tạo câu hỏi kiểm tra chính xác bám sát 100% tài liệu và chỉ xuất JSON hợp lệ."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=8192,
    )
    data = clean_json(result.choices[0].message.content or "")
    questions = data.get("questions", [])
    if not questions:
        raise ValueError("AI không trả về câu hỏi. Hãy thử lại với tài liệu khác.")
    
    valid = []
    for q in questions:
        q_type = q.get("type", "multiple_choice")
        question_text = q.get("question")
        answer = str(q.get("answer", "")).strip()
        explanation = str(q.get("explanation", ""))
        
        if not question_text or not answer:
            continue
            
        if q_type == "multiple_choice":
            opts = q.get("options", {})
            ans_upper = answer.upper()
            if all(k in opts for k in ("A", "B", "C", "D")) and ans_upper in ("A", "B", "C", "D"):
                valid.append({
                    "type": "multiple_choice",
                    "question": str(question_text),
                    "options": {k: str(opts[k]) for k in ("A", "B", "C", "D")},
                    "answer": ans_upper,
                    "explanation": explanation
                })
        elif q_type == "true_false":
            ans_norm = "Đúng" if answer.lower() in ["đúng", "true", "t", "1", "yes"] else "Sai" if answer.lower() in ["sai", "false", "f", "0", "no"] else answer
            if ans_norm in ("Đúng", "Sai"):
                valid.append({
                    "type": "true_false",
                    "question": str(question_text),
                    "options": {"Đúng": "Đúng", "Sai": "Sai"},
                    "answer": ans_norm,
                    "explanation": explanation
                })
        elif q_type == "short_answer":
            valid.append({
                "type": "short_answer",
                "question": str(question_text),
                "answer": answer,
                "explanation": explanation
            })
            
    if not valid:
        raise ValueError("Dữ liệu câu hỏi AI trả về không đúng định dạng. Hãy bấm tạo đề lại.")
    return {"title": str(data.get("title", "Đề kiểm tra AI")), "questions": valid}

def check_answer(q, chosen):
    if chosen is None:
        return False
    q_type = q.get("type", "multiple_choice")
    if q_type in ("multiple_choice", "true_false"):
        return str(chosen).strip().upper() == str(q["answer"]).strip().upper()
    elif q_type == "short_answer":
        return str(chosen).strip().lower() == str(q["answer"]).strip().lower()
    return False

st.markdown("""
<div class="hero">
  <h1>🧠 AI Quiz Pro</h1>
  <div>Tạo đề kiểm tra 100% bám sát tài liệu bằng Groq AI</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Cài đặt đề")
    question_count = st.number_input("Số câu hỏi", min_value=1, max_value=200, value=20, step=5)
    difficulty = st.selectbox("Độ khó", ["Cơ bản", "Trung bình", "Nâng cao", "Hỗn hợp"])
    
    st.markdown("### Định dạng câu hỏi")
    q_type_mc = st.checkbox("Trắc nghiệm (4 lựa chọn)", value=True)
    q_type_tf = st.checkbox("Đúng / Sai", value=True)
    q_type_sa = st.checkbox("Trả lời ngắn", value=True)
    
    topic = st.text_input("Chủ đề (không bắt buộc)", placeholder="Ví dụ: Chương 1 - Lịch sử")
    model = st.text_input("Groq model", value=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    st.caption("API key chỉ đặt trong Secrets, không ghi trực tiếp vào code.")

tab_create, tab_quiz, tab_history = st.tabs(["📚 Tạo đề", "✍️ Làm bài", "📊 Lịch sử phiên"])

with tab_create:
    st.subheader("Tạo đề từ tài liệu")
    st.write("Tải lên PDF, DOCX, TXT hoặc MD. Hệ thống sẽ giới hạn tạo câu hỏi **100% chính xác theo văn bản tài liệu**.")
    uploaded = st.file_uploader("Chọn tài liệu", type=["pdf", "docx", "txt", "md"])
    pasted = st.text_area("Hoặc dán nội dung tài liệu vào đây", height=180, placeholder="Dán nội dung bài học...")
    
    if st.button("✨ Tạo đề bằng AI", type="primary", use_container_width=True):
        selected_types = []
        if q_type_mc: selected_types.append("Trắc nghiệm")
        if q_type_tf: selected_types.append("Đúng/Sai")
        if q_type_sa: selected_types.append("Trả lời ngắn")
        
        if not selected_types:
            st.error("Vui lòng chọn ít nhất một định dạng câu hỏi ở thanh bên trái.")
        else:
            try:
                source = pasted.strip()
                if uploaded is not None:
                    extracted = extract_text(uploaded).strip()
                    if extracted:
                        source = (source + "\n\n" + extracted).strip() if source else extracted
                if len(source) < 50:
                    st.error("Tài liệu quá ngắn. Hãy tải file hoặc dán ít nhất vài đoạn nội dung.")
                else:
                    with st.spinner("Groq AI đang đọc kỹ tài liệu và trích xuất câu hỏi..."):
                        quiz = make_quiz(source, int(question_count), difficulty, topic, model.strip(), selected_types)
                    st.session_state.quiz = quiz
                    st.session_state.answers = {}
                    st.session_state.submitted = False
                    st.success(f"Đã tạo thành công {len(quiz['questions'])} câu hỏi sát tài liệu. Mở tab “Làm bài” để bắt đầu.")
            except Exception as exc:
                st.error(f"Không tạo được đề: {exc}")
                st.info("Kiểm tra API key, tên model, kết nối mạng và nội dung file.")

with tab_quiz:
    quiz = st.session_state.quiz
    if not quiz:
        st.info("Chưa có đề. Sang tab “Tạo đề” để tải tài liệu và tạo đề trước.")
    else:
        st.subheader(quiz["title"])
        st.caption(f"{len(quiz['questions'])} câu hỏi · Hoàn thành các câu hỏi bên dưới và bấm Nộp bài.")
        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                q_type = q.get("type", "multiple_choice")
                type_label = "Trắc nghiệm" if q_type == "multiple_choice" else "Đúng/Sai" if q_type == "true_false" else "Trả lời ngắn"
                
                st.markdown(f"**Câu {i + 1}** *({type_label})*: {q['question']}")
                current = st.session_state.answers.get(str(i), None)
                
                if q_type == "multiple_choice":
                    choice = st.radio(
                        f"Chọn đáp án câu {i + 1}",
                        options=["A", "B", "C", "D"],
                        format_func=lambda key, opts=q["options"]: f"{key}. {opts[key]}",
                        index=["A", "B", "C", "D"].index(current) if current in ["A", "B", "C", "D"] else None,
                        key=f"answer_{i}",
                        label_visibility="collapsed",
                    )
                    st.session_state.answers[str(i)] = choice
                elif q_type == "true_false":
                    choice = st.radio(
                        f"Chọn đáp án câu {i + 1}",
                        options=["Đúng", "Sai"],
                        index=["Đúng", "Sai"].index(current) if current in ["Đúng", "Sai"] else None,
                        key=f"answer_{i}",
                        label_visibility="collapsed",
                    )
                    st.session_state.answers[str(i)] = choice
                elif q_type == "short_answer":
                    choice = st.text_input(
                        f"Nhập câu trả lời cho câu {i + 1}",
                        value=current if current is not None else "",
                        key=f"answer_{i}",
                        placeholder="Nhập câu trả lời ngắn...",
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
                chosen = st.session_state.answers.get(str(i), "Chưa trả lời")
                is_correct = check_answer(q, chosen)
                q_type = q.get("type", "multiple_choice")
                
                st.markdown(f"**Câu {i + 1}:** {'✅ Đúng' if is_correct else '❌ Sai'}")
                st.write(f"Câu trả lời của bạn: {chosen}")
                
                if q_type == "multiple_choice":
                    st.write(f"Đáp án đúng: {q['answer']}. {q['options'][q['answer']]}")
                elif q_type == "true_false":
                    st.write(f"Đáp án đúng: {q['answer']}")
                elif q_type == "short_answer":
                    st.write(f"Đáp án chuẩn: {q['answer']}")
                    
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

st.caption("Lưu ý: Đề kiểm tra được hệ thống trích xuất và bám sát hoàn toàn theo dữ liệu từ file tài liệu của bạn.")
