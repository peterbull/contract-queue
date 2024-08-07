import os
from typing import Any, Dict, List

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from utils.graphs import create_network_graph

st.set_page_config(layout="wide")
STREAMLIT_APP_BACKEND_URL = os.environ.get("STREAMLIT_APP_BACKEND_URL")

# section = st.sidebar.selectbox("Sections", ["Section 1", "Section 2", "Section 3"])

# Title
st.image("imgs/contract-queue.webp", width=400)
st.title("Contract Queue")
st.markdown("## An app for exploring government procurement data with semantic search")
st.markdown(
    """
    <a href="https://github.com/peterbull/contract-queue">Github Repo
    </a>
    """,
    unsafe_allow_html=True,
)
st.markdown("***")

# Nav
st.markdown("### Navigation")
st.markdown(
    "- [Calculating Cosine Distance to Evaluate Semantic Similarity](#calculating-cosine-distance-to-evaluate-semantic-similarity)"
)
st.markdown(
    "- [Calculating Similarity for Network Graphs](#calculating-similarity-for-network-graphs)"
)
st.markdown("- [Search for NAICS Codes](#search-for-naics-codes)")
st.markdown(
    "- [Search Notices by Summary or Chunked Summary](#search-notices-by-summary-or-chunked-summary)"
)
st.markdown("- [Find Notices from Mean Embeddings](#find-notices-from-mean-embeddings)")
st.markdown("- [Find Similar Notices from Notice ID](#find-similar-notices-from-notice-id)")
st.divider()


# Math
st.header("Calculating Cosine Distance to Evaluate Semantic Similarity")
st.markdown(
    "**The `pgvector` plugin for `postgres` will be can handle calculating `cosine distances` out of the box, so we'll be using that to evaluate distances between query embeddings and the returned embeddings from the database.**"
)

st.latex(
    r"""
    \text{{cosine\_distance}}(\mathbf{{A}}, \mathbf{{B}}) = 1 - \frac{{\mathbf{{A}} \cdot \mathbf{{B}}}}{{\|\mathbf{{A}}\| \|\mathbf{{B}}\|}}
    """
)

st.divider()
st.header("Calculating Similarity for Network Graphs")
st.markdown("**The formula for a similarity matrix is:**")
st.latex(
    r"""
S_{ij} = \sum_{k} E_{ik} \cdot E_{jk}
"""
)

st.markdown(
    "**All this means is that we're going to combine the `embedding vectors` of our results into a `matrix` and get the `dot product` of the combined `matrix` and the combined `matrix transposed`**"
)

st.latex(
    r"""
E = \begin{bmatrix}
    1 & 2 & 3 & \cdots & 1535 & 1536 \\
    \vdots & \vdots & \vdots & \ddots & \vdots & \vdots \\
    e_{m1} & e_{m2} & e_{m3} & \cdots & e_{m,1535} & e_{m,1536}
\end{bmatrix}

E^T = \begin{bmatrix}
    1 & \cdots & e_{m1} \\
    2 & \cdots & e_{m2} \\
    3 & \cdots & e_{m3} \\
    \vdots & \ddots & \vdots \\
    1535 & \cdots & e_{m,1535} \\
    1536 & \cdots & e_{m,1536}
\end{bmatrix}
"""
)
st.markdown("<br/>", unsafe_allow_html=True)
st.latex(
    r"""
S = E \cdot E^T = \begin{bmatrix}
    1 & \cdots & e_{m1} \\
    \vdots & \ddots & \vdots \\
    e_{m1} & \cdots & e_{m,1536}
\end{bmatrix} \cdot \begin{bmatrix}
    1 & \cdots & 1536 \\
    \vdots & \ddots & \vdots \\
    e_{m1} & \cdots & e_{m,1536}
\end{bmatrix}
"""
)


st.markdown("**This will compare every `embedding vector` to every other `embedding vector`**")
st.markdown("***")


# NAICS code search
st.header("Search for NAICS Codes")

st.markdown(
    """The [North American Industry Classification System](https://www.census.gov/naics/) (`NAICS`) is the standard used by Federal statistical agencies in classifying business establishments for the purpose of collecting, analyzing, and publishing statistical data related to the U.S. business economy. NAICS codes are one of the categorization methods for government RFP or procurement postings."""
)
st.markdown(
    "Below you can search for `NAICS` categories by semantic similarity. The `embeddings` for your query will be compared to the `embeddings` of the NAICS code description and evaluated using `cosine distance`."
)

st.markdown("""Your query will return a `network graph` and a `dataframe`.""")
st.markdown(
    "- The `dataframe` will return the `nearest` NAICS codes, a.k.a, those most semantically similar to `your query`."
)
st.markdown(
    "- The `network graph` will return a node graph of the `relationships` between the returned NAICS codes, specifically, how similar they are to `each other`"
)

st.markdown("<br/>", unsafe_allow_html=True)
# Naics Query Input
naics_query = st.text_input(
    "Enter an industry, skill, or other keyword to find related NAICS job codes, ex: Software Development",
    "cabinet making",
)

if st.button("Search"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/naicscodes/search", params={"query": naics_query}
    )

    if res.status_code == 200:
        data, embeddings = res.json()
        df = pd.DataFrame(data)
        fig = create_network_graph(
            data,
            embeddings,
            naics_query,
            embedding_key="description_embedding",
            title_key="title",
            similarity_threshold=0.5,
        )
        st.plotly_chart(fig)
        # Show Dataframe
        st.dataframe(df, hide_index=True)
    else:
        st.write(f"Error: {res.status_code}")

st.divider()


# Summary Search
st.header("Search Notices by Summary or Chunked Summary")
st.markdown(
    "New federal procurement notices and related attachments are posted daily on [sam.gov](https://www.sam.gov). The `airflow` backend of this project it configured to get these notices each day, parse their related attachments and store in a `postgres` database."
)
st.markdown("After parsing and storing the attachment data as text, `airflow` will:")
st.markdown("- Use Anthropic's `claude haiku` model to generate summaries of the raw text")
st.markdown("- Generate `embeddings` for the `summary` using OpenAI's `text-embedding-3-small`")
st.markdown("- Chunk the summary")
st.markdown(
    "- Generate `embeddings` for the `summary chunks` using OpenAI's `text-embedding-3-small`"
)
st.markdown(
    "*Due to API rate limits from both `sam.gov` and `Anthropic` a single day of data will be used for the purposes of this demo.*"
)

st.markdown("<br/>", unsafe_allow_html=True)
notice_query = st.text_input(
    "Enter an industry, skill, or other keyword to find relevant notices", "software development"
)

# Chunk Query
if st.button("Search Notices by Summary Chunk"):

    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/summary_chunks", params={"query": notice_query}
    )

    if res.status_code == 200:
        data, embeddings = res.json()
        fig = create_network_graph(
            data,
            embeddings,
            notice_query,
            embedding_key="chunk_embedding",
            title_key="title",
            similarity_threshold=0.5,
        )
        st.session_state["fig_chunks"] = fig
        df = pd.DataFrame(data)
        st.session_state["df_chunks"] = df
    else:
        st.write(f"Error: {res.status_code}")

if "fig_chunks" in st.session_state:
    st.plotly_chart(st.session_state["fig_chunks"])

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
        data, embeddings = res.json()
        fig = create_network_graph(
            data,
            embeddings,
            notice_query,
            embedding_key="summary_embedding",
            title_key="title",
            similarity_threshold=0.5,
        )
        st.session_state["fig_summary"] = fig
        df = pd.DataFrame(data)
        st.session_state["df_summary"] = df
    else:
        st.write(f"Error: {res.status_code}")

if "fig_summary" in st.session_state:
    st.plotly_chart(st.session_state["fig_summary"])

if "df_summary" in st.session_state:
    df = st.session_state["df_summary"]
    query = st.text_input("Filter summary dataframe")
    if query:
        query = query.lower()
        mask = df.applymap(lambda x: query in str(x).lower()).any(axis=1)
        df = df[mask]
    st.dataframe(df, hide_index=True)

st.divider()
st.header("Find Notices from Mean Embeddings")
st.markdown(
    "The summary and chunks `embeddings` can be concatenated and vertically stacked to get a mean embedding for each notice. "
)

mean_embed_query = st.text_input("Enter any keywords or query:", "Roofing repair for small company")

if st.button("Search Mean Embeddings"):

    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/mean_notices",
        params={"query": mean_embed_query},
    )

    if res.status_code == 200:
        data, embeddings = res.json()
        fig = create_network_graph(
            data,
            embeddings,
            notice_query,
            embedding_key="mean_embedding",
            title_key="title",
            similarity_threshold=0.3,
        )
        st.session_state["fig_summary_mean_embeds"] = fig
        df = pd.DataFrame(data)
        st.session_state["df_summary_mean_embeds"] = df
    else:
        st.write(f"Error: {res.status_code}")


if "fig_summary_mean_embeds" in st.session_state:
    st.plotly_chart(st.session_state["fig_summary_mean_embeds"])

if "df_summary_mean_embeds" in st.session_state:
    df = st.session_state["df_summary_mean_embeds"]
    query = st.text_input("Filter mean dataframe")
    if query:
        query = query.lower()
        mask = df.applymap(lambda x: query in str(x).lower()).any(axis=1)
        df = df[mask]
    st.dataframe(df, hide_index=True)


st.divider()
st.header("Find Similar Notices from Notice ID")
st.markdown(
    "Now that the `notices` table has it's own embeddings from the mean mentioned above, we can look for similar notices to a given notice."
)

notice_id_query = st.text_input(
    "Enter a Notice I.D. from one of the tables above:", "4fd8b2bcb07447889cf8f2bef9b5d07b"
)
if st.button("Search Notices By I.D."):

    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/notices/search/{notice_id_query}/nearby_summaries"
    )

    if res.status_code == 200:
        data, embeddings = res.json()
        fig = create_network_graph(
            data,
            embeddings,
            notice_query,
            embedding_key="mean_embedding",
            title_key="title",
            similarity_threshold=0.3,
        )
        st.session_state["fig_nearby_mean_embeds"] = fig
        df = pd.DataFrame(data)
        st.session_state["df_nearby_mean_embeds"] = df
    else:
        st.write(f"Error: {res.status_code}")

if "fig_nearby_mean_embeds" in st.session_state:
    st.plotly_chart(st.session_state["fig_nearby_mean_embeds"])

if "df_nearby_mean_embeds" in st.session_state:
    df = st.session_state["df_nearby_mean_embeds"]
    query = st.text_input("Filter nearby dataframe")
    if query:
        query = query.lower()
        mask = df.applymap(lambda x: query in str(x).lower()).any(axis=1)
        df = df[mask]
    st.dataframe(df, hide_index=True)
