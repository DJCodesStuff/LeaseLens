# import os
# import glob
# import pandas as pd
# import networkx as nx

# # Define directory containing CSVs
# csv_dir = "./data"
# csv_files = glob.glob(os.path.join(csv_dir, "*.csv"))

# # Columns to normalize
# associate_cols = ['Associate 1', 'Associate 2', 'Associate 3', 'Associate 4']
# all_dataframes = []

# # Load and normalize all CSVs
# for file in csv_files:
#     try:
#         df = pd.read_csv(file)
#         # Only keep necessary columns if present
#         available_cols = set(df.columns)
#         needed = {'unique_id', 'Property Address', 'Floor', 'Suite',
#                   'Annual Rent', 'Monthly Rent', 'GCI On 3 Years', 'Size (SF)'}
#         if not needed.issubset(available_cols):
#             print(f"Skipping {file} due to missing required columns.")
#             continue
#         # Fill associate columns
#         for col in associate_cols:
#             if col not in df.columns:
#                 df[col] = ""
#         df[associate_cols] = df[associate_cols].fillna("")
#         all_dataframes.append(df)
#     except Exception as e:
#         print(f"Error reading {file}: {e}")

# # Combine all data
# if not all_dataframes:
#     raise RuntimeError("No valid CSVs found in ./data to process.")

# combined_df = pd.concat(all_dataframes, ignore_index=True)

# # Create directed graph
# G = nx.DiGraph()

# for _, row in combined_df.iterrows():
#     lease_id = f"Lease-{row['unique_id']}"
#     property_id = f"Property-{row['Property Address']}-{row['Floor']}-{row['Suite']}"

#     # Add Lease node
#     G.add_node(lease_id, type="Lease", annual_rent=row["Annual Rent"],
#                monthly_rent=row["Monthly Rent"], gci=row["GCI On 3 Years"])

#     # Add Property node
#     G.add_node(property_id, type="Property", address=row["Property Address"],
#                floor=row["Floor"], suite=row["Suite"], size=row["Size (SF)"])

#     # Edge Lease → Property
#     G.add_edge(lease_id, property_id, relation="LOCATED_AT")

#     # Edge Lease → Brokers
#     for col in associate_cols:
#         broker = str(row[col]).strip()
#         if broker:
#             broker_id = f"Broker-{broker.replace(' ', '_')}"
#             G.add_node(broker_id, type="Broker", name=broker)
#             G.add_edge(lease_id, broker_id, relation="HANDLED_BY")

# # Save graph
# nx.write_graphml(G, "./data/lease_graph.graphml")
# nx.write_gml(G, "./data/lease_graph.gml")

# print(f"✅ Combined graph created with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")


import os
import pandas as pd
import networkx as nx
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
loaded = load_dotenv(env_path)

# Load Mongo URI from environment variable
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise EnvironmentError("MONGO_URI environment variable is not set.")

# Connect to MongoDB
client = MongoClient(mongo_uri)
db = client["CRM"]
collection = db["Listings"]

# Query all documents
documents = list(collection.find({}))

if not documents:
    raise RuntimeError("No documents found in MongoDB collection 'CRM.listings'.")

# Normalize schema to match expected format
normalized_docs = []
for doc in documents:
    try:
        normalized = {
            "unique_id": doc.get("unique_id"),
            "Property Address": doc.get("property_address", ""),
            "Floor": doc.get("floor", ""),
            "Suite": doc.get("suite", ""),
            "Size (SF)": doc.get("size_sf", 0),
            "Annual Rent": doc.get("annual_rent", 0),
            "Monthly Rent": doc.get("monthly_rent", 0),
            "GCI On 3 Years": doc.get("gci_on_3_years", 0),
            "Associate 1": doc.get("broker_email", ""),  # map broker_email to Associate 1
            "Associate 2": "",
            "Associate 3": "",
            "Associate 4": ""
        }
        normalized_docs.append(normalized)
    except Exception as e:
        print(f"Error normalizing document {doc.get('_id')}: {e}")

# Convert to DataFrame
df = pd.DataFrame(normalized_docs)

# Create directed graph
G = nx.DiGraph()

for _, row in df.iterrows():
    lease_id = f"Lease-{row['unique_id']}"
    property_id = f"Property-{row['Property Address']}-{row['Floor']}-{row['Suite']}"

    # Add Lease node
    G.add_node(lease_id, type="Lease",
               annual_rent=row["Annual Rent"],
               monthly_rent=row["Monthly Rent"],
               gci=row["GCI On 3 Years"])

    # Add Property node
    G.add_node(property_id, type="Property",
               address=row["Property Address"],
               floor=row["Floor"],
               suite=row["Suite"],
               size=row["Size (SF)"])

    # Edge Lease → Property
    G.add_edge(lease_id, property_id, relation="LOCATED_AT")

    # Edge Lease → Brokers
    for col in ['Associate 1', 'Associate 2', 'Associate 3', 'Associate 4']:
        broker = str(row[col]).strip()
        if broker:
            broker_id = f"Broker-{broker.replace(' ', '_')}"
            G.add_node(broker_id, type="Broker", name=broker)
            G.add_edge(lease_id, broker_id, relation="HANDLED_BY")

# Save graph
os.makedirs("./data", exist_ok=True)
nx.write_graphml(G, "./data/lease_graph.graphml")
nx.write_gml(G, "./data/lease_graph.gml")

print(f"✅ Graph created from MongoDB with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
