import os
import pandas as pd
import networkx as nx
from agno import Tool
import google.generativeai as genai
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class CSVTool(Tool):
    def setup(self):
        try:
            self.df = pd.read_csv("./data/HackathonInternalKnowledgeBase.csv")
        except Exception as e:
            raise RuntimeError(f"❌ Failed to load CSV: {e}")

    def query(self, question: str) -> str:
        """Generate Pandas code using Gemini and execute it on the loaded DataFrame."""
        prompt = f"""
            You are working with a CSV file loaded as a Pandas DataFrame called `df`.

            User asked: "{question}"

            Generate only the correct Python code using Pandas to answer the question.
"""
        model = genai.GenerativeModel("gemini-pro")
        try:
            code = model.generate_content(prompt).text.strip("```python").strip("```")
            result = eval(code, {}, {"df": self.df})
            return str(result)
        except Exception as e:
            return f"❌ Error executing generated code:\n{e}\n\n🔍 Generated code:\n{code}"


class KnowledgeGraphTool(Tool):
    def setup(self):
        try:
            self.G = nx.read_graphml("data/lease_graph.graphml")
        except Exception as e:
            raise RuntimeError(f"❌ Failed to load GraphML file: {e}")

    def leases_by_broker(self, broker_name: str) -> str:
        broker_node = f"Broker-{broker_name.replace(' ', '_')}"
        if broker_node not in self.G:
            return f"🔍 Broker '{broker_name}' not found in the graph."

        leases = [
            u for u, v, d in self.G.in_edges(broker_node, data=True)
            if d.get('relation') == 'HANDLED_BY'
        ]
        if leases:
            return f"📄 Leases handled by {broker_name}:\n- " + "\n- ".join(leases)
        else:
            return f"ℹ️ No leases found handled by {broker_name}."

    def describe_lease(self, lease_id: str) -> str:
        node = f"Lease-{lease_id}"
        if node in self.G:
            lease_data = self.G.nodes[node]
            return f"🧾 Lease {lease_id} details:\n" + "\n".join(f"{k}: {v}" for k, v in lease_data.items())
        return f"❌ Lease '{lease_id}' not found."


class GeminiTool(Tool):
    def setup(self):
        self.model = genai.GenerativeModel("gemini-pro")

    def summarize(self, text: str) -> str:
        prompt = f"Summarize the following in simple, plain English:\n\n{text}"
        try:
            return self.model.generate_content(prompt).text.strip()
        except Exception as e:
            return f"❌ Error summarizing: {e}"

    def translate_to_graph_query(self, question: str) -> str:
        prompt = f"""
You are working with a directed graph (NetworkX).
Translate this user question into a Python function or plan to query the graph.

Question: "{question}"
"""
        try:
            return self.model.generate_content(prompt).text.strip()
        except Exception as e:
            return f"❌ Error generating graph query plan: {e}"
