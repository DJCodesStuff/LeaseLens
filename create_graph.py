import pandas as pd
import networkx as nx

# Load CSV
df = pd.read_csv("./data/HackathonInternalKnowledgeBase.csv")
associate_cols = ['Associate 1', 'Associate 2', 'Associate 3', 'Associate 4']
df[associate_cols] = df[associate_cols].fillna("")

# Create a directed graph
G = nx.DiGraph()

for _, row in df.iterrows():
    lease_id = f"Lease-{row['unique_id']}"
    property_id = f"Property-{row['Property Address']}-{row['Floor']}-{row['Suite']}"

    # Add Lease node with attributes
    G.add_node(lease_id, type="Lease", annual_rent=row["Annual Rent"],
               monthly_rent=row["Monthly Rent"], gci=row["GCI On 3 Years"])

    # Add Property node with attributes
    G.add_node(property_id, type="Property", address=row["Property Address"],
               floor=row["Floor"], suite=row["Suite"], size=row["Size (SF)"])

    # Connect Lease to Property
    G.add_edge(lease_id, property_id, relation="LOCATED_AT")

    # Connect Lease to Brokers
    for col in associate_cols:
        broker = row[col].strip()
        if broker:
            broker_id = f"Broker-{broker.replace(' ', '_')}"
            G.add_node(broker_id, type="Broker", name=broker)
            G.add_edge(lease_id, broker_id, relation="HANDLED_BY")


# Save as GraphML (openable in Gephi or other tools)
nx.write_graphml(G, "./data/lease_graph.graphml")

# Save as GML (more readable)
nx.write_gml(G, "./data/lease_graph.gml") 

# # Or save as JSON
# import json
# with open("lease_graph.json", "w") as f:
#     json.dump(nx.node_link_data(G), f, indent=2)
