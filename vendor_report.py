#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import io
import os
from ftplib import FTP_TLS

# Configure page
st.set_page_config(page_title="Finance Report Generator", layout="wide")

# --- Authentication Setup ---
USERNAME = os.getenv("MARKETING_USER", "finance")  # Default: "finance"
PASSWORD = os.getenv("MARKETING_PASS", "finance#1298")  # Default: "finance#1298"

def authenticate(username, password):
    """Function to check if username and password match"""
    return username == USERNAME and password == PASSWORD

# --- Login Functionality ---
def login():
    """Handles the login process"""
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    # Login button
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state["authenticated"] = True
            st.success("Login Successful!")
            return True
        else:
            st.session_state["authenticated"] = False
            st.error("Invalid username or password.")
            return False

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

# --- Process Vendor Report (Step 1) ---
def Vendor_ledger_analysis(uploaded_csv_file):
    try:
        df = pd.read_csv(uploaded_csv_file, encoding='cp1252', skiprows=8)
    except Exception as e:
        st.error(f"Error reading the CSV file: {e}")
        return pd.DataFrame()

    # Ensure 'Invoice No' is treated as a string
    df['Invoice No'] = df['Invoice No'].astype(str)

    # Clean 'Debit' and 'Credit' columns
    df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)

    # Filter out rows where 'Invoice No' starts with 'Opening'
    df1 = df[~df['Invoice No'].str.lower().str.startswith('opening')]

    # Remove special characters from 'Invoice No' and create a new column 'Invoice_No_clean'
    df1['Invoice_No_clean'] = df1['Invoice No'].str.replace(r'[^A-Za-z0-9]', '', regex=True)

    # Group by 'Invoice_No_clean' and sum 'Debit' and 'Credit'
    grouped = df1.groupby('Invoice_No_clean')[['Debit', 'Credit']].sum().reset_index()
    grouped['Total'] = grouped['Debit'] + grouped['Credit']
    grouped['Remarks'] = grouped['Total'].apply(lambda x: 'Not Duplicate' if x == 0 else 'Duplicate')

    # Merge grouped data with the original dataframe
    df2 = df1.merge(grouped[['Invoice_No_clean', 'Remarks', 'Total']], on='Invoice_No_clean', how='left')
    
    # Show processed data in the app
    st.dataframe(df2.head())

    # Prepare CSV for download
    csv_buffer = io.StringIO()
    df2.to_csv(csv_buffer, index=False)
    st.download_button("Download Processed Report (Step 1)", data=csv_buffer.getvalue(), file_name="vendor_analysis_output.csv", mime="text/csv")

    # Save processed data to session state
    st.session_state['processed_vendor_report'] = df2

    st.success("✅ Step 1 - Vendor Report processed and ready for download.")
    
    return df2


# --- User Remarks Upload (Step 2) ---
def urse(user_file):
    if 'processed_vendor_report' not in st.session_state:
        st.error("Please complete Step 1 (Vendor Report Upload) before proceeding.")
        return pd.DataFrame()

    original_df = st.session_state['processed_vendor_report']
    user_df = pd.read_csv(user_file)

    # Clean 'Invoice No' in user data and original data
    user_df['Invoice No'] = user_df['Invoice No'].str.upper().str.replace(r'[^A-Za-z0-9]', '', regex=True)
    original_df['Invoice No'] = original_df['Invoice No'].str.upper().str.replace(r'[^A-Za-z0-9]', '', regex=True)

    if 'User Remark' not in user_df.columns:
        st.error("User Remark column is missing from the uploaded file.")
        return pd.DataFrame()

    # Merge the user remarks with the original processed data
    merged = pd.merge(original_df, user_df, on="Invoice No", how="left", suffixes=('', '_user'))
    merged['Final Status'] = merged.get('User Remark', 'NA')

    # Convert the merged data to CSV and upload to FTP
    csv_bytes = merged.to_csv(index=False).encode('utf-8')
    ftp_success, msg = upload_to_ftp(
        file_bytes=csv_bytes,
        filename='user_remark_vendor_report.csv',
        ftp_host='dev.buywclothes.com',
        ftp_user='researchbuy',
        ftp_pass='hYQ2eoGpmkJubN8',
        ftp_dir='/home/researchbuy/public_html/wms_ax'
    )

    if ftp_success:
        st.success("✅ Step 2 - Final report uploaded successfully.")
    else:
        st.error(f"❌ {msg}")


# --- Streamlit UI ---
if 'authenticated' not in st.session_state or not st.session_state['authenticated']:
    # If not authenticated, show login page
    login()
else:
    # Main app functionality after login
    st.title("Finance Report Generator")

    # Step 1: Vendor Report Upload
    step_1 = st.selectbox("Select Step 1: Vendor Report Upload", ["Select", "Upload Vendor Report"])
    if step_1 == "Upload Vendor Report":
        uploaded_csv = st.file_uploader("Upload Vendor CSV File", type=["csv"])
        if uploaded_csv is not None:
            # Process the Vendor Ledger CSV file (Step 1)
            Vendor_ledger_analysis(uploaded_csv)

    # Step 2: User Remarks Upload
    step_2 = st.selectbox("Select Step 2: User Remarks Upload", ["Select", "Upload User Remarks"])
    if step_2 == "Upload User Remarks":
        if 'processed_vendor_report' not in st.session_state:
            st.error("Please complete Step 1 before uploading the user remarks.")
        else:
            user_file = st.file_uploader("Upload User Remarks CSV", type=["csv"])
            if user_file is not None:
                # Process User Remarks Upload (Step 2)
                urse(user_file)
