#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import io
import os
from ftplib import FTP_TLS


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
        with FTP_TLS(ftp_host) as ftp:
            ftp.login(ftp_user, ftp_pass)
            ftp.cwd(ftp_dir)
            ftp.storbinary(f'STOR {filename}', io.BytesIO(file_bytes))
            return True, "Upload successful."
    except Exception as e:
        return False, f"FTP upload failed: {e}"


# --- Process Vendor Report ---
def Vendor_ledger_analysis(uploaded_pdf_file):
    try:
        df = pd.read_csv(uploaded_pdf_file, encoding='cp1252', skiprows=8)
    except Exception as e:
        st.error(f"Error reading the file: {e}")
        return pd.DataFrame()

    # Clean column names
    df.columns = df.columns.str.strip().str.replace(r' ', '_')

    # Convert 'Invoice No' to string for consistency
    df['Invoice No'] = df['Invoice No'].astype(str)

    # Clean 'Debit' and 'Credit' columns
    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)

    df1 = df[~df['Invoice No'].str.lower().str.startswith('opening')]

    # Clean 'Invoice No' and create new column 'Invoice_No_clean'
    df1['Invoice No'] = df1['Invoice No'].str.upper()
    df1['Invoice_No_clean'] = df1['Invoice No'].str.replace(r'[^A-Za-z0-9]', '', regex=True)

    # Group and summarize
    grouped = df1.groupby('Invoice_No_clean')[['Debit', 'Credit']].sum().reset_index()
    grouped['Total'] = grouped['Debit'] + grouped['Credit']
    grouped['Remarks'] = grouped['Total'].apply(lambda x: 'Not Duplicate' if x == 0 else 'Duplicate')

    df2 = df1.merge(grouped[['Invoice_No_clean', 'Remarks', 'Total']], on='Invoice_No_clean', how='left')
    st.dataframe(df2.head())

    csv_buffer = io.StringIO()
    df2.to_csv(csv_buffer, index=False)
    st.download_button("Download Processed Report", data=csv_buffer.getvalue(), file_name="vendor_analysis_output.csv", mime="text/csv")

    st.session_state['processed_vendor_report'] = df2

    return df2

# --- User Remarks Upload ---
def urse(user_file):
    if 'processed_vendor_report' not in st.session_state:
        st.error("Please complete Step 1 (Vendor Report Upload) before proceeding.")
        return pd.DataFrame()

    original_df = st.session_state['processed_vendor_report']
    user_df = pd.read_csv(user_file)

    user_df['Invoice No'] = user_df['Invoice No'].str.upper().str.replace(r'[^A-Za-z0-9]', '', regex=True)
    original_df['Invoice No'] = original_df['Invoice No'].str.upper().str.replace(r'[^A-Za-z0-9]', '', regex=True)

    if 'User Remark' not in user_df.columns:
        st.error("User Remark column is missing from the uploaded file.")
        return pd.DataFrame()

    merged = pd.merge(original_df, user_df, on="Invoice No", how="left", suffixes=('', '_user'))
    merged['Final Status'] = merged.get('User Remark', 'NA')

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
        st.success("✅ Final report uploaded")
