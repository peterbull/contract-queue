import os

import pandas as pd
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

naics_input = st.number_input("Enter a NAICS code: ", value=237110)
if st.button("Get Data By NAICS Code"):
    res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}/notices/{naics_input}")

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.table(df)
    else:
        st.write("Failed to fetch")
