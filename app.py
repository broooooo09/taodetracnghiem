    st.header("⚙️ Cài đặt đề")
    question_count = st.slider("Số câu hỏi", min_value=5, max_value=100, value=20, step=5)
    difficulty = st.selectbox("Độ khó", ["Cơ bản", "Trung bình", "Nâng cao", "Hỗn hợp"])
    topic = st.text_input("Chủ đề (không bắt buộc)", placeholder="Ví dụ: Sinh học tế bào")
    model = st.text_input("Groq model", value=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    st.caption("API key nên đặt trong Streamlit Secrets, không ghi trực tiếp vào code.")

tab_create, tab_quiz, tab_history = st.tabs(["📚 Tạo đề", "✍️ Làm bài", "📊 Lịch sử phiên"])

with tab_create:
    st.subheader("Tạo đề từ tài liệu")
    st.write("Tải lên PDF có văn bản, DOCX, TXT hoặc MD. Có thể dán thêm nội dung bài học.")
    uploaded = st.file_uploader("Chọn tài liệu", type=["pdf", "docx", "txt", "md"])
    pasted = st.text_area("Hoặc dán nội dung tài liệu vào đây", height=180,
                          placeholder="Dán ghi chú hoặc nội dung bài học...")
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
                with st.spinner("Groq AI đang đọc tài liệu và tạo đủ câu hỏi..."):
                    quiz = make_quiz(source, question_count, difficulty, topic, model.strip())
                st.session_state.quiz = quiz
                st.session_state.answers = {}
                st.session_state.submitted = False
                st.success(f"Đã tạo {len(quiz['questions'])}/{question_count} câu. Mở tab “Làm bài” hoặc tải file đề bên dưới.")
                safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", quiz["title"]).strip("_")[:50] or "de_trac_nghiem"
                st.download_button("⬇️ Tải toàn bộ đề (.txt)", data=quiz_as_text(quiz),
                                   file_name=f"{safe_name}.txt", mime="text/plain; charset=utf-8",
                                   use_container_width=True)
                st.download_button("⬇️ Tải đề dạng JSON", data=json.dumps(quiz, ensure_ascii=False, indent=2),
                                   file_name=f"{safe_name}.json", mime="application/json",
                                   use_container_width=True)
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
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", quiz["title"]).strip("_")[:50] or "de_trac_nghiem"
        st.download_button("⬇️ Tải toàn bộ đề (.txt)", data=quiz_as_text(quiz),
                           file_name=f"{safe_name}.txt", mime="text/plain; charset=utf-8")
        with st.form("quiz_form"):
            selected_answers = {}
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Câu {i + 1}. {q['question']}**")
                current = st.session_state.answers.get(str(i))
                choice = st.radio(
                    f"Chọn đáp án câu {i + 1}",
                    options=["A", "B", "C", "D"],
                    format_func=lambda key, opts=q["options"]: f"{key}. {opts[key]}",
                    index=["A", "B", "C", "D"].index(current) if current in ["A", "B", "C", "D"] else None,
                    key=f"answer_{i}",
                    label_visibility="collapsed",
                )
                selected_answers[str(i)] = choice
                st.divider()
            submitted = st.form_submit_button("Nộp bài và chấm điểm", type="primary", use_container_width=True)
        if submitted:
            st.session_state.answers = selected_answers
            st.session_state.submitted = True
            correct = sum(1 for i, q in enumerate(quiz["questions"])
                          if selected_answers.get(str(i)) == q["answer"])
            score = round(correct / len(quiz["questions"]) * 10, 2)
            st.session_state.history.insert(0, {
                "title": quiz["title"], "correct": correct,
                "total": len(quiz["questions"]), "score": score
            })
        if st.session_state.submitted:
            correct = sum(1 for i, q in enumerate(quiz["questions"])
                          if st.session_state.answers.get(str(i)) == q["answer"])
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
