import streamlit as st
from groq import Groq
import json
import docx
from pypdf import PdfReader

# Cấu hình trang web
st.set_page_config(page_title="AI Tạo Đề Trắc Nghiệm Đa Định Dạng", layout="wide")

st.title("📚 Trợ Lý AI Chuyển Đổi Đề Trắc Nghiệm (All-in-One)")
st.write("Hỗ trợ tải lên mọi loại file đề thi: Word (.docx), PDF, Văn bản (.txt).")

# Tích hợp sẵn Groq API Key của bạn
api_key = "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"

try:
    client = Groq(api_key=api_key)

    # Cho phép chọn định dạng file
    uploaded_file = st.file_uploader("Chọn file đề thi", type=["docx", "pdf", "txt"])

    if uploaded_file is not None:
        st.success(f"Đã tải lên: {uploaded_file.name}")
        
        if st.button("🚀 Xử lý và tạo đề trắc nghiệm"):
            with st.spinner("AI đang đọc và phân tích nội dung tài liệu..."):
                try:
                    file_extension = uploaded_file.name.split('.')[-1].lower()
                    file_content = ""

                    # Trích xuất nội dung từ các định dạng file
                    if file_extension == "docx":
                        doc = docx.Document(uploaded_file)
                        file_content = "\n".join([p.text for p in doc.paragraphs])
                    elif file_extension == "pdf":
                        reader = PdfReader(uploaded_file)
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                file_content += text + "\n"
                    elif file_extension == "txt":
                        file_content = uploaded_file.getvalue().decode("utf-8")

                    json_example = """[
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

                    prompt = (
                        "Hãy đọc kỹ nội dung đề thi trắc nghiệm dưới đây. "
                        "Trích xuất toàn bộ các câu hỏi trắc nghiệm và trả về kết quả DUY NHẤT dưới dạng một mảng JSON (JSON array) "
                        "với cấu trúc chuẩn như mẫu sau, không kèm theo văn bản giải thích nào khác:\n"
                        + json_example + "\n\n"
                        "(Lưu ý: Trường \"answer\" là đáp án đúng nếu có trong đề, nếu không có hãy để trống hoặc đoán dựa trên nội dung).\n\n"
                        "Nội dung đề thi:\n" + file_content
                    )

                    # Sử dụng mô hình chuẩn mới nhất llama-3.1-8b-instant của Groq
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Bạn là chuyên gia trích xuất dữ liệu đề thi sang định dạng JSON chính xác."},
                            {"role": "user", "content": prompt}
                        ],
                        model="llama-3.1-8b-instant",
                    )
                    response_text = chat_completion.choices[0].message.content.strip()

                    # Xử lý chuỗi JSON kết quả
                    if response_text.startswith("```json"):
                        response_text = response_text[7:]
                    if response_text.endswith("```"):
                        response_text = response_text[:-3]

                    parsed_data = json.loads(response_text.strip())
                    if isinstance(parsed_data, dict):
                        for key, val in parsed_data.items():
                            if isinstance(val, list):
                                parsed_data = val
                                break

                    st.session_state["quiz_data"] = parsed_data
                    st.success("Đã xử lý thành công!")

                except Exception as e:
                    st.error(f"Đã có lỗi xảy ra khi xử lý file: {e}")

    # Hiển thị giao diện bài thi kiểu Azota
    if "quiz_data" in st.session_state:
        st.markdown("---")
        st.subheader("📝 Giao diện xem trước đề thi (Giống Azota)")
        
        user_answers = {}
        with st.form("quiz_form"):
            for item in st.session_state["quiz_data"]:
                q_id = item.get('id', 1)
                q_text = item.get('question', '')
                options_dict = item.get('options', {})
                
                st.markdown(f"**Câu {q_id}: {q_text}**")
                options_list = [
                    f"A. {options_dict.get('A', '')}", 
                    f"B. {options_dict.get('B', '')}", 
                    f"C. {options_dict.get('C', '')}", 
                    f"D. {options_dict.get('D', '')}"
                ]
                
                choice = st.radio(
                    f"Chọn đáp án câu {q_id}", 
                    options_list, 
                    key=f"q_{q_id}",
                    label_visibility="collapsed"
                )
                user_answers[q_id] = choice[0] if choice else ""
                st.write("")

            submitted = st.form_submit_button("Nộp bài")
            if submitted:
                score = 0
                total = len(st.session_state["quiz_data"])
                for item in st.session_state["quiz_data"]:
                    q_id = item.get('id', 1)
                    if user_answers.get(q_id) == item.get('answer'):
                        score += 1
                st.balloons()
                st.metric(label="Kết quả của bạn", value=f"{score}/{total}")

except Exception as e:
    st.error(f"Lỗi khởi tạo hệ thống: {e}")
