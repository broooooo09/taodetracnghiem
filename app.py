import streamlit as st
import google.generativeai as genai
import json
import docx

# Cấu hình trang web
st.set_page_config(page_title="AI Tạo Đề Trắc Nghiệm kiểu Azota", layout="wide")

st.title("📚 Trợ Lý AI Chuyển Đổi Đề Trắc Nghiệm")
st.write("Tải lên file đề thi Word (.docx) để AI tự động chuyển thành định dạng trắc nghiệm trực tuyến.")

# API Key của bạn
api_key = "AQ.Ab8RN6Ll0xWNHUjSJGX6iYevM-hIK7k3Hp97XJBJ_n_fMntKbw"

try:
    genai.configure(api_key=api_key)
    # Sử dụng model flash chuẩn
    model = genai.GenerativeModel("gemini-2.5-flash")

    uploaded_file = st.file_uploader("Chọn file đề thi Word", type=["docx"])

    if uploaded_file is not None:
        st.success(f"Đã tải lên: {uploaded_file.name}")
        
        if st.button("🚀 Xử lý và tạo đề trắc nghiệm"):
            with st.spinner("AI đang đọc nội dung và phân tích câu hỏi..."):
                try:
                    # Đọc trực tiếp nội dung văn bản từ file Word
                    doc = docx.Document(uploaded_file)
                    file_content = "\n".join([paragraph.text for paragraph in doc.paragraphs])

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

                    response = model.generate_content(prompt)

                    # Xử lý chuỗi JSON kết quả
                    json_text = response.text.strip()
                    if json_text.startswith("```json"):
                        json_text = json_text[7:]
                    if json_text.endswith("```"):
                        json_text = json_text[:-3]

                    quiz_data = json.loads(json_text.strip())
                    st.session_state["quiz_data"] = quiz_data
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
                st.markdown(f"**Câu {item['id']}: {item['question']}**")
                options_list = [
                    f"A. {item['options'].get('A', '')}", 
                    f"B. {item['options'].get('B', '')}", 
                    f"C. {item['options'].get('C', '')}", 
                    f"D. {item['options'].get('D', '')}"
                ]
                
                choice = st.radio(
                    f"Chọn đáp án câu {item['id']}", 
                    options_list, 
                    key=f"q_{item['id']}",
                    label_visibility="collapsed"
                )
                user_answers[item['id']] = choice[0] if choice else ""
                st.write("")

            submitted = st.form_submit_button("Nộp bài")
            if submitted:
                score = 0
                total = len(st.session_state["quiz_data"])
                for item in st.session_state["quiz_data"]:
                    if user_answers.get(item['id']) == item.get('answer'):
                        score += 1
                st.balloons()
                st.metric(label="Kết quả của bạn", value=f"{score}/{total}")

except Exception as e:
    st.error(f"Lỗi khởi tạo: {e}")
