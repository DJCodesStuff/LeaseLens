

# import os
# import networkx as nx
# from dotenv import load_dotenv
# import google.generativeai as genai
# from Agents.graph_query_agent import GraphQueryAgent
# from Agents.prompts import SYSTEM_PROMPT


# class GenAIWrapper:
#     def __init__(self, system_prompt=None):
#         load_dotenv()

#         self.api_key = os.getenv("GOOGLE_API_KEY")
#         self.model_name = os.getenv("MODEL_NAME", "gemini-pro")
#         self.system_prompt = system_prompt or SYSTEM_PROMPT

#         if not self.api_key:
#             raise ValueError("GOOGLE_API_KEY not found in environment variables.")

#         # Configure Gemini
#         genai.configure(api_key=self.api_key)
#         self.model = genai.GenerativeModel(self.model_name)
#         self.chat = self.model.start_chat(history=[
#             {"role": "user", "parts": [self.system_prompt.strip()]}
#         ])

#         self.graph = None
#         self.query_agent = None

#     def load_graph(self, graph_file_path):
#         try:
#             if graph_file_path.endswith(".graphml"):
#                 self.graph = nx.read_graphml(graph_file_path)
#             elif graph_file_path.endswith(".gml"):
#                 self.graph = nx.read_gml(graph_file_path)
#             else:
#                 raise ValueError("Unsupported graph file format. Use .graphml or .gml")

#             if self.graph:
#                 self.query_agent = GraphQueryAgent(graph_file_path)
#                 print(f"✅ Graph loaded with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
#         except Exception as e:
#             print(f"Error loading graph file: {e}")

#     def safe_float(self, value):
#         try:
#             return float(str(value).replace("$", "").replace(",", "").strip())
#         except (ValueError, TypeError):
#             return None

#     def query_graph(self, query_type, **kwargs):
#         if self.graph is None:
#             return "No graph loaded for querying."
#         G = self.graph

#         try:
#             if query_type == "brokers_for_lease":
#                 lease_id = kwargs.get("lease_id")
#                 lease_node = next((n for n, d in G.nodes(data=True)
#                                    if d.get("type") == "Lease" and (n == lease_id or n.endswith(lease_id))),
#                                   None)
#                 if not lease_node:
#                     return f"Lease {lease_id} not found."

#                 brokers = [G.nodes[n].get("name", n)
#                            for n in G.successors(lease_node)
#                            if G.nodes[n].get("type") == "Broker"]
#                 return brokers or f"No brokers found for lease {lease_node}."

#             elif query_type == "lease_info_by_suite":
#                 node = f"Property-{kwargs['address']}-{kwargs['floor']}-{kwargs['suite']}"
#                 if not G.has_node(node):
#                     return f"Property {node} not found."

#                 leases = [u for u, v in G.edges() if v == node and G.nodes[u].get("type") == "Lease"]
#                 lease_data = [{
#                     "Lease ID": lease_id,
#                     "Annual Rent": G.nodes[lease_id].get("annual_rent"),
#                     "Monthly Rent": G.nodes[lease_id].get("monthly_rent"),
#                     "GCI": G.nodes[lease_id].get("gci"),
#                 } for lease_id in leases]
#                 return lease_data or f"No leases found for {node}."

#             elif query_type == "average_annual_rent":
#                 rents = [self.safe_float(d.get("annual_rent"))
#                          for n, d in G.nodes(data=True) if d.get("type") == "Lease"]
#                 rents = [r for r in rents if r is not None]
#                 if not rents:
#                     return "No valid rent data to compute average."
#                 avg = round(sum(rents) / len(rents), 2)
#                 return f"The average annual rent across all leases is ${avg:,}."

#             elif query_type == "brokers_for_highest_rent_lease":
#                 max_lease = max(
#                     ((n, self.safe_float(d.get("annual_rent")))
#                      for n, d in G.nodes(data=True)
#                      if d.get("type") == "Lease" and self.safe_float(d.get("annual_rent")) is not None),
#                     key=lambda x: x[1],
#                     default=(None, None)
#                 )
#                 lease_node, max_rent = max_lease
#                 if not lease_node:
#                     return "No lease found with valid rent."

#                 brokers = [G.nodes[n].get("name", n)
#                            for n in G.successors(lease_node)
#                            if G.nodes[n].get("type") == "Broker"]
#                 return f"{', '.join(brokers)} handled {lease_node} which has the highest annual rent of ${max_rent:,}."

#             elif query_type == "total_number_of_leases":
#                 total = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "Lease")
#                 return f"There are {total} leases in total."

#             else:
#                 return f"Unsupported query type: {query_type}"

#         except Exception as e:
#             return f"Error in graph query: {e}"

#     def generate(self, prompt, **kwargs):
#         try:
#             if not prompt or not isinstance(prompt, str):
#                 raise ValueError("Prompt must be a non-empty string.")

#             if self.query_agent is None:
#                 return "Query agent not initialized. Load a graph first."

#             query_instructions = self.query_agent.generate_query_from_prompt(prompt)

#             if isinstance(query_instructions, dict):
#                 query_instructions = [query_instructions]

#             responses = []
#             for instruction in query_instructions:
#                 qtype = instruction.get("query_type")
#                 params = instruction.get("params", {})

#                 if qtype == "unsupported":
#                     responses.append("❌ I couldn't understand this part of your request.")
#                     continue

#                 result = self.query_graph(qtype, **params)
#                 responses.append(str(result))

#             enriched_prompt = (
#                 "You are a helpful assistant. Answer the user's query based only on the query results below. "
#                 "Do not ask for clarification. Do not explain your reasoning.\n\n"
#                 f"User question: {prompt}\n\n"
#                 "Query results:\n" + "\n".join(responses)
#             )
#             print("🧠 Gemini query instruction:", query_instructions)


#             response = self.chat.send_message(enriched_prompt, **kwargs)
#             return response.text

#         except Exception as e:
#             return f"Error during generation: {str(e)}"


#     def debug_leases(self, max_items=50):
#         if not self.graph:
#             print("No graph loaded.")
#             return

#         print("\nInspecting Lease Nodes:")
#         count = 0
#         for node, data in self.graph.nodes(data=True):
#             if data.get("type") == "Lease":
#                 print(f"{node} → annual_rent = {data.get('annual_rent')}")
#                 count += 1
#                 if count >= max_items:
#                     break


# Agents/genai_wrapper.py  ─── refactored
import os
from dotenv import load_dotenv
import networkx as nx
import google.generativeai as genai

from Agents.graph_query_agent import GraphQueryAgent
from Agents.prompts import SYSTEM_PROMPT


class GenAIWrapper:
    """
    High-level façade:
    ─ User prompt
        └─► GraphQueryAgent.generate_query_from_prompt()   (LLM → JSON)
            └─► GraphQueryAgent.execute(...)              (run handler on NX graph)
                └─► Result(s) injected back into Gemini   (answer user)
    """

    # ───────────────────────── INIT ──────────────────────────
    def __init__(self, system_prompt: str | None = None):
        load_dotenv()

        self.api_key    = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("MODEL_NAME", "gemini-pro")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY missing in environment")

        self.system_prompt = system_prompt or SYSTEM_PROMPT

        genai.configure(api_key=self.api_key)
        self.chat = genai.GenerativeModel(self.model_name).start_chat(
            history=[{"role": "user", "parts": [self.system_prompt.strip()]}]
        )

        self.graph       = None
        self.query_agent = None

    # ────────────────────── GRAPH LOAD ───────────────────────
    def load_graph(self, path: str):
        try:
            if path.endswith(".graphml"):
                self.graph = nx.read_graphml(path)
            elif path.endswith(".gml"):
                self.graph = nx.read_gml(path)
            else:
                raise ValueError("Unsupported graph format (.graphml | .gml)")

            self.query_agent = GraphQueryAgent(path)
            print(
                f"✅ Graph loaded with "
                f"{self.graph.number_of_nodes()} nodes and "
                f"{self.graph.number_of_edges()} edges."
            )
        except Exception as e:
            print("Error loading graph:", e)

    # ─────────────────── TOP-LEVEL GENERATE ──────────────────
    def generate(self, user_prompt: str, **chat_kwargs):
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            return "Prompt must be a non-empty string."
        if self.query_agent is None:
            return "Graph not loaded. Call load_graph() first."

        # 1️⃣  Translate NL → structured queries
        instructions = self.query_agent.generate_query_from_prompt(user_prompt)

        # 2️⃣  Run each instruction on the graph
        results = []
        for inst in instructions:
            qtype  = inst.get("query_type", "unsupported")
            params = inst.get("params", {})
            if qtype == "unsupported":
                results.append("❌ I couldn’t understand this part of your request.")
                continue
            results.append(str(self.query_agent.execute(qtype, **params)))

        # 3️⃣  Feed the clean results back to Gemini for a final answer
        enriched = (
            "You are a helpful assistant. Answer the user's question **only** "
            "with the information in the query results below. "
            "Do not ask for clarification or expose internal reasoning.\n\n"
            f"User question: {user_prompt}\n\n"
            "Query results:\n" + "\n".join(results)
        )

        print("🧠 Gemini query instruction:", instructions)
        try:
            reply = self.chat.send_message(enriched, **chat_kwargs)
            return reply.text
        except Exception as e:
            return f"Error from Gemini: {e}"

    # ────────────── OPTIONAL DEBUGGING UTILITIES ─────────────
    def debug_leases(self, max_items: int = 50):
        """Quickly inspect the first N lease nodes & annual rent values."""
        if not self.graph:
            print("No graph loaded.")
            return
        print("\nInspecting Lease nodes:")
        shown = 0
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "Lease":
                print(f"{node} → annual_rent = {data.get('annual_rent')}")
                shown += 1
                if shown >= max_items:
                    break
