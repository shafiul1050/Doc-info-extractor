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

# Embedded Database of Withdrawn Certificates (abbreviated for length; full list can be maintained in app)
WITHDRAWN_CERTIFICATES = [
    "19001696", "20000901", "24000220", "04.B.9047/1", "05.KA.0012", "05.KA.5882", 
    "11-22936", "14.HBD.40465", "15000343", "16000681", "17000367", "18000076", 
    "19000404", "20000282", "21000991", "22000015", "23000588", "24000163", 
    "25001402", "6821CIT", "7180CIT", "DH020 223168", "HK003 223667", "SH150 263079.1"
]

def clean_cert_number(cert_str):
    if not cert_str or cert_str.lower() == "not found":
        return ""
    return re.sub(r'[\s\-_./]', '', cert_str).lower()

# Fetch API Key from Streamlit Advanced Settings (Secrets)
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    client = genai.Client(api_key=GOOGLE_API_KEY)
except Exception:
    st.error("❌ Please add your GOOGLE_API_KEY in the Streamlit Advanced Settings (Secrets).")
    st.stop()

# File Upload Option
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
        
        prompt = """
        Analyze all provided document images (OEKO-TEX, SDL, or combined). Extract required fields into valid JSON format without markdown code blocks.
        Structure: {"Document Type": "...", "OEKO-TEX Details": {"Certificate Holder Name": "...", "Certificate Number": "...", "Expire Date": "...", "Certificate Scope": "..."}, "SDL Details": {"Certificate Number/ Holding Oeko-tex number": "...", "Name of the seller": "...", "Issue date": "..."}}
        """
        
        response = None
        contents_payload = [prompt] + images_to_process
        
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=contents_payload
            )
        except Exception as e:
            st.error(f"❌ An error occurred: {e}")
                
        if response is not None:
            try:
                clean_text = response.text.strip().replace("```json", "").replace("```", "")
                data = json.loads(clean_text)
                st.success("✅ Information successfully extracted!")
                st.subheader(f"📄 Classification: {data.get('Document Type', 'Unknown')}")
                
                extracted_oeko_num = data.get('OEKO-TEX Details', {}).get("Certificate Number", "Not Found")
                extracted_oeko_expiry = data.get('OEKO-TEX Details', {}).get("Expire Date", "Not Found")
                extracted_sdl_num = data.get('SDL Details', {}).get("Certificate Number/ Holding Oeko-tex number", "Not Found")
                
                # Render Data Layouts and Verification Panel...
                st.markdown("---")
                st.subheader("🔍 Registry Verification Panel")
                if st.button("Verify Certificate", type="primary"):
                    target_oeko = clean_cert_number(extracted_oeko_num)
                    target_sdl = clean_cert_number(extracted_sdl_num)
                    cleaned_db = [clean_cert_number(num) for num in WITHDRAWN_CERTIFICATES]
                    
                    if (target_oeko and target_oeko in cleaned_db) or (target_sdl and target_sdl in cleaned_db):
                        st.markdown("<h2 style='color:red; font-weight:bold;'>🔴 Withdrawn</h2>", unsafe_allow_html=True)
                        st.error("Warning: Certificate is listed in the official withdrawn database.")
                    else:
                        st.markdown("<h2 style='color:green; font-weight:bold;'>🟢 Verified</h2>", unsafe_allow_html=True)
                        st.success("Pass: Certificate record is clear from active withdrawals.")
            except Exception as parse_error:
                st.error(f"❌ Failed to parse data correctly. Error: {parse_error}")
