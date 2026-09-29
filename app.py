import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# ওয়েবসাইটের নাম এবং লেআউট সেটআপ
st.set_page_config(page_title="Doc Intel Extractor", layout="centered")
st.title("📄 ডকুমেন্ট ইনফরমেশন এক্সট্রাক্টর")
st.write("আপনার OEKO-TEX বা SDL ডকুমেন্টটি (Image) আপলোড করুন।")

# Streamlit Advanced Settings (Secrets) থেকে API Key নেওয়া
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    st.error("❌ দয়া করে Streamlit Advanced Settings (Secrets)-এ আপনার GOOGLE_API_KEY যুক্ত করুন।")

# ফাইল আপলোড অপশন
uploaded_file = st.file_uploader("ডকুমেন্ট আপলোড করুন (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='আপলোডকৃত ডকুমেন্ট', use_column_width=True)
    st.info("💡 তথ্য খোঁজা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    
    prompt = """
    Analyze this document image and classify whether it is 'OEKO-TEX' or 'SDL'.
    Then extract the following information strictly in JSON format. Do not include markdown code formatting like ```json.
    
    If it is OEKO-TEX, extract:
    {
      "Doc Type": "OEKO-TEX",
      "Certificate Holder Name": "...",
      "Certificate Number": "...",
      "Expire Date": "...",
      "Certificate Scope": "..."
    }
    
    If it is SDL, extract:
    {
      "Doc Type": "SDL",
      "Certificate Number/ Holding Oeko-tex number": "...",
      "Name of the seller": "...",
      "Issue date": "..."
    }
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image])
        
        # ট্রিম করে শুধু পিওর জেসন টেক্সট নেওয়া
        clean_text = response.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(clean_text)
        
        st.success("✅ সফলভাবে তথ্য সংগ্রহ করা হয়েছে!")
        st.subheader(f"📄 ডকুমেন্টের ধরন: {data.get('Doc Type', 'অজানা')}")
        
        for key, value in data.items():
            if key != "Doc Type":
                st.write(f"**{key}**")
                # st.code ব্যবহার করলে স্বয়ংক্রিয়ভাবে ডানপাশে একটি 'Copy' বাটন চলে আসে
                st.code(value, language="text")
                
    except Exception as e:
        st.error(f"❌ দুঃখিত, তথ্য সংগ্রহ করা যায়নি। আবার চেষ্টা করুন। ভুলটি হলো: {e}")
