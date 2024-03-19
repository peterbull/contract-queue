import os

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
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
st.markdown("### Search for NAICS Codes")
res = requests.get(f"{STREAMLIT_APP_BACKEND_URL}/naicscodes")
if res.status_code == 200:
    unique_naics_codes = res.json()
else:
    unique_naics_codes = []

# Naics Code Query
naics_query = st.text_input(
    "Enter an industry, skill, or other keyword to find related NAICS job codes", "cabinet making"
)

if st.button("Search"):
    res = requests.get(
        f"{STREAMLIT_APP_BACKEND_URL}/naicscodes/search", params={"query": naics_query}
    )

    if res.status_code == 200:
        data, embeddings = res.json()
        embeddings = np.array([embedding.get("description_embedding") for embedding in embeddings])
        df = pd.DataFrame(data)
        st.dataframe(df, hide_index=True)

        labels = [item.get("title") for item in data]

        # Get similarity matrix
        similarity_matrix = np.dot(embeddings, embeddings.T)

        # Init graph
        G = nx.Graph()
        for i, label in enumerate(labels):
            G.add_node(i, label=label)

        # Add edges based on threshold
        similarity_threshold = 0.5
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                if similarity_matrix[i, j] > similarity_threshold:
                    G.add_edge(i, j)

        pos = nx.spring_layout(G)

        # Add edges
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y, line=dict(width=0.5, color="#888"), hoverinfo="none", mode="lines"
        )

        # Add nodes
        node_x = []
        node_y = []
        for node in pos:
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            hoverinfo="text",
            marker=dict(
                showscale=True,
                colorscale="YlGnBu",
                reversescale=True,
                color=[],
                size=10,
                colorbar=dict(
                    thickness=15, title="Node Connections", xanchor="left", titleside="right"
                ),
                line_width=2,
            ),
        )

        # Color nodes by number of adjacencies
        node_adjacencies = []
        node_text = []
        for node, adjacencies in enumerate(G.adjacency()):
            node_adjacencies.append(len(adjacencies[1]))
            node_text.append(f"{labels[node]} (# of connections: {len(adjacencies[1])})")
        node_trace.marker.color = node_adjacencies
        node_trace.text = node_text

        # Plot graph
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title="<br>Network graph made with Python",
                titlefont_size=16,
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                annotations=[
                    dict(
                        text="Python code: <a href='https://plotly.com/ipython-notebooks/network-graphs/'> https://plotly.com/ipython-notebooks/network-graphs/</a>",
                        showarrow=False,
                        xref="paper",
                        yref="paper",
                        x=0.005,
                        y=-0.002,
                    )
                ],
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            ),
        )

        st.plotly_chart(fig)
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
