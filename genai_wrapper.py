import os
import re
import networkx as nx
from dotenv import load_dotenv
import google.generativeai as genai

class GenAIWrapper:
    def __init__(self, system_prompt=None, enable_rag=False):
        load_dotenv()

        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("MODEL_NAME", "gemini-pro")
        self.system_prompt = system_prompt or os.getenv(
            "SYSTEM_PROMPT",
            "You are a helpful, multilingual assistant."
        )

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables.")

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        self.chat = self.model.start_chat(history=[
            {"role": "user", "parts": [self.system_prompt.strip()]}
        ])

        self.enable_rag = enable_rag
        self.graph_context = []  # Text-based summary of the graph
        self.graph = None        # The NetworkX graph for queries

    def add_rag_documents(self, graph_file_path):
        if not self.enable_rag:
            print("RAG is disabled.")
            return

        try:
            if graph_file_path.endswith(".graphml"):
                G = nx.read_graphml(graph_file_path)
            elif graph_file_path.endswith(".gml"):
                G = nx.read_gml(graph_file_path)
            else:
                raise ValueError("Unsupported graph file format. Use .gml or .graphml")

            self.graph = G

            chunks = []
            for node, data in G.nodes(data=True):
                chunks.append(f"Node {node}: {dict(data)}")
            for u, v, data in G.edges(data=True):
                chunks.append(f"Edge from {u} to {v}: {dict(data)}")

            self.graph_context = chunks
            print(f"Loaded {len(chunks)} graph elements into RAG context.")

        except Exception as e:
            print(f"Error loading graph file: {e}")

    def query_graph(self, query_type, **kwargs):
        if self.graph is None:
            return "No graph loaded for querying."

        try:
            G = self.graph

            if query_type == "brokers_for_lease":
                lease_id_query = kwargs.get("lease_id")
                lease_node = None

                for node, data in G.nodes(data=True):
                    if data.get("type") == "Lease" and (node == lease_id_query or node.endswith(lease_id_query)):
                        lease_node = node
                        break

                if not lease_node:
                    return f"Lease {lease_id_query} not found in graph."

                brokers = []
                for neighbor in G.successors(lease_node):
                    if G.nodes[neighbor].get("type") == "Broker":
                        brokers.append(G.nodes[neighbor].get("name", neighbor))

                return brokers or f"No brokers found for lease {lease_node}."

            elif query_type == "lease_info_by_suite":
                address = kwargs.get("address")
                floor = kwargs.get("floor")
                suite = kwargs.get("suite")
                property_node = f"Property-{address}-{floor}-{suite}"

                if not G.has_node(property_node):
                    return f"Property {property_node} not found in graph."

                leases = [u for u, v in G.edges() if v == property_node and G.nodes[u].get("type") == "Lease"]
                lease_data = []
                for lease_id in leases:
                    lease_data.append({
                        "Lease ID": lease_id,
                        "Annual Rent": G.nodes[lease_id].get("annual_rent"),
                        "Monthly Rent": G.nodes[lease_id].get("monthly_rent"),
                        "GCI": G.nodes[lease_id].get("gci")
                    })

                return lease_data or f"No leases found for property {property_node}."

            else:
                return f"Unsupported query type: {query_type}"

        except Exception as e:
            return f"Error in query: {e}"

    def extract_query_intent(self, prompt):
        prompt_lower = prompt.lower()

        lease_match = re.search(r"lease[ -]?(\d+)", prompt_lower)
        if "who" in prompt_lower and "handle" in prompt_lower and lease_match:
            return {
                "query_type": "brokers_for_lease",
                "params": {"lease_id": f"Lease-{lease_match.group(1)}"}
            }

        property_match = re.search(r"property at (.+?), floor (\d+), suite (\d+)", prompt_lower)
        if "rent" in prompt_lower and property_match:
            return {
                "query_type": "lease_info_by_suite",
                "params": {
                    "address": property_match.group(1).strip(),
                    "floor": property_match.group(2),
                    "suite": property_match.group(3)
                }
            }

        return None  # No match

    def generate(self, prompt, **kwargs):
        try:
            if not prompt or not isinstance(prompt, str):
                raise ValueError("Prompt must be a non-empty string.")

            # Detect queryable intent and run graph query
            query_result = None
            if self.enable_rag and self.graph:
                intent = self.extract_query_intent(prompt)
                if intent:
                    query_result = self.query_graph(intent["query_type"], **intent["params"])

            # Add graph context (RAG)
            if self.enable_rag and self.graph_context:
                prompt += "\n\n---\nRelevant graph context:\n" + "\n".join(self.graph_context[:50])

            # Add query result (if detected)
            if query_result:
                prompt += "\n\n---\nGraph query result:\n" + str(query_result)

            # Send enriched prompt to Gemini
            response = self.chat.send_message(prompt, **kwargs)
            return response.text

        except Exception as e:
            return f"Error during generation: {str(e)}"

    def print_sample_nodes(self, n=10):
        if self.graph:
            print("Sample nodes:")
            for i, (node, data) in enumerate(self.graph.nodes(data=True)):
                print(f"{i+1}. {node} → {data}")
                if i + 1 >= n:
                    break
        else:
            print("Graph not loaded.")
