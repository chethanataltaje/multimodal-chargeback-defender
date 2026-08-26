import os
import httpx
from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv()

def test_gemini():
    print("\n--- Testing Google Gemini API ---")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY is missing in .env")
        return

    client = genai.Client(api_key=api_key)
    
    # 1. Fetch available models for your specific key
    try:
        models = [m.name for m in client.models.list() if "generateContent" in (m.supported_actions or [])]
        clean_names = [m.replace("models/", "") for m in models]
        print(f"📋 Supported Gemini models on your key: {clean_names[:5]}...")
    except Exception as e:
        print(f"⚠️ Could not list models: {e}")
        clean_names = []

    # Priority list of current models
    preferred = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    target_model = next((m for m in preferred if m in clean_names), clean_names[0] if clean_names else "gemini-3.6-flash")

    print(f"Testing generation with: '{target_model}'...")
    test_img = Image.new("RGB", (50, 50), color="blue")
    
    try:
        response = client.models.generate_content(
            model=target_model,
            contents=[test_img, "Respond with exactly: 'OK'"],
        )
        print(f"✅ Gemini Online with model '{target_model}'! Response: {response.text.strip()}")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")

def test_groq():
    print("\n--- Testing Groq API ---")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY is missing in .env")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=10.0) as client:
        try:
            res = client.get("https://api.groq.com/openai/v1/models", headers=headers)
            if res.status_code != 200:
                print(f"❌ Groq Authentication Error [{res.status_code}]: {res.text}")
                return

            available_models = [m["id"] for m in res.json().get("data", [])]
            preferred = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
            selected_model = next((m for m in preferred if m in available_models), available_models[0] if available_models else None)

            if not selected_model:
                print("❌ No models found on this Groq account.")
                return

            print(f"Testing Groq inference with model: '{selected_model}'...")
            body = {
                "model": selected_model,
                "messages": [{"role": "user", "content": "Respond with 'OK'"}],
                "max_tokens": 5,
            }
            chat_res = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body)
            if chat_res.status_code == 200:
                msg = chat_res.json()["choices"][0]["message"]["content"].strip()
                print(f"✅ Groq Online! Response: {msg}")
            else:
                print(f"❌ Groq Chat Error [{chat_res.status_code}]: {chat_res.text}")

        except Exception as e:
            print(f"❌ Groq Connection Error: {e}")

if __name__ == "__main__":
    test_gemini()
    test_groq()