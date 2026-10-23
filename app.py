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

st.set_page_config(page_title="AI Quiz - Tạo đề trắc nghiệm", page_icon="🧠", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1100px; padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.6rem; border-radius: 18px; background: linear-gradient(120deg, #172554, #4338ca); color: white; margin-bottom: 1rem;}
.hero h1 {color: white; margin-bottom: .3rem;}
div.stButton > button {border-radius: 10px; min-height: 2.6rem;}
</style>
""", unsafe_allow_html=True)

for key, default in {
    "quiz": None, "answers": {}, "submitted": False, "history": []
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

def get_api_key():
    key = "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"
    return key

def extract_text(uploaded_file):
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    if name.endswith((".txt", ".md")):
        return raw.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        if PdfReader is None:
            raise ValueError("Thiếu thư viện pypdf. Hãy cài requirements.txt.")
        reader = PdfReader(BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        if Document is None:
            raise ValueError("Thiếu thư viện python-docx. Hãy cài requirements.txt.")
        doc = Document(BytesIO(raw))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    raise ValueError("Định dạng chưa hỗ trợ. Hãy tải lên PDF, DOCX, TXT hoặc MD.")

def clean_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI trả về dữ liệu không phải JSON hoàn chỉnh. Hãy thử tạo lại.")
    return json.loads(text[start:end + 1])

def normalise_questions(data):
    valid = []
    for q in data.get("questions", []):
        if not isinstance(q, dict):
            continue
        opts = q.get("options", {})
        answer = str(q.get("answer", "")).strip().upper()
        if (q.get("question") and isinstance(opts, dict)
                and all(k in opts for k in ("A", "B", "C", "D"))
                and answer in ("A", "B", "C", "D")):
            valid.append({
                "question": str(q["question"]).strip(),
                "options": {k: str(opts[k]).strip() for k in ("A", "B", "C", "D")},
                "answer": answer,
                "explanation": str(q.get("explanation", "")).strip()
            })
    return valid

def make_quiz(source_text, count, difficulty, topic, model, batch_size=8):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Chưa có Groq API key. Thêm GROQ_API_KEY trong Streamlit → Settings → Secrets.")
    client = Groq(api_key=api_key)
