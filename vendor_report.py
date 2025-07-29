#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import io
import os
import pysftp

# Configure Streamlit page
st.set_page_config(page_title="Finance Report Generator", layout="wide")

# --- Authentication Setup ---
USERNAME = os.getenv("MARKETING_USER", "finance")
PASSWORD = os.getenv("MARKETING_PASS", "finance#1298")

# --- Ensure session state initialization ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# --- Authentication Function ---
def authenticate(username, password):
    return username == USERNAME and password == PASSWORD

# --- Login UI ---
def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if authenticate(username, password):
            st.session_state["authenticated"] = True
            st.success("✅ Login Successful!")
        else:
            st.session_state["authenticated"] = False
            st.error("❌ Invalid username or password.")

# --- SFTP Upload Function ---
def upload_to_sftp(file_bytes, filename):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None  # Warning: disables host key checking for testing only

    host = "dev.buywclothes.com"
    port = 22922
    username = "researchbuy"
    password = "hYQ2eoGpmkJubN8"
    remote_path = "/home/researchbuy/public_html/wms_ax"

    try:
        with pysftp.Connection(
            host=host, port=port, username=username, password=password, cnopts=cnopts
        ) as sftp:
            with sftp.cd(remote_path):
                with open("temp_upload_file.csv", "wb") as f:
                    f.write(file_bytes)
                sftp.put("temp_upload_file.csv", filename)
        os.remove("temp_upload_file.csv")  # Clean up temporary file
        return True, "Upload successful via SFTP."
    except Exception as e:
        return False, f"SFTP upload failed: {e}"

# --- Step 1: Vendor Ledger Analysis ---
def Vendor_ledger_analysis(uploaded_csv_file):
    try:
        df = pd.read_csv(uploaded_csv_file, encoding='cp1252', skiprows=8)
    except Exception as e:
        st.error(f"❌ Error reading the CSV file: {e}")
        return pd.DataFrame()

    df['Invoice No'] = df['Invoice No'].astype(str)
    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)

    df1 = df[~df['Invoice No'].str.lower().str.startswith('opening')]
    df1['Invoice_No_clean'] = df1['Invoice No'].str.replace(r'[^A-Za-z0-9]', '', regex=True)

    grouped = df1.groupby('Invoice_No_clean')[['Debit', 'Credit']].sum().reset_index()
    grouped['Total'] = grouped['Debit'] + grouped['Credit']
    grouped['Remarks'] = grouped['Total'].apply(lambda x: 'Not Duplicate' if x == 0 else 'Duplicate')

    df2 = df1.merge(grouped[['Invoice_No_clean', 'Remarks', 'Total']], on='Invoice_No_clean', how='left')

    st.dataframe(df2.head())

    csv_buffer = io.StringIO()
    df2.to_csv(csv_buffer, index=False)
    st.download_button("📥 Download Processed Report (Step 1)", data=csv_buffer.getvalue(),
                       file_name="vendor_analysis_output.csv", mime="text/csv")

    st.session_state['processed_vendor_report'] = df2
    st.success("✅ Step 1 complete: Vendor Report processed.")

    return df2

# --- Step 2: User Remarks Upload & Merge ---
def urse(user_file):
    try:
        user_df = pd.read_csv(user_file)
    except Exception as e:
        st.error(f"❌ Error reading the uploaded user remarks file: {e}")
        return

    if 'User_Remark' not in user_df.columns:
        st.error("❌ 'User_Remark' column is missing.")
        return

    if 'Invoice_No_clean' not in user_df.columns:
        if 'Invoice No' in user_df.columns:
            user_df['Invoice_No_clean'] = user_df['Invoice No'].astype(str).str.replace(r'[^A-Za-z0-9]', '', regex=True)
        else:
            st.error("❌ Missing 'Invoice_No_clean' or 'Invoice No' column.")
            return

    processed_df = st.session_state.get('processed_vendor_report')
    if processed_df is None:
        st.error("❌ Please complete Step 1 before uploading remarks.")
        return

    merged_df = processed_df.merge(user_df[['Invoice_No_clean', 'User_Remark']], on='Invoice_No_clean', how='left')
    csv_bytes = merged_df.to_csv(index=False).encode('utf-8')

    sftp_success, msg = upload_to_sftp(file_bytes=csv_bytes, filename="user_remark_vendor_report.csv")

    if sftp_success:
        st.success("✅ Step 2 complete: Report uploaded via SFTP.")
        st.download_button("📥 Download Final Report", data=csv_bytes, file_name="final_report.csv", mime="text/csv")
    else:
        st.error(f"❌ {msg}")

# --- MAIN APP LOGIC ---
def main():
    if not st.session_state["authenticated"]:
        login()
    else:
        st.title("📊 Finance Report Generator")

        st.subheader("Step 1: Upload Vendor Ledger CSV")
        uploaded_file = st.file_uploader("Upload Vendor CSV File", type=["csv"])
        if uploaded_file:
            Vendor_ledger_analysis(uploaded_file)

        st.subheader("Step 2: Upload User Remarks (Optional)")
        user_file = st.file_uploader("Upload User Remarks File", type=["csv"])
        if user_file:
            urse(user_file)

if __name__ == "__main__":
    main()
