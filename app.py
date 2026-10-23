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
    try:
        return st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        return os.getenv("GROQ_API_KEY", "")

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
