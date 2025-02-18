import streamlit as st
import pandas as pd
import os
import json
from apify_client import ApifyClient
from datetime import datetime, timedelta
from openai import OpenAI
from io import BytesIO

# Path folder untuk token Apify
APIFY_TOKEN_FOLDER = "./Token Apify"

# Fungsi memuat token Apify dari file JSON
def load_apify_tokens(folder_path):
    tokens = {}
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r") as file:
                data = json.load(file)
                tokens[filename] = data["api_key"]
    return tokens

# Muat token Apify
tokens_apify = load_apify_tokens(APIFY_TOKEN_FOLDER)

# Sidebar untuk memilih token
st.sidebar.title("Pengaturan Token")
selected_apify_token_file = st.sidebar.selectbox("Pilih Token Apify", list(tokens_apify.keys()))


# Sidebar Upload Token GPT
st.sidebar.title("Upload Token AI")
gpt_token_file = st.sidebar.file_uploader("Unggah file token AI (.txt)", type=["txt"])

if gpt_token_file:
    gpt_token = gpt_token_file.read().decode("utf-8").strip()
    st.sidebar.success("✅ Token AI berhasil diunggah!")
else:
    gpt_token = None
    st.sidebar.warning("⚠️ Silakan upload file token AI terlebih dahulu.")


# Token Apify yang dipilih
apify_token = tokens_apify[selected_apify_token_file]

st.sidebar.markdown(
    "⚠️ **Jika terjadi error atau limit token, coba ganti token yang dipilih di atas.**"
)

# Inisialisasi klien OpenAI dan Apify
client_apify = ApifyClient(apify_token)
client_gpt = OpenAI(api_key=gpt_token) if gpt_token else None

# Fungsi untuk scraping dan analisis
def scrape_and_analyze():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    run_input = {
        "onlyPostsNewerThan": "1 days",
        "resultsLimit": 100,
        "startUrls": [
            {"url": "https://www.facebook.com/lingkarsemarangofficial"},
            {"url": "https://www.facebook.com/semarangsekarang"},
            {"url": "https://www.facebook.com/mediainfosemarang"},
            {"url": "https://www.facebook.com/rasika105.6FM"}
        ]
    }

    # Jalankan Apify actor
    run = client_apify.actor("KoJrdxJCTtpon81KY").call(run_input=run_input)

    # Ambil hasil scraping
    data_items = [
        {
            'pageName': item.get('pageName', 'none'),
            'text': item.get('text', 'none'),
            'time': item.get('time', 'none'),
            'url': item.get('url', 'none')
        }
        for item in client_apify.dataset(run["defaultDatasetId"]).iterate_items()
    ]
    
    df = pd.DataFrame(data_items)
    if df.empty:
        return pd.DataFrame(), "Tidak ada data yang diperoleh dari proses scraping."
    
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.sort_values(by='time', ascending=False)
    # Hapus timezone agar bisa disimpan ke Excel
    df['time'] = df['time'].dt.tz_localize(None)
    all_texts = " ".join(df['text'].dropna())
    
    prompt = f"""
    Analisislah postingan dari berbagai halaman Facebook berikut:
    {all_texts}
    
    Data pendukung:
    {df.to_string(index=False)}
    
    1. Identifikasi topik utama yang sering muncul.
    2. Tentukan kategori berita (serius, hoaks, satire, dll.).
    3. Berikan ide artikel menarik berdasarkan postingan yang relevan.
    4. Jelaskan alasan pemilihan topik serta sumber datanya.
    5. Sertakan contoh judul, ringkasan, dan struktur penulisan artikel.
    6. Tampilkan URL dan waktu kejadian yang mendukung setiap topik tersebut, dan tempelkan di poin ke 4.
    """

    if client_gpt:
        completion = client_gpt.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        hasil_analisis = completion.choices[0].message.content
    else:
        hasil_analisis = "Token GPT belum diunggah, tidak dapat melakukan analisis."

    return df, hasil_analisis

# UI Streamlit
st.title("Analisis Kejadian Facebook")

st.markdown("""
Pantau kejadian terkini di Semarang dengan mudah menggunakan aplikasi ini.
Pastikan Anda mengganti token di bagian samping jika mengalami masalah.
""")

if st.button("Mulai Scraping dan Analisis"):
    with st.spinner("Sedang melakukan scraping dan analisis data... Mohon tunggu..."):
        df_result, analysis_result = scrape_and_analyze()

    if not df_result.empty:
        st.subheader("📑 Data Hasil Scraping")
        st.dataframe(df_result)

        # Ekspor data ke dalam format Excel
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_result.to_excel(writer, index=False)
            df_result["time"] = df_result["time"].dt.tz_localize(None)
        excel_data = excel_buffer.getvalue()

        # Tombol unduh data Excel
        st.download_button(
            label="Unduh Data dalam Format Excel",
            data=excel_data,
            file_name="hasil_scraping_facebook.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if analysis_result:
        st.subheader("📋 Hasil Analisis")
        st.write(analysis_result)
    else:
        st.error("Tidak ada data yang diperoleh dari proses scraping.")
