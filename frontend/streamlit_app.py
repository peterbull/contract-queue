import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(layout="wide")
STREAMLIT_APP_BACKEND_URL = os.environ.get("STREAMLIT_APP_BACKEND_URL")

st.title("Contract Queue Frontend")

if st.button("Fetch Data"):
    res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}")
    if res.status_code == 200:
        data = res.json()
        st.write(data)
    else:
        st.write("Failed to fetch")

res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}/naicscodes")
if res.status_code == 200:
    unique_naics_codes = res.json()
else:
    unique_naics_codes = []


naics_input = st.selectbox("Enter a NAICS code: ", unique_naics_codes, index=0)
if st.button("Get Data By NAICS Code"):
    res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}/notices/naicscode/{naics_input}")

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.table(df)
    else:
        st.write("Failed to fetch")


naics_query = st.text_input("Enter an industry, skill, or other keyword")

if st.button("Search"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/naicscodes/search", params={"query": naics_query}
    )

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.table(df)
    else:
        st.write(f"Error: {res.status_code}")

notice_query = st.text_input("Enter an industry, skill, or other keyword to find relevant notices")

if st.button("Search Notices by Chunk"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/summary_chunks", params={"query": notice_query}
    )

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.table(df)
    else:
        st.write(f"Error: {res.status_code}")

if st.button("Search Notices by Summary"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/summary", params={"query": notice_query}
    )

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.table(df)
    else:
        st.write(f"Error: {res.status_code}")
