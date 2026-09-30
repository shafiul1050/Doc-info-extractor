import streamlit as st
from google import genai
from PIL import Image
import json
import pypdfium2 as pdfium
import io

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
        # Process PDF File (Extracting ALL pages)
        if file_type == "pdf":
            pdf = pdfium.PdfDocument(uploaded_file.read())
            num_pages = len(pdf)
            st.info(f"📄 Processing a total of {num_pages} page(s) from the PDF...")
            
            for page_idx in range(num_pages):
                page = pdf[page_idx]
                bitmap = page.render(scale=2)
                pil_img = bitmap.to_pil()
                images_to_process.append(pil_img)
                
            # Preview the first page for the user
            st.image(images_to_process[0], caption='Document Preview (Page 1)', use_container_width=True)
        else:
            # Process standard Image file
            image = Image.open(uploaded_file)
            images_to_process.append(image)
            st.image(image, caption='Uploaded Document', use_container_width=True)
            
    except Exception as e:
        st.error(f"❌ Failed to read the file. Error: {e}")

    if images_to_process:
        st.info("💡 Analyzing document pages... Please wait.")
        
        # Updated prompt to handle single or combined document structures across multiple pages
        prompt = """
        Analyze all the provided images of the document. The document may contain an OEKO-TEX certificate, an SDL certificate, or BOTH combined within the pages.
        
        Carefully extract all required fields and return the result strictly in valid JSON format. 
        Do not include markdown code formatting like ```json or ```.
        
        Structure your response exactly like this JSON object:
        {
          "Document Type": "OEKO-TEX only / SDL only / Combined (OEKO-TEX & SDL)",
          "OEKO-TEX Details": {
            "Certificate Holder Name": "...",
            "Certificate Number": "...",
            "Expire Date": "...",
            "Certificate Scope": "..."
          },
          "SDL Details": {
            "Certificate Number/ Holding Oeko-tex number": "...",
            "Name of the seller": "...",
            "Issue date": "..."
          }
        }
        
        Note: If a specific certificate type is not found in the document, fill its fields as "Not Found".
        """
        
        response = None
        # Prepare contents array containing the prompt and all page images
        contents_payload = [prompt] + images_to_process
        
        try:
            # 1st Attempt: Gemini 3.8 Flash
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=contents_payload
            )
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                st.warning("⚠️ Main server is busy. Swapping to backup server...")
                try:
                    # 2nd Attempt: Gemini 3.5 Flash Fallback
                    response = client.models.generate_content(
                        model='gemini-3.5-flash',
                        contents=contents_payload
                    )
                except Exception as fallback_error:
                    st.error(f"❌ All Google servers are temporarily overloaded. Please try again in 1 minute. Error: {fallback_error}")
            else:
                st.error(f"❌ An error occurred: {e}")
                
        # Parse and display results if response is successful
        if response is not None:
            try:
                clean_text = response.text.strip()
                if "```json" in clean_text:
                    clean_text = clean_text.split("```json")[-1].split("```")[0].strip()
                elif "```" in clean_text:
                    clean_text = clean_text.split("```")[0].strip()
                    
                data = json.loads(clean_text)
                
                st.success("✅ Information successfully extracted!")
                st.subheader(f"📄 Classification: {data.get('Document Type', 'Unknown')}")
                
                # Layout for OEKO-TEX details
                if "OEKO-TEX" in data.get('Document Type', '') or any(v != "Not Found" for v in data.get('OEKO-TEX Details', {}).values()):
                    st.markdown("### 🔹 OEKO-TEX Certificate Data")
                    oeko_data = data.get('OEKO-TEX Details', {})
                    for key, value in oeko_data.items():
                        st.write(f"**{key}**")
                        st.code(value, language="text")
                        
                # Layout for SDL details
                if "SDL" in data.get('Document Type', '') or any(v != "Not Found" for v in data.get('SDL Details', {}).values()):
                    st.markdown("### 🔹 SDL Certificate Data")
                    sdl_data = data.get('SDL Details', {})
                    for key, value in sdl_data.items():
                        st.write(f"**{key}**")
                        st.code(value, language="text")
                        
            except Exception as parse_error:
                st.error(f"❌ Failed to parse data correctly. Please re-upload. Error: {parse_error}")
