import streamlit as st
from google import genai
from PIL import Image
import json
import pypdfium2 as pdfium
import io
from datetime import datetime
import re

# Website Name and Layout Setup
st.set_page_config(page_title="Doc Intel Extractor", layout="centered")
st.title("📄 Document Information Extractor")
st.write("Upload your OEKO-TEX, SDL, or combined document (Image/PDF).")

# Embedded Database of Withdrawn Certificates provided by the user
WITHDRAWN_CERTIFICATES = [
    "19001696", "20000901", "24000220", "04.B.9047/1", "05.KA.0012", "05.KA.5882"
]

def clean_cert_number(cert_str):
    if not cert_str or cert_str.lower() == "not found":
        return ""
    return re.sub(r'[\s\-_./]', '', cert_str).lower()

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    client = genai.Client(api_key=GOOGLE_API_KEY)
except Exception:
    st.error("❌ Please add your GOOGLE_API_KEY in the Streamlit Advanced Settings (Secrets).")
    st.stop()

uploaded_file = st.file_uploader("Upload Document (PNG, JPG, JPEG, PDF)", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    file_type = uploaded_file.name.split(".")[-1].lower()
    images_to_process = []

    try:
        if file_type == "pdf":
            pdf = pdfium.PdfDocument(uploaded_file.read())
            num_pages = len(pdf)
            st.info(f"📄 Processing a total of {num_pages} page(s) from the PDF...")
            for page_idx in range(num_pages):
                page = pdf[page_idx]
                bitmap = page.render(scale=2)
                images_to_process.append(bitmap.to_pil())
            st.image(images_to_process, caption='Document Preview', use_container_width=True)
        else:
            image = Image.open(uploaded_file)
            images_to_process.append(image)
            st.image(image, caption='Uploaded Document', use_container_width=True)
    except Exception as e:
        st.error(f"❌ Failed to read the file. Error: {e}")

    if images_to_process:
        st.info("💡 Analyzing document pages... Please wait.")
        prompt = "Analyze all provided images and extract details into valid JSON format without markdown code blocks."
        
        response = None
        contents_payload = [prompt] + images_to_process
        
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload)
        except Exception as e:
            st.error(f"❌ An error occurred: {e}")
                
        if response is not None:
            try:
                clean_text = response.text.strip()
                data = json.loads(clean_text)
                st.success("✅ Information successfully extracted!")
                
                extracted_oeko_num = data.get('OEKO-TEX Details', {}).get("Certificate Number", "Not Found")
                extracted_sdl_num = data.get('SDL Details', {}).get("Certificate Number/ Holding Oeko-tex number", "Not Found")
                
                if st.button("Verify Certificate", type="primary"):
                    target_oeko = clean_cert_number(extracted_oeko_num)
                    target_sdl = clean_cert_number(extracted_sdl_num)
                    cleaned_db = [clean_cert_number(num) for num in WITHDRAWN_CERTIFICATES]
                    
                    is_withdrawn = (target_oeko and target_oeko in cleaned_db) or (target_sdl and target_sdl in cleaned_db)
                    
                    if is_withdrawn:
                        st.markdown("<h2 style='color:red; font-weight:bold; margin:0;'>🔴 Withdrawn</h2>", unsafe_style_allowed=True)
                        st.error("Warning: Certificate is listed as withdrawn.")
                    else:
                        st.markdown("<h2 style='color:green; font-weight:bold; margin:0;'>🟢 Verified</h2>", unsafe_style_allowed=True)
                        st.success("Pass: Certificate record is clear.")
            except Exception as parse_error:
                st.error(f"❌ Failed to parse data correctly. Error: {parse_error}")
