import os

import pandas as pd
import requests
import streamlit as st

# import streamlit_option_menu
# from streamlit_option_menu import option_menu

st.set_page_config(layout="wide")
STREAMLIT_APP_BACKEND_URL = os.environ.get("STREAMLIT_APP_BACKEND_URL")

# with st.sidebar:
#     selected = option_menu(
#         menu_title="Main Menu",
#         options=["Home", "Warehouse", "Query Optimization and Processing", "Storage", "Contact Us"],
#         icons=["house", "gear", "activity", "snowflake", "envelope"],
#         menu_icon="cast",
#         default_index=0,
#         # orientation = "horizontal",
#     )


st.title("Contract Queue Frontend")

st.markdown("### Health Check")
if st.button("Backend Health Check"):
    res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}")
    if res.status_code == 200:
        data = res.json()
        st.write(data)
    else:
        st.write("Failed to fetch")

st.markdown("***")
res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}/naicscodes")
if res.status_code == 200:
    unique_naics_codes = res.json()
else:
    unique_naics_codes = []

# Naics Code Query
naics_query = st.text_input(
    "Enter an industry, skill, or other keyword to find related NAICS job codes"
)

if st.button("Search"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/naicscodes/search", params={"query": naics_query}
    )

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.dataframe(df, hide_index=True)
    else:
        st.write(f"Error: {res.status_code}")

notice_query = st.text_input(
    "Enter an industry, skill, or other keyword to find relevant notices", "software development"
)

# Chunk Query
if st.button("Search Notices by Chunk"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/summary_chunks", params={"query": notice_query}
    )

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.session_state["df_chunks"] = df
    else:
        st.write(f"Error: {res.status_code}")

if "df_chunks" in st.session_state:
    df = st.session_state["df_chunks"]
    query = st.text_input("Filter chunks Dataframe")
    if query:
        query = query.lower()
        mask = df.applymap(lambda x: query in str(x).lower()).any(axis=1)
        df = df[mask]
    st.dataframe(df, hide_index=True)

# Summary Query
if st.button("Search Notices by Summary"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/summary", params={"query": notice_query}
    )

    if res.status_code == 200:
        data = res.json()
        df = pd.DataFrame(data)
        st.session_state["df_summary"] = df
    else:
        st.write(f"Error: {res.status_code}")

if "df_summary" in st.session_state:
    df = st.session_state["df_summary"]
    query = st.text_input("Filter summary dataframe")
    if query:
        query = query.lower()
        mask = df.applymap(lambda x: query in str(x).lower()).any(axis=1)
        df = df[mask]
    st.dataframe(df, hide_index=True)
