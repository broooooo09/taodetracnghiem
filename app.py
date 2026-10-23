import streamlit as st
from groq import Groq
import json
import docx
from pypdf import PdfReader

# Cấu hình giao diện trang web
st.set_page_config(page_title="Hệ Thống Trắc Nghiệm AI", layout="wide")

st.title("📚 Trợ Lý AI Chuyển Đổi Đề Trắc Nghiệm")
st.write("Tải lên đề thi (Word, PDF, TXT) để tự động hóa giao diện làm bài trực tuyến.")

# Tích hợp sẵn API Key
API_KEY = "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"

def extract_text_from_file(uploaded_file):
    filename = uploaded_file.name.lower()
    content = ""
    try:
        if filename.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            content = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        elif filename.endswith(".pdf"):
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        elif filename.endswith(".txt"):
            content = uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
    return content

def call_groq_ai(text_content):
    client = Groq(api_key=API_KEY)
    
    json_structure_example = """[
      {
        "id": 1,
        "question": "Nội dung câu hỏi?",
        "options": {
          "A": "Đáp án A",
          "B": "Đáp án B",
          "C": "Đáp án C",
          "D": "Đáp án D"
        },
        "answer": "A"
      }
    ]"""

    prompt = f"""
    Bạn là một chuyên gia khảo thí giáo dục. Hãy đọc kỹ nội dung đề thi bên dưới, trích xuất toàn bộ các câu hỏi trắc nghiệm.
    Kết quả trả về PHẢI LÀ MỘT MẢNG JSON (JSON array) thuần túy tuân thủ chính xác cấu trúc mẫu sau, tuyệt đối không kèm theo bất kỳ văn bản chào hỏi hay giải thích nào khác ngoài JSON:
    {json_structure_example}

    Nội dung đề thi cần xử lý:
    {text_content}
    """

    # Danh sách các model chuẩn hiện tại của Groq để tự động chuyển đổi nếu cần
    models = ["llama-3.1-8b-instant", "llama3-70b-8192"]
    
    for model_name in models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            ]
            response_content = completion.choices[0].message.content.strip()
            
            # Làm sạch chuỗi markdown JSON nếu AI vô tình trả về
            if response_content.startswith("```json"):
                response_content = response_content[7:]
            if response_content.endswith("```"):
                response_content = response_content[:-3]
                
            data = json.loads(response_content.strip())
            if isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, list):
                        return val
            if isinstance(data, list):
                return data
        except Exception:
            continue
            
    raise Exception("Không thể trích xuất dữ liệu từ AI. Vui lòng kiểm tra lại nội dung file.")

# Giao diện chính tải file
uploaded_file = st.file_uploader("Chọn file đề thi của bạn", type=["docx", "pdf", "txt"])

if uploaded_file is not None:
    st.success(f"Đã nhận file: {uploaded_file.name}")
    
    if st.button("🚀 Phân tích và tạo đề thi"):
        with st.spinner("Hệ thống đang trích xuất câu hỏi bằng AI..."):
            extracted_text = extract_text_from_file(uploaded_file)
            
            if extracted_text.strip() == "":
                st.warning("File không có nội dung hoặc không đọc được văn bản.")
            else:
                try:
                    quiz_items = call_groq_ai(extracted_text)
                    st.session_state["quiz_data"] = quiz_items
                    st.success("Tạo đề thi thành công!")
                except Exception as err:
                    st.error(f"Đã xảy ra lỗi: {err}")

# Giao diện thi trực tuyến giống Azota
if "quiz_data" in st.session_state:
    st.markdown("---")
    st.subheader("📝 Giao diện làm bài trực tuyến")
    
    user_selections = {}
    with st.form("exam_form"):
        for index, item in enumerate(st.session_state["quiz_data"]):
            q_id = item.get('id', index + 1)
            q_title = item.get('question', '')
            options = item.get('options', {})
            
            st.markdown(f"**Câu {q_id}: {q_title}**")
            
            choice_list = [
                f"A. {options.get('A', '')}",
                f"B. {options.get('B', '')}",
                f"C. {options.get('C', '')}",
                f"D. {options.get('D', '')}"
            ]
            
            selected_option = st.radio(
                f"Chọn đáp án câu {q_id}",
                choice_list,
                key=f"question_{q_id}",
                label_visibility="collapsed"
            )
            
            # Lấy ký tự đầu tiên (A, B, C, D) làm đáp án người dùng chọn
            user_selections[q_id] = selected_option[0] if selected_option else ""
            st.write("")

        submitted_exam = st.form_submit_button("Nộp bài")
        if submitted_exam:
            total_score = 0
            total_questions = len(st.session_state["quiz_data"])
            
            for item in st.session_state["quiz_data"]:
                q_id = item.get('id')
                correct_ans = str(item.get('answer', '')).strip().upper()
                if user_selections.get(q_id) == correct_ans:
                    total_score += 1
                    
            st.balloons()
            st.metric(label="Kết quả bài làm", value=f"{total_score} / {total_questions} câu đúng")
