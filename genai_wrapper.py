import os
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
        self.graph_context = []  # Holds parsed graph text

    def add_rag_documents(self, graph_file_path):
        if not self.enable_rag:
            print("RAG is disabled.")
            return

        # Load graph
        try:
            if graph_file_path.endswith(".graphml"):
                G = nx.read_graphml(graph_file_path)
            elif graph_file_path.endswith(".gml"):
                G = nx.read_gml(graph_file_path)
            else:
                raise ValueError("Unsupported graph file format. Use .gml or .graphml")

            # Convert nodes and edges to text
            chunks = []

            for node, data in G.nodes(data=True):
                chunks.append(f"Node {node}: {data}")

            for u, v, data in G.edges(data=True):
                chunks.append(f"Edge from {u} to {v}: {data}")

            self.graph_context = chunks
            print(f"Loaded {len(chunks)} graph elements into RAG context.")

        except Exception as e:
            print(f"Error loading graph file: {e}")


    def generate(self, prompt, **kwargs):
        try:
            if not prompt or not isinstance(prompt, str):
                raise ValueError("Prompt must be a non-empty string.")

            if self.enable_rag and self.graph_context:
                context = "\n".join(self.graph_context[:50])  # optionally limit size
                prompt = f"{prompt}\n\n---\nRelevant graph context:\n{context}"

            response = self.chat.send_message(prompt, **kwargs)
            return response.text

        except Exception as e:
            return f"Error during generation: {str(e)}"
