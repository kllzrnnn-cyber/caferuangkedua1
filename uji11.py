import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

from mlxtend.frequent_patterns import apriori, association_rules

# ==================================================
# CONFIG
# ==================================================

st.set_page_config(
    page_title="Sistem Bundling Cafe Ruang Kedua",
    page_icon="☕",
    layout="wide"
)

# ==================================================
# KREDENSIAL LOGIN
# ==================================================
# Kredensial diambil dari st.secrets (disimpan di file .streamlit/secrets.toml)
# agar tidak ditulis langsung (hardcode) di source code.
#
# Contoh isi file .streamlit/secrets.toml:
#
# [credentials]
# username = "admin_ruangkedua"
# password = "password_rahasia_anda"
#
# Jika secrets belum diatur (misal saat development lokal), kode di bawah
# akan otomatis menggunakan kredensial default sebagai fallback.

try:
    VALID_USERNAME = st.secrets["credentials"]["username"]
    VALID_PASSWORD = st.secrets["credentials"]["password"]
except Exception:
    VALID_USERNAME = "admin"
    VALID_PASSWORD = "ruangkedua123"

# ==================================================
# SESSION STATE UNTUK STATUS LOGIN
# ==================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ==================================================
# FUNGSI HALAMAN LOGIN
# ==================================================

def tampilkan_halaman_login():
    st.title("☕ Sistem Bundling Cafe Ruang Kedua")
    st.subheader("🔒 Login Pengelola Cafe")

    st.markdown(
        "Dashboard ini hanya dapat diakses oleh **pengelola/pemilik Cafe Ruang Kedua**. "
        "Silakan masukkan username dan password untuk melanjutkan."
    )

    with st.form("form_login"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submit = st.form_submit_button("Masuk", type="primary", use_container_width=True)

    if submit:
        if username_input == VALID_USERNAME and password_input == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("❌ Username atau password salah. Silakan coba lagi.")

# ==================================================
# GERBANG LOGIN — HENTIKAN EKSEKUSI JIKA BELUM LOGIN
# ==================================================

if not st.session_state.logged_in:
    tampilkan_halaman_login()
    st.stop()

# ==================================================
# TOMBOL LOGOUT (tampil di sidebar setelah login berhasil)
# ==================================================

with st.sidebar:
    st.success("✅ Anda login sebagai pengelola cafe")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.hasil_analisis = None
        st.rerun()

# ==================================================
# HEADER
# ==================================================

st.title("☕ Sistem Rekomendasi Bundling Produk")
st.subheader("Cafe Ruang Kedua")

st.markdown("""
Dashboard ini menerapkan tahapan **CRISP-DM** (Data Understanding, Data
Preparation, Modeling, Evaluation, Deployment) menggunakan **Algoritma
Apriori** dan **Association Rules** untuk menemukan pola pembelian produk
yang sering terjadi bersamaan, sebagai dasar rekomendasi *bundling* menu.
""")

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title("⚙️ Pengaturan")

uploaded_file = st.sidebar.file_uploader(
    "Upload Dataset Excel",
    type=["xlsx"]
)

# ==================================================
# JIKA FILE BELUM DIUPLOAD
# ==================================================

if uploaded_file is None:
    st.info("📂 Silakan upload dataset Excel terlebih dahulu melalui sidebar.")
    st.markdown(
        """
        **Format kolom yang dibutuhkan:**
        - `Tanggal`
        - `No_Transaksi`
        - `Nama_Produk`
        - `Qty`
        """
    )
    st.stop()

# ==================================================
# BACA DATA
# ==================================================

try:
    df_raw = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Gagal membaca file: {e}")
    st.stop()

# Validasi kolom wajib (Qty diikutkan, karena dipakai untuk membentuk basket)
REQUIRED_COLS = {"No_Transaksi", "Nama_Produk", "Qty"}
if not REQUIRED_COLS.issubset(df_raw.columns):
    missing = REQUIRED_COLS - set(df_raw.columns)
    st.error(f"Kolom berikut tidak ditemukan dalam dataset: **{', '.join(missing)}**")
    st.stop()

# ==================================================
# 1. DATA UNDERSTANDING
# ==================================================

st.header("1️⃣ Data Understanding")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Jumlah Baris", f"{len(df_raw):,}")
with col2:
    st.metric("Jumlah Transaksi", f"{df_raw['No_Transaksi'].nunique():,}")
with col3:
    st.metric("Jumlah Produk (mentah)", f"{df_raw['Nama_Produk'].nunique():,}")
with col4:
    st.metric("Total Missing Value", f"{int(df_raw.isnull().sum().sum()):,}")

with st.expander("🔍 Lihat Preview Data (5 baris pertama)"):
    st.dataframe(df_raw.head(), use_container_width=True)

with st.expander("📊 Pemeriksaan Kualitas Data"):
    n_produk_mentah = df_raw["Nama_Produk"].nunique()
    n_produk_bersih = df_raw["Nama_Produk"].astype(str).str.strip().str.title().nunique()
    if n_produk_mentah != n_produk_bersih:
        st.warning(
            f"⚠️ Terdeteksi duplikasi nama produk akibat penulisan tidak konsisten "
            f"(huruf besar/kecil atau spasi): **{n_produk_mentah} nama** tertulis, "
            f"padahal sebenarnya hanya **{n_produk_bersih} produk unik**. "
            f"Ini akan dirapikan otomatis di tahap Data Preparation."
        )
    else:
        st.success("Tidak ditemukan duplikasi nama produk akibat inkonsistensi penulisan.")

    st.write("**Missing value per kolom:**")
    st.dataframe(df_raw.isnull().sum().rename("jumlah_missing"))

with st.expander("📈 Analisis Karakteristik Data (ukuran basket & produk terlaris)"):
    basket_size_raw = df_raw.groupby("No_Transaksi")["Nama_Produk"].nunique()
    st.write(f"Rata-rata produk unik per transaksi: **{basket_size_raw.mean():.2f}**")

    fig_size, ax_size = plt.subplots(figsize=(8, 4))
    basket_size_raw.value_counts().sort_index().plot(kind="bar", ax=ax_size, color="#4C72B0")
    ax_size.set_xlabel("Jumlah produk unik per transaksi")
    ax_size.set_ylabel("Jumlah transaksi")
    ax_size.set_title("Distribusi Ukuran Basket")
    plt.tight_layout()
    st.pyplot(fig_size)
    plt.close(fig_size)

# ==================================================
# PARAMETER
# ==================================================

st.header("⚙️ Parameter Apriori")

c1, c2, c3 = st.columns(3)

with c1:
    support_percent = st.slider(
        "Minimum Support (%)",
        min_value=1, max_value=50, value=1, step=1,
        help="Seberapa sering kombinasi produk muncul di semua transaksi. "
             "Nilai realistis untuk data ritel/kafe umumnya 1-5%."
    )

with c2:
    confidence_percent = st.slider(
        "Minimum Confidence (%)",
        min_value=10, max_value=100, value=50, step=5,
        help="Seberapa besar peluang produk B dibeli jika produk A sudah dibeli."
    )

with c3:
    min_lift = st.number_input(
        "Minimum Lift",
        min_value=1.00, value=1.50, step=0.10, format="%.2f",
        help="Lift > 1 berarti kombinasi produk lebih sering terjadi dari kebetulan. "
             "Semakin tinggi, semakin kuat hubungannya."
    )

min_support    = support_percent / 100
min_confidence = confidence_percent / 100

# ==================================================
# INISIALISASI SESSION STATE
# ==================================================

if "hasil_analisis" not in st.session_state:
    st.session_state.hasil_analisis = None

# ==================================================
# TOMBOL ANALISIS
# ==================================================

if st.button("🔍 Analisis Data", type="primary", use_container_width=True):

    with st.spinner("Sedang membersihkan data dan menjalankan Apriori..."):

        # ==========================================
        # 2. DATA PREPARATION
        # ==========================================

        df = df_raw.copy()

        # --- Pembersihan Data ---
        df["Nama_Produk"] = df["Nama_Produk"].astype(str).str.strip().str.title()
        df = df.dropna(subset=["No_Transaksi", "Nama_Produk"])
        df = df[df["Qty"] > 0]

        if df.empty:
            st.error("Dataset kosong setelah proses pembersihan data.")
            st.stop()

        # --- Transformasi Data ---
        if "Tanggal" in df.columns:
            df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors="coerce")

        # --- Top produk terlaris (berdasarkan Qty, bukan cuma jumlah baris) ---
        produk_terlaris = (
            df.groupby("Nama_Produk")["Qty"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .sort_values()
        )

        # --- Integrasi dan Penyusunan Data (bentuk basket) ---
        basket = df.groupby(["No_Transaksi", "Nama_Produk"])["Qty"].sum().unstack(fill_value=0)

        # --- Reduksi Data (ubah ke biner: dibeli / tidak) ---
        basket_sets = basket > 0

        if basket_sets.shape[0] == 0:
            st.error("Tidak ada transaksi valid yang dapat diproses.")
            st.stop()

        total_transaksi = basket_sets.shape[0]

        # ==========================================
        # 3. MODELING
        # ==========================================

        frequent_itemsets = apriori(
            basket_sets,
            min_support=min_support,
            use_colnames=True
        )

        if frequent_itemsets.empty:
            st.error(
                f"Tidak ada Frequent Itemset ditemukan dengan Support ≥ {support_percent}%. "
                "Coba turunkan nilai Minimum Support."
            )
            st.stop()

        frequent_itemsets["length"] = frequent_itemsets["itemsets"].apply(len)

        frequent_display = frequent_itemsets.copy()
        frequent_display["itemsets"] = (
            frequent_display["itemsets"].apply(lambda x: ", ".join(sorted(list(x))))
        )
        frequent_display["support"] = frequent_display["support"].round(4)

        # --- Association Rules (metric lift, lalu difilter confidence) ---
        rules = association_rules(
            frequent_itemsets,
            metric="lift",
            min_threshold=min_lift
        )

        rules = rules[rules["confidence"] >= min_confidence]

        if rules.empty:
            st.warning(
                f"Tidak ditemukan Association Rule dengan parameter saat ini.\n\n"
                f"- Support: {support_percent}% | Confidence: {confidence_percent}% | Lift: {min_lift}\n\n"
                "Saran: coba turunkan nilai Support ke 1%, Confidence ke 30%, Lift ke 1.0."
            )
            st.stop()

        # --- Kolom jumlah transaksi pendukung (validasi, bukan cuma persentase) ---
        rules["jumlah_transaksi_pendukung"] = (
            (rules["support"] * total_transaksi).round().astype(int)
        )

        # Format tampilan
        rules_display = rules.copy()
        rules_display["antecedents"] = (
            rules_display["antecedents"].apply(lambda x: ", ".join(sorted(list(x))))
        )
        rules_display["consequents"] = (
            rules_display["consequents"].apply(lambda x: ", ".join(sorted(list(x))))
        )
        rules_display["support"]    = rules_display["support"].round(4)
        rules_display["confidence"] = rules_display["confidence"].round(4)
        rules_display["lift"]       = rules_display["lift"].round(4)

        # Hapus duplikat pasangan terbalik — simpan hanya yang lift-nya lebih tinggi
        rules_display["_pair"] = rules_display.apply(
            lambda r: tuple(sorted([r["antecedents"], r["consequents"]])), axis=1
        )
        rules_display = (
            rules_display
            .sort_values(by="lift", ascending=False)
            .drop_duplicates(subset="_pair")
            .drop(columns=["_pair"])
            .reset_index(drop=True)
        )

        # ------------------------------------------
        # SIMPAN KE SESSION STATE
        # ------------------------------------------

        st.session_state.hasil_analisis = {
            "produk_terlaris": produk_terlaris,
            "frequent_display": frequent_display,
            "rules_display": rules_display,
            "total_transaksi": total_transaksi,
        }

# ==================================================
# 4. EVALUATION  &  5. DEPLOYMENT (dari session_state)
# ==================================================

if st.session_state.hasil_analisis is not None:

    hasil            = st.session_state.hasil_analisis
    produk_terlaris  = hasil["produk_terlaris"]
    frequent_display = hasil["frequent_display"]
    rules_display    = hasil["rules_display"]
    total_transaksi  = hasil["total_transaksi"]

    st.header("4️⃣ Evaluation")

    # ==========================================
    # TOP PRODUK TERLARIS
    # ==========================================

    st.subheader("🏆 Top 10 Produk Terlaris")

    fig_top, ax_top = plt.subplots(figsize=(10, 5))
    bars_top = ax_top.barh(produk_terlaris.index, produk_terlaris.values, color="#4C72B0")
    ax_top.bar_label(bars_top, padding=3)
    ax_top.set_title("Top 10 Produk Terlaris (berdasarkan Qty)", fontsize=14, fontweight="bold")
    ax_top.set_xlabel("Total Qty Terjual")
    ax_top.set_ylabel("Produk")
    plt.tight_layout()
    st.pyplot(fig_top)
    plt.close(fig_top)

    # ==========================================
    # FREQUENT ITEMSET
    # ==========================================

    st.subheader("📦 Frequent Itemset")

    fi1, fi2 = st.columns([1, 2])
    with fi1:
        st.write("**Distribusi panjang itemset:**")
        st.dataframe(
            frequent_display.assign(
                length=frequent_display["itemsets"].apply(lambda x: len(x.split(", ")))
            )["length"].value_counts().sort_index().rename("jumlah_itemset")
        )
    with fi2:
        st.dataframe(
            frequent_display.sort_values(by="support", ascending=False),
            use_container_width=True
        )

    # ==========================================
    # TABEL ASSOCIATION RULE
    # ==========================================

    st.subheader("🔗 Association Rule")

    st.dataframe(
        rules_display[
            ["antecedents", "consequents", "support", "confidence", "lift", "jumlah_transaksi_pendukung"]
        ],
        use_container_width=True
    )

    # ==========================================
    # STATISTIK RULE
    # ==========================================

    st.subheader("📊 Statistik Rule")

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Jumlah Rule",            len(rules_display))
    with s2:
        st.metric("Lift Tertinggi",         round(rules_display["lift"].max(), 4))
    with s3:
        st.metric("Confidence Rata-rata",   round(rules_display["confidence"].mean(), 4))
    with s4:
        st.metric("Support Rata-rata",      round(rules_display["support"].mean(), 4))

    # ==========================================
    # SELEKSI RULE TERBAIK
    # ==========================================

    st.subheader("🧪 Seleksi Rule Terbaik (Confidence ≥ 60% & Lift ≥ 2)")

    rules_terpilih = rules_display[
        (rules_display["confidence"] >= 0.6) & (rules_display["lift"] >= 2)
    ].sort_values(["confidence", "lift"], ascending=False).reset_index(drop=True)

    if rules_terpilih.empty:
        st.info("Belum ada rule yang memenuhi kriteria seleksi ini pada parameter saat ini.")
    else:
        st.dataframe(rules_terpilih, use_container_width=True)

    # ==========================================
    # GRAFIK FREQUENT ITEMSET
    # ==========================================

    st.subheader("📈 Top 10 Frequent Itemset")

    top_itemset = (
        frequent_display
        .sort_values(by="support", ascending=False)
        .head(10)
        .sort_values(by="support")
    )

    fig1, ax1 = plt.subplots(figsize=(10, 5))
    bars1 = ax1.barh(top_itemset["itemsets"], top_itemset["support"], color="#55A868")
    ax1.bar_label(bars1, fmt="%.4f", padding=3)
    ax1.set_title("Top 10 Frequent Itemset berdasarkan Support", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Support")
    ax1.set_ylabel("Itemset")
    plt.tight_layout()
    st.pyplot(fig1)
    plt.close(fig1)

    # ==========================================
    # GRAFIK CONFIDENCE
    # ==========================================

    st.subheader("📊 Top 10 Rule berdasarkan Confidence")

    confidence_chart = (
        rules_display
        .sort_values(by="confidence", ascending=False)
        .head(10)
        .sort_values(by="confidence")
    )
    labels_conf = confidence_chart["antecedents"] + "  ➜  " + confidence_chart["consequents"]

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    bars2 = ax2.barh(labels_conf, confidence_chart["confidence"], color="#C44E52")
    ax2.bar_label(bars2, fmt="%.4f", padding=3)
    ax2.set_title("Top 10 Rule berdasarkan Confidence", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Confidence")
    ax2.set_ylabel("Rule")
    plt.tight_layout()
    st.pyplot(fig2)
    plt.close(fig2)

    # ==========================================
    # GRAFIK LIFT
    # ==========================================

    st.subheader("📈 Top 10 Rule berdasarkan Lift")

    lift_chart = (
        rules_display
        .sort_values(by="lift", ascending=False)
        .head(10)
        .sort_values(by="lift")
    )
    labels_lift = lift_chart["antecedents"] + "  ➜  " + lift_chart["consequents"]

    fig3, ax3 = plt.subplots(figsize=(10, 5))
    bars3 = ax3.barh(labels_lift, lift_chart["lift"], color="#8172B2")
    ax3.bar_label(bars3, fmt="%.4f", padding=3)
    ax3.set_title("Top 10 Rule berdasarkan Lift Ratio", fontsize=13, fontweight="bold")
    ax3.set_xlabel("Lift")
    ax3.set_ylabel("Rule")
    plt.tight_layout()
    st.pyplot(fig3)
    plt.close(fig3)

    # ==========================================
    # 5. DEPLOYMENT
    # ==========================================

    st.header("5️⃣ Deployment")

    st.subheader("🎯 Top Rekomendasi Bundling")

    for jumlah, (_, row) in enumerate(rules_display.head(10).iterrows(), start=1):
        st.success(
            f"**#{jumlah} — {row['antecedents']}  ➜  {row['consequents']}**\n\n"
            f"Support: `{row['support']}`  |  "
            f"Confidence: `{row['confidence']}`  |  "
            f"Lift: `{row['lift']}`  |  "
            f"Didukung `{row['jumlah_transaksi_pendukung']}` transaksi"
        )

    # ==========================================
    # KESIMPULAN
    # ==========================================

    st.subheader("📝 Kesimpulan")

    best_rule = rules_display.iloc[0]

    st.info(
        f"Bundling terbaik adalah **{best_rule['antecedents']}** dengan "
        f"**{best_rule['consequents']}**, memiliki nilai lift sebesar "
        f"**{best_rule['lift']}** dan confidence **{best_rule['confidence']}**, "
        f"didukung **{best_rule['jumlah_transaksi_pendukung']}** transaksi dari "
        f"total **{total_transaksi}** transaksi."
    )

    st.caption(
        "Catatan: nilai confidence/lift yang sangat tinggi (mis. 100%) perlu dicek jumlah "
        "transaksi pendukungnya sebelum dijadikan keputusan bisnis, karena rule yang hanya "
        "didukung sedikit transaksi bisa jadi kebetulan, bukan pola yang benar-benar kuat."
    )

    # ==========================================
    # DOWNLOAD
    # ==========================================

    st.subheader("📥 Download Hasil")

    dl1, dl2 = st.columns(2)

    with dl1:
        csv_rules = rules_display[
            ["antecedents", "consequents", "support", "confidence", "lift", "jumlah_transaksi_pendukung"]
        ].to_csv(index=False)

        st.download_button(
            label="⬇️ Download Association Rule (CSV)",
            data=csv_rules,
            file_name="hasil_association_rule.csv",
            mime="text/csv",
            use_container_width=True
        )

    with dl2:
        csv_itemset = frequent_display.to_csv(index=False)

        st.download_button(
            label="⬇️ Download Frequent Itemset (CSV)",
            data=csv_itemset,
            file_name="hasil_frequent_itemset.csv",
            mime="text/csv",
            use_container_width=True
        )
else:
    st.info("Klik tombol **'Analisis Data'** di atas untuk melihat hasil Evaluation & Deployment.")