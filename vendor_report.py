#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import os
from ftplib import FTP
import pdfplumber

# Configure page
st.set_page_config(page_title="Finance Report Generator", layout="wide")

# --- Authentication ---
USERNAME = os.getenv("MARKETING_USER", "finance")
PASSWORD = os.getenv("MARKETING_PASS", "finance#1298")

def authenticate(username, password):
    return username == USERNAME and password == PASSWORD

# --- FTP Upload ---
def upload_to_ftp(file_bytes, filename, ftp_host, ftp_user, ftp_pass, ftp_dir='/'):
    try:
        ftp = FTP(ftp_host)
        ftp.login(ftp_user, ftp_pass)
        ftp.cwd(ftp_dir)
        ftp.storbinary(f'STOR {filename}', io.BytesIO(file_bytes))
        ftp.quit()
        return True, "Upload successful."
    except Exception as e:
        return False, f"FTP upload failed: {e}"

# --- Step 1: Process Vendor PDF Report ---
def Vendor_ledger_analysis(uploaded_pdf_file):
    with pdfplumber.open(uploaded_pdf_file) as pdf:
        all_text = ''
        for page in pdf.pages:
            all_text += page.extract_text() + "\n"

    # NOTE: You need to replace this block with your custom parser logic
    data = []
    for line in all_text.splitlines():
        parts = line.split()
        if len(parts) >= 5:  # assuming structure
            data.append(parts[:5])  # trim to expected 5 columns

    df = pd.DataFrame(data, columns=["Date", "Invoice No", "Description", "Debit", "Credit"])
    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)

    df["Invoice_No_clean"] = df["Invoice No"].str.replace(r'[^A-Za-z0-9]', '', regex=True)
    grouped = df.groupby("Invoice_No_clean")[["Debit", "Credit"]].sum().reset_index()
    grouped["Total"] = grouped["Debit"] + grouped["Credit"]
    grouped["Remarks"] = grouped["Total"].apply(lambda x: "Not Duplicate" if x == 0 else "Duplicate")

    final_df = df.merge(grouped[["Invoice_No_clean", "Remarks"]], on="Invoice_No_clean", how="left")

    st.session_state['processed_vendor_report'] = final_df
    return final_df

# --- Step 2: Handle User Remarks Upload ---
def urse(user_file):
    if 'processed_vendor_report' not in st.session_state:
        st.error("Please complete Step 1 (Vendor Report Upload) before proceeding.")
        return pd.DataFrame()

    original_df = st.session_state['processed_vendor_report']
    user_df = pd.read_csv(user_file)

    merged = pd.merge(original_df, user_df, on="Invoice No", how="left", suffixes=('', '_user'))
    merged['Final Status'] = merged.get('User Remark', 'NA')

    # Upload to FTP
    csv_bytes = merged.to_csv(index=False).encode('utf-8')
    ftp_success, msg = upload_to_ftp(
        file_bytes=csv_bytes,
        filename='user_remark_vendor_report.csv',
        ftp_host='your.ftp.server.com',
        ftp_user='your_ftp_user',
        ftp_pass='your_ftp_pass',
        ftp_dir='/ftp/path/'
    )

    if ftp_success:
        st.success("✅ Final report uploaded to FTP as `user_remark_vendor_report.csv`")
    else:
        st.error(f"FTP upload failed: {msg}")

    return merged

# --- UI ---
def main_app():
    st.markdown("<h1 style='text-align: center;'>Marketing Report Generator</h1>", unsafe_allow_html=True)

    step = st.radio("Choose Step", ["Step 1: Upload Vendor Report", "Step 2: Upload User Remarks"])

    if step == "Step 1: Upload Vendor Report":
        uploaded_pdf = st.file_uploader("Upload Vendor Ledger PDF", type=["pdf"])
        if uploaded_pdf:
            with st.spinner("Processing PDF..."):
                processed_df = Vendor_ledger_analysis(uploaded_pdf)
                if not processed_df.empty:
                    st.success("✅ Vendor report processed successfully.")
                    csv_buffer = io.StringIO()
                    processed_df.to_csv(csv_buffer, index=False)
                    st.download_button("Download Processed Report", data=csv_buffer.getvalue(), file_name="vendor_analysis_output.csv", mime="text/csv")

    elif step == "Step 2: Upload User Remarks":
        uploaded_csv = st.file_uploader("Upload User Remarks CSV (based on previous download)", type=["csv"])
        if uploaded_csv:
            with st.spinner("Merging with original data and uploading to FTP..."):
                final_df = urse(uploaded_csv)
                if not final_df.empty:
                    st.dataframe(final_df.head())

# --- Login Page ---
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>Login</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if authenticate(username, password):
                    st.session_state.authenticated = True
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

# --- Main Flow ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if st.session_state.authenticated:
    main_app()
else:
    login_page()

