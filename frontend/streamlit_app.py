import os

import requests
import streamlit as st

STREAMLIT_APP_BACKEND_URL = os.environ.get("STREAMLIT_APP_BACKEND_URL")

st.title("Contract Queue Frontend")

if st.button("Fetch Data"):
    res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}")
    if res.status_code == 200:
        data = res.json()
        st.write(data)
    else:
        st.write("Failed to fetch")
