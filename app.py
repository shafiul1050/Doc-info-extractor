import streamlit as st
from google import genai
from PIL import Image
import json
import pypdfium2 as pdfium
import io

# ওয়েবসাইটের নাম এবং লেআউট সেটআপ
st.set_page_config(page_title="Doc Intel Extractor", layout="centered")
st.title("📄 ডকুমেন্ট ইনফরমেশন এক্সট্রাক্টর")
st.write("আপনার OEKO-TEX বা SDL ডকুমেন্টটি (Image/PDF) আপলোড করুন।")

# Streamlit Advanced Settings (Secrets) থেকে API Key নিয়ে ক্লায়েন্ট তৈরি করা
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    # নতুন গুগল এসডিকে (SDK) অনুযায়ী ক্লায়েন্ট সেটআপ
    client = genai.Client(api_key=GOOGLE_API_KEY)
except Exception:
    st.error("❌ দয়া করে Streamlit Advanced Settings (Secrets)-এ আপনার GOOGLE_API_KEY যুক্ত করুন।")
    st.stop()

# ফাইল আপলোড অপশন
uploaded_file = st.file_uploader("ডকুমেন্ট আপলোড করুন (PNG, JPG, JPEG, PDF)", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    file_type = uploaded_file.name.split(".")[-1].lower()
    image = None

    try:
        # PDF ফাইল প্রসেস করা
        if file_type == "pdf":
            pdf = pdfium.PdfDocument(uploaded_file.read())
            page = pdf[0] # প্রথম পেজ
            bitmap = page.render(scale=2)
            pil_img = bitmap.to_pil()
            
            image = pil_img
            st.image(image, caption='আপলোডকৃত PDF ডকুমেন্টের প্রথম পাতা', use_container_width=True)
        else:
            # ইমেজ ফাইল প্রসেস করা
            image = Image.open(uploaded_file)
            st.image(image, caption='আপলোডকৃত ডকুমেন্ট', use_container_width=True)
            
    except Exception as e:
        st.error(f"❌ ফাইলটি পড়তে সমস্যা হচ্ছে। ভুল: {e}")

    if image is not None:
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
            # গুগলের নতুন আপডেটেড লাইব্রেরির নিয়ম অনুযায়ী মডেল কল করা
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, image]
            )
            
            # টেক্সট পরিষ্কার করা
            clean_text = response.text.strip()
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[-1].split("```")[0].strip()
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(clean_text)
            
            st.success("✅ সফলভাবে তথ্য সংগ্রহ করা হয়েছে!")
            st.subheader(f"📄 ডকুমেন্টের ধরন: {data.get('Doc Type', 'অজানা')}")
            
            for key, value in data.items():
                if key != "Doc Type":
                    st.write(f"**{key}**")
                    # টেক্সটটি কোড ব্লকে দেখানো হচ্ছে যাতে পাশে থাকা কপি বাটনে ক্লিক করে কপি করা যায়
                    st.code(value, language="text")
                    
        except Exception as e:
            st.error(f"❌ দুঃখিত, তথ্য সংগ্রহ করা যায়নি। আবার চেষ্টা করুন। ভুলটি হলো: {e}")
