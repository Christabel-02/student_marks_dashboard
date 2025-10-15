# app.py
import os
import base64
import json
from datetime import datetime

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Firebase admin
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="Student Marks Dashboard", layout="wide")

st.title("🎓 Cloud-Based Student Marks Dashboard")

# ---------------------------
# Initialize Firebase
# ---------------------------
def init_firestore():
    # If running on Streamlit Cloud / remote, we expect env var FIREBASE_CREDENTIALS (base64)
    if "FIREBASE_CREDENTIALS" in os.environ:
        try:
            b64 = os.environ["FIREBASE_CREDENTIALS"]
            json_str = base64.b64decode(b64).decode("utf-8")
            cred_dict = json.loads(json_str)
            cred = credentials.Certificate(cred_dict)
        except Exception as e:
            st.error("Couldn't load Firebase credentials from FIREBASE_CREDENTIALS env var.")
            st.stop()
    else:
        # Local file fallback
        key_path = "firebase_key.json"
        if not os.path.exists(key_path):
            st.error("firebase_key.json not found. Place your Firebase service account JSON file in the project folder (or set FIREBASE_CREDENTIALS env var).")
            st.stop()
        cred = credentials.Certificate(key_path)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firestore()

# ---------------------------
# Helper functions
# ---------------------------
def add_mark(name, student_id, subject, marks, date_str):
    doc_ref = db.collection("students").document()  # auto-id
    doc_ref.set({
        "name": name,
        "student_id": student_id,
        "subject": subject,
        "marks": marks,
        "date": date_str
    })

def fetch_all():
    docs = db.collection("students").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        rows.append({
            "id": d.id,
            "name": data.get("name", ""),
            "student_id": data.get("student_id", ""),
            "subject": data.get("subject", ""),
            "marks": data.get("marks", 0),
            "date": data.get("date", "")
        })
    return pd.DataFrame(rows)

# ---------------------------
# UI: Data entry
# ---------------------------
st.sidebar.header("Add / Manage Marks")
with st.sidebar.form("entry_form", clear_on_submit=True):
    name = st.text_input("Student Name")
    student_id = st.text_input("Student ID (optional)")
    subject = st.text_input("Subject")
    marks = st.number_input("Marks (0-100)", min_value=0, max_value=100, value=0)
    date = st.date_input("Date", value=datetime.today())
    submitted = st.form_submit_button("Add Record")
    if submitted:
        date_str = date.isoformat()
        if not name or not subject:
            st.warning("Please enter at least Student Name and Subject.")
        else:
            add_mark(name, student_id, subject, int(marks), date_str)
            st.success("Record added successfully!")

# ---------------------------
# Main dashboard
# ---------------------------
st.header("📊 Dashboard")

df = fetch_all()
if df.empty:
    st.info("No records yet. Add student marks from the left panel.")
else:
    # Show data table
    st.subheader("All Records")
    st.dataframe(df.sort_values(by="date", ascending=False).reset_index(drop=True))

    # Filters
    cols = st.columns([2,2,2,2])
    with cols[0]:
        subj_filter = st.selectbox("Filter by Subject", options=["All"] + sorted(df['subject'].unique().tolist()))
    with cols[1]:
        student_filter = st.selectbox("Filter by Student", options=["All"] + sorted(df['name'].unique().tolist()))
    with cols[2]:
        agg_choice = st.selectbox("Aggregate", options=["Average", "Max", "Min", "Count"])
    with cols[3]:
        show_chart = st.checkbox("Show Charts", value=True)

    filtered = df.copy()
    if subj_filter != "All":
        filtered = filtered[filtered['subject'] == subj_filter]
    if student_filter != "All":
        filtered = filtered[filtered['name'] == student_filter]

    if filtered.empty:
        st.warning("No data after applying filters.")
    else:
        # Aggregation by subject
        agg_map = {
            "Average": filtered.groupby("subject")["marks"].mean(),
            "Max": filtered.groupby("subject")["marks"].max(),
            "Min": filtered.groupby("subject")["marks"].min(),
            "Count": filtered.groupby("subject")["marks"].count()
        }
        result_series = agg_map[agg_choice].round(2)

        st.subheader(f"{agg_choice} marks by subject")
        st.table(result_series.reset_index().rename(columns={0: agg_choice.lower(), "marks": agg_choice}))

        if show_chart:
            fig, ax = plt.subplots(figsize=(8,4))
            result_series.plot(kind="bar", ax=ax)
            ax.set_ylabel(agg_choice)
            ax.set_xlabel("Subject")
            ax.set_title(f"{agg_choice} by Subject")
            st.pyplot(fig)

        # Student-wise trend (if single student selected)
        if student_filter != "All":
            st.subheader(f"Marks trend for {student_filter}")
            trend = filtered.sort_values("date")
            trend['date'] = pd.to_datetime(trend['date'])
            fig2, ax2 = plt.subplots(figsize=(8,3))
            ax2.plot(trend['date'], trend['marks'], marker='o')
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Marks")
            ax2.set_ylim(0, 100)
            st.pyplot(fig2)

# ---------------------------
# Export / download CSV
# ---------------------------
st.header("Export")
if not df.empty:
    csv = df.to_csv(index=False)
    st.download_button("Download CSV", csv, file_name="student_marks.csv", mime="text/csv")

st.caption("Tip: Keep firebase_key.json in project folder for local testing. Do NOT commit it to GitHub. Use Streamlit secrets for deployment.")
