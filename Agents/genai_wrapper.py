
# Agents/genai_wrapper.py  ─── refactored
import os
from dotenv import load_dotenv
from pathlib import Path
import networkx as nx
import google.generativeai as genai

from Agents.graph_query_agent import GraphQueryAgent
from Agents.prompts import SYSTEM_PROMPT

env_path = Path(__file__).parent / ".env"
loaded = load_dotenv(env_path)


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


        self.api_key    = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("MODEL_NAME")
        print(self.api_key)
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
    def load_graph(self, path: str = "./data/lease_graph.graphml"):
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
