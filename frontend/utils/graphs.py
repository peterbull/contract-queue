from typing import Any, Dict, List

import networkx as nx
import numpy as np
import plotly.graph_objects as go


def create_network_graph(
    data: List[Dict[str, Any]],
    embeddings: List[Dict[str, List[float]]],
    embedding_key: str = "description_embedding",
    title_key: str = "title",
    similarity_threshold: float = 0.5,
) -> go.Figure:
    labels = [item.get(title_key) for item in data]
    embeddings = np.array([embedding.get(embedding_key) for embedding in embeddings])
    # Get similarity matrix
    similarity_matrix = np.dot(embeddings, embeddings.T)

    # Init graph
    G = nx.Graph()
    for i, label in enumerate(labels):
        G.add_node(i, label=label)

    # Add edges based on threshold
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
            title="<br>Network Graph of NAICS Code Relationships",
            titlefont_size=16,
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[
                dict(
                    text="Contract Queue",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.005,
                    y=-0.002,
                )
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            width=1200,
            height=600,
            dragmode="pan",
        ),
    )

    return fig
