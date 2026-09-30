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
        Note: If both OEKO-TEX and SDL details are found, set "Document Type" as "OEKO+SDL". Fill fields as "Not Found" if missing.
        """
        
        response = None
        contents_payload = [prompt] + images_to_process
        
        # FIXED: Quota Handler & Active Fallback logic with absolute SDK compliance
        def call_gemini_model(model_name):
            try:
                return client.models.generate_content(model=model_name, contents=contents_payload)
            except Exception as error_msg:
                err_str = str(error_msg)
                # Catch Quota Limit (429) or Server Overload (503/404 v1beta traps)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                    wait_time = 25
                    match = re.search(r'retry in (\d+)', err_str)
                    if match:
                        wait_time = int(match.group(1)) + 2
                    
                    st.warning(f"⏳ Server is busy or limits reached! Auto-Refresh Handler is waiting {wait_time} seconds to reload...")
                    
                    # Live UI countdown placeholder
                    countdown_placeholder = st.empty()
                    for seconds_left in range(wait_time, 0, -1):
                        countdown_placeholder.text(f"🔄 Retrying automatically in {seconds_left} seconds...")
                        time.sleep(1)
                    countdown_placeholder.empty()
                    
                    st.info("🔄 Re-trying execution loop now...")
                    return client.models.generate_content(model=model_name, contents=contents_payload)
                else:
                    raise error_msg

        try:
            # 1st attempt with the new global standard model
            response = call_gemini_model('gemini-3.8-flash')
        except Exception as e:
            st.warning("⚠️ Main server encountered an issue. Swapping to active backup model...")
            try:
                # 2nd attempt with universal string naming format without v1beta path conflicts
                response = call_gemini_model('gemini-1.5-flash')
            except Exception as fallback_error:
                st.error(f"❌ All Google servers are temporarily overloaded. Please try again. Error: {fallback_error}")
                
        if response is not None:
            try:
                clean_text = response.text.strip().replace("```json", "").replace("```", "")
                data = json.loads(clean_text)
                
                doc_type_display = data.get('Document Type', 'Unknown')
                if "Combined" in doc_type_display or ("OEKO" in doc_type_display and "SDL" in doc_type_display):
                    doc_type_display = "OEKO+SDL"
                    
                st.success("✅ Information successfully extracted!")
                st.subheader(f"📄 Classification: {doc_type_display}")
                
                # Show OEKO-TEX data layer
                if any(v != "Not Found" for v in data.get('OEKO-TEX Details', {}).values()):
                    st.markdown("### 🔹 OEKO-TEX Certificate Data")
                    oeko_data = data.get('OEKO-TEX Details', {})
                    for key, value in oeko_data.items():
                        st.write(f"**{key}**")
                        if key in ["Certificate Holder Name", "Certificate Number"]:
                            st.code(str(value).upper(), language="text")
                        else:
                            st.code(value, language="text")
                        
                # Show SDL data layer
                if any(v != "Not Found" for v in data.get('SDL Details', {}).values()):
                    st.markdown("### 🔹 SDL Certificate Data")
                    sdl_data = data.get('SDL Details', {})
                    for key, value in sdl_data.items():
                        st.write(f"**{key}**")
                        if key in ["Certificate Number/ Holding Oeko-tex number"]:
                            st.code(str(value).upper(), language="text")
                        else:
                            st.code(value, language="text")
                
                # Official Verification Redirection Panel
                st.markdown("---")
                st.subheader("🌐 Official Verification Registry")
                st.write("Click the link below to manually verify this label on the official OEKO-TEX database:")
                st.markdown("[🔗 Verify on Official Website (oeko-tex.com)](https://oeko-tex.com)", unsafe_allow_html=True)
                            
            except Exception as parse_error:
                st.error(f"❌ Failed to parse data correctly. Error: {parse_error}")
