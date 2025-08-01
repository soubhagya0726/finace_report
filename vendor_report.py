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
    cnopts.hostkeys = None  # Disable host key verification for demo/testing

    host = "dev.buywclothes.com"
    port = 22922
    username = "researchbuy"
    password = "hYQ2eoGpmkJubN8"
    remote_path = "/home/researchbuy/public_html/financereport"

    try:
        with pysftp.Connection(
            host=host, port=port, username=username, password=password, cnopts=cnopts
        ) as sftp:
            with sftp.cd(remote_path):
                with open("temp_upload_file.csv", "wb") as f:
                    f.write(file_bytes)
                sftp.put("temp_upload_file.csv", filename)
        os.remove("temp_upload_file.csv")
        return True, "Upload successful via SFTP."
    except Exception as e:
        return False, f"SFTP upload failed: {e}"

# --- Step 1: Vendor Ledger Analysis ---
def Vendor_ledger_analysis(uploaded_csv_file):
    try:
        df = pd.read_csv(uploaded_csv_file, encoding='cp1252', skiprows=8)
    except Exception as e:
        st.error(f"❌ Error reading the CSV file: {e}")
        return

    df['Invoice No'] = df['Invoice No'].astype(str)
    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)

    df1 = df[~df['Invoice No'].str.lower().str.startswith('opening')]
    df1['Invoice_No_clean'] = df1['Invoice No'].str.replace(r'[^A-Za-z0-9]', '', regex=True)

    grouped = df1.groupby('Invoice_No_clean')[['Debit', 'Credit']].sum().reset_index()
    grouped['Total'] = grouped['Debit'] + grouped['Credit']
    grouped['Remarks'] = grouped['Total'].apply(lambda x: 'Not Duplicate' if x == 0 else 'Duplicate')

    df2 = df1.merge(grouped[['Invoice_No_clean', 'Remarks', 'Total']], on='Invoice_No_clean', how='left')
    df_check = pd.read_csv('https://research.buywclothes.com/financereport/user_remark_vendor_report.csv')
   

    df2['KEY'] = (df2['Vendor code'].astype(str) + '-' +df2['Voucher'].astype(str) )
    df_check['KEY'] = (df_check['Vendor code'].astype(str) + '-' +df_check['Voucher'].astype(str) )
    filtered_table2 = df2[~df2['KEY'].isin(df_check['KEY'])]

    df3 = pd.concat([df_check, filtered_table2], ignore_index=True)
    df3 = df3.drop('KEY', axis=1)

    st.dataframe(df3.head())

    csv_buffer = io.StringIO()
    df3.to_csv(csv_buffer, index=False)
    st.download_button("📥 Download Processed Report (Step 1)", data=csv_buffer.getvalue(),
                       file_name="vendor_analysis_output.csv", mime="text/csv")

    # Optional: upload to SFTP too
    upload = st.checkbox("Upload this file to server via SFTP")
    if upload:
        success, msg = upload_to_sftp(csv_buffer.getvalue().encode('utf-8'), "vendor_analysis_output.csv")
        if success:
            st.success("✅ File uploaded to server.")
        else:
            st.error(f"❌ {msg}")

# --- Step 2: User Remarks Merge (now independent) ---
def urse(user_file):
    try:
        user_df = pd.read_csv(user_file)
    except Exception as e:
        st.error(f"❌ Error reading the uploaded remarks file: {e}")
        return

    st.dataframe(user_df.head())

    # Optional: Add validation or transformation if needed
    csv_bytes = user_df.to_csv(index=False).encode('utf-8')

    # Upload to SFTP
    success, msg = upload_to_sftp(csv_bytes, "user_remark_vendor_report.csv")
    if success:
        st.success("✅ Step 2 complete: Remarks file uploaded via SFTP.")
        st.download_button("📥 Download Uploaded Remarks File", data=csv_bytes,
                           file_name="user_remark_vendor_report.csv", mime="text/csv")
    else:
        st.error(f"❌ {msg}")

# --- MAIN APP LOGIC ---
def main():
    if not st.session_state["authenticated"]:
        login()
    else:
        st.title("📊 Finance Report Generator")

        st.subheader("Step 1: Upload and Analyze Vendor Ledger")
        uploaded_file = st.file_uploader("Upload Vendor Ledger CSV", type=["csv"], key="vendor_csv")
        if uploaded_file:
            Vendor_ledger_analysis(uploaded_file)

        st.subheader("Step 2: Upload User Remarks (Optional)")
        user_file = st.file_uploader("Upload User Remarks File", type=["csv"], key="remarks_csv")
        if user_file:
            urse(user_file)

if __name__ == "__main__":
    main()
