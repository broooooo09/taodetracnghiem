import streamlit as st
from google import genai
import json
import tempfile

# Cấu hình trang web
st.set_page_config(page_title="AI Tạo Đề Trắc Nghiệm kiểu Azota", layout="wide")

st.title("📚 Trợ Lý AI Chuyển Đổi Đề Trắc Nghiệm")
st.write("Tải lên file đề thi (PDF, Word, Ảnh) để AI tự động chuyển thành định dạng trắc nghiệm trực tuyến.")

# Nhập Gemini API Key
api_key = st.sidebar.text_input("Nhập Google Gemini API Key của bạn:", type="password")

if api_key:
    try:
        # Sử dụng thư viện google-genai mới tương thích với Key dạng AQ...
        client = genai.Client(api_key=api_key.strip())

        uploaded_file = st.file_uploader("Chọn file đề thi", type=["pdf", "docx", "png", "jpg", "jpeg"])

        if uploaded_file is not None:
            st.success(f"Đã tải lên: {uploaded_file.name}")
            
            if st.button("🚀 Xử lý và tạo đề trắc nghiệm"):
                with st.spinner("AI đang đọc đề và phân tích câu hỏi..."):
                    try:
                        # Lưu file tạm để tải lên Gemini API
                        suffix = f".{uploaded_file.name.split('.')[-1]}"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        # Upload file lên Gemini API
                        uploaded_media = client.files.upload(file=tmp_path)

                        prompt = """
                        Hãy đọc kỹ tài liệu/hình ảnh đề thi trắc nghiệm đính kèm. 
                        Trích xuất toàn bộ các câu hỏi trắc nghiệm và trả về kết quả DUY NHẤT dưới dạng một mảng JSON (JSON array) với cấu trúc chuẩn sau đây, không kèm theo văn bản giải thích nào khác:
                        [
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
                        ]
                        (Lưu ý: Trường "answer" là đáp án đúng nếu có trong đề, nếu không có hãy để trống hoặc đoán dựa trên nội dung).
                        """

                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[uploaded_media, prompt]
                        )

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
        st.error(f"Lỗi khởi tạo API Key: {e}")
else:
    st.warning("Vui lòng nhập Gemini API Key ở thanh bên trái để bắt đầu.")
