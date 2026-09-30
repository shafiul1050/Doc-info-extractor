import streamlit as st
from google import genai
from PIL import Image
import json
import pypdfium2 as pdfium
import io
from datetime import datetime
import re
import time

# Website Name and Layout Setup
st.set_page_config(page_title="Doc Intel Extractor", layout="centered")
st.title("📄 Document Information Extractor")
st.write("Upload your OEKO-TEX, SDL, or combined document (Image/PDF).")

# Complete Embedded Database of Withdrawn Certificates provided by you
WITHDRAWN_CERTIFICATES = [
    "19001696", "20000901", "24000220", "04.B.9047/1", "05.KA.0012", "05.KA.5882", 
    "07.KA.51265", "07.KA.53969", "09.HBD.70597", "09.HBD.73508", "10.HBD.74861", 
    "11-22936", "11-27369", "11-28208", "11-28251", "11-28854", "11-30432", 
    "11-30448", "11-33333", "11-33701", "11-34179", "11-34200", "11-34266", 
    "11-35533", "11-35536", "11-35881", "11-37139", "11-41447", "11-41536", 
    "11-43875", "11-45894", "11-48507", "11-51912", "11-54735", "11-54863", 
    "11-54965", "11-55265", "11-55812", "11-57672", "11-58484", "11-67198", 
    "14.HBD.40465", "14.HBD.47112", "14.HBD.50663", "14.HBD.50665", "14.HBD.52100", 
    "14.HBD.53304", "15000343", "15.HBD.58746", "15.HBD.63398", "15.HBD.66317", 
    "15.HBD.76518", "16000681", "16.HBD.00566", "17000367", "17000547", 
    "17.HBD.22761", "17.HBD.27981", "18000076", "18000098", "18000100", 
    "18001314", "18001325", "18001538", "18001875", "19000404", "19001551", 
    "19.HBD.68131", "20000282", "20000293", "20000934", "20001328", "20001564", 
    "20001834", "2012BL0022", "2014OK0353", "2014OK0435", "2015OK0322", 
    "2017OK0295", "2018OK1734", "20205OK1672", "2021OK0328", "20.HBD.19413", 
    "20.HBD.35380", "20.HBD.35381", "20.HBD.35382", "20.HBD.35384", "20.HBD.38452", 
    "21000991", "21001194", "21001419", "21001543", "21001936", "21.HBD.60661", 
    "21.HBD.78200", "21.HBD.78202", "21.HBD.78204", "21.HBD.82262", "22000015", 
    "22000217", "22000431", "22002411", "22003164", "22003377", "22.HBD.03448", 
    "22.HBD.45004", "22.HBD.48475", "23000588", "23001118", "23001488", 
    "23001871", "23002333", "23002513", "23002614", "2311289", "2311290", 
    "23.HBD.10888", "23.HBD.13692", "23.HBD.26570", "23.HBD.35805", "23.HBD.57286", 
    "23.HBD.65026", "23.HBD.70122", "24000163", "24.HBD.15289", "24.HBD.43527", 
    "24.HBD.72834", "24.HBD.83998", "24.HBD.85655", "25001402", "25002841", 
    "25.HBD.37705", "25.HBD.48366", "25.HBD.49359", "25.HBD.81643", "26.HBD.96579", 
    "6821CIT", "7180CIT", "7861CIT", "7862CIT", "DH020 223168", "DH020 247438", 
    "HK003 223667", "HKYO 045400", "ZHGO 061107", "ZHGO 062905", "ZHGO 065484", 
    "ZHGO 070426", "SH150 263079.1"
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
            
            for idx, img in enumerate(images_to_process):
                st.image(img, caption=f'Document Page {idx + 1}', use_container_width=True)
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
        Structure exactly as: 
        {
          "Document Type": "...", 
          "OEKO-TEX Details": {"Certificate Holder Name": "...", "Certificate Number": "...", "Expire Date": "...", "Certificate Scope": "..."}, 
          "SDL Details": {"Certificate Number/ Holding Oeko-tex number": "...", "Name of the seller": "...", "Issue date": "..."}
        }
        Note: Fill fields as "Not Found" if missing.
        """
        
        response = None
        contents_payload = [prompt] + images_to_process
        
        def call_gemini_model(model_name):
            try:
                return client.models.generate_content(model=model_name, contents=contents_payload)
            except Exception as error_msg:
                err_str = str(error_msg)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = 30
                    match = re.search(r'retry in (\d+)', err_str)
                    if match:
                        wait_time = int(match.group(1)) + 2
                    
                    st.warning(f"⏳ Free usage limits reached! Waiting {wait_time} seconds to reload your quota...")
                    
                    countdown_placeholder = st.empty()
                    for seconds_left in range(wait_time, 0, -1):
                        countdown_placeholder.text(f"🔄 Retrying automatically in {seconds_left} seconds...")
                        time.sleep(1)
                    countdown_placeholder.empty()
                    
                    st.info("🔄 Quota refreshed! Processing your document now...")
                    return client.models.generate_content(model=model_name, contents=contents_payload)
                else:
                    raise error_msg

        try:
            response = call_gemini_model('gemini-3.8-flash')
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                st.warning("⚠️ Main server is busy. Swapping to backup model...")
                try:
                    response = call_gemini_model('gemini-2.5-flash')
                except Exception as fallback_error:
                    st.error(f"❌ All Google servers are temporarily overloaded. Please try again. Error: {fallback_error}")
            else:
                st.error(f"❌ An error occurred: {e}")
                
        if response is not None:
            try:
                clean_text = response.text.strip().replace("```json", "").replace("```", "")
                data = json.loads(clean_text)
                st.success("✅ Information successfully extracted!")
                st.subheader(f"📄 Classification: {data.get('Document Type', 'Unknown')}")
                
                extracted_oeko_num = "Not Found"
                extracted_oeko_expiry = "Not Found"
                extracted_sdl_num = "Not Found"
                
                if any(v != "Not Found" for v in data.get('OEKO-TEX Details', {}).values()):
                    st.markdown("### 🔹 OEKO-TEX Certificate Data")
                    oeko_data = data.get('OEKO-TEX Details', {})
                    extracted_oeko_num = oeko_data.get("Certificate Number", "Not Found")
                    extracted_oeko_expiry = oeko_data.get("Expire Date", "Not Found")
                    for key, value in oeko_data.items():
                        st.write(f"**{key}**")
                        st.code(value, language="text")
                        
                if any(v != "Not Found" for v in data.get('SDL Details', {}).values()):
                    st.markdown("### 🔹 SDL Certificate Data")
                    sdl_data = data.get('SDL Details', {})
                    extracted_sdl_num = sdl_data.get("Certificate Number/ Holding Oeko-tex number", "Not Found")
                    for key, value in sdl_data.items():
                        st.write(f"**{key}**")
                        st.code(value, language="text")
                
                st.markdown("---")
                st.subheader("🔍 Registry Verification Panel")
                
                if st.button("Verify Certificate", type="primary"):
                    target_oeko = clean_cert_number(extracted_oeko_num)
                    target_sdl = clean_cert_number(extracted_sdl_num)
                    cleaned_db = [clean_cert_number(num) for num in WITHDRAWN_CERTIFICATES]
                    
                    is_withdrawn = (target_oeko and target_oeko in cleaned_db) or (target_sdl and target_sdl in cleaned_db)
                    
                    if is_withdrawn:
                        st.markdown("<h2 style='color:red; font-weight:bold; margin:0;'>🔴 Withdrawn</h2>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h2 style='color:green; font-weight:bold; margin:0;'>🟢 Verified</h2>", unsafe_allow_html=True)
                    
                    if extracted_oeko_expiry and extracted_oeko_expiry != "Not Found":
                        try:
                            date_digits = re.findall(r'\d+', extracted_oeko_expiry)
                            exp_year = None
                            for token in date_digits:
                                if len(token) == 4:
                                    exp_year = int(token)
                                    break
                            
                            if not exp_year and date_digits:
