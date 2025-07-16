# Agents/graph_query_agent.py  ─── refactored
import os, re, json, statistics, networkx as nx
from dotenv import load_dotenv
import google.generativeai as genai
from Agents.prompts import SYSTEM_PROMPT_QUERY_TRANSLATOR


class GraphQueryAgent:
    """Translate NL questions ➜ structured query ➜ execute on NetworkX graph."""

    # ──────────────────────────── INIT ──────────────────────────────────────────
    def __init__(self, graph_path: str):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("MODEL_NAME")

        if not api_key:
            raise ValueError("Missing GOOGLE_API_KEY")

        genai.configure(api_key=api_key)
        self.chat   = genai.GenerativeModel(model_name).start_chat(history=[])
        self.graph  = self._load_graph(graph_path)
        self.prompt = SYSTEM_PROMPT_QUERY_TRANSLATOR.strip()

        # ‣ Register handlers -----------------------------------------------------
        self.handlers = {
            # Lease-level
            "average_annual_rent":              self._avg("annual_rent"),
            "average_monthly_rent":             self._avg("monthly_rent"),
            "total_gci_all_leases":             self._sum("gci"),
            "lease_with_highest_annual_rent":   self._extreme("annual_rent", max),
            "lease_with_lowest_annual_rent":    self._extreme("annual_rent", min),
            "lease_with_highest_gci":           self._extreme("gci", max),
            "lease_with_largest_size":          self._extreme("size_sqft", max),
            "lease_with_smallest_size":         self._extreme("size_sqft", min),
            "lease_details_by_id":              self._lease_details_by_id,
            "leases_by_rent_range":             self._leases_by_rent_range,
            "leases_by_gci_threshold":          self._leases_by_gci_threshold,

            # Broker-level
            "brokers_for_lease":                       self._brokers_for_lease,
            "broker_with_most_leases":                 self._top_broker("count"),
            "broker_with_highest_total_rent":          self._top_broker("sum_rent"),
            "broker_with_highest_total_gci":           self._top_broker("sum_gci"),
            "total_gci_by_broker":                     self._total_gci_by_broker,
            # "average_rent_by_broker":                  self._average_rent_by_broker,
            # "leases_by_broker":                        self._leases_by_broker,
            # "properties_by_broker":                    self._properties_by_broker,
            # "brokers_with_shared_properties":          self._brokers_with_shared_properties,
            # "brokers_handling_multiple_properties":    self._brokers_multi_properties,
            "brokers_for_lease_with_lowest_annual_rent": self._brokers_for_extreme_lease("annual_rent", min),
            "brokers_for_lease_with_highest_gci":        self._brokers_for_extreme_lease("gci", max),
            "brokers_for_highest_rent_lease":            self._brokers_for_extreme_lease("annual_rent", max),

            # Property-level
            "lease_info_by_suite":             self._lease_info_by_suite,
            # "leases_for_property":             self._leases_for_property,
            # "total_lease_count_per_property":  self._total_lease_count_per_property,
            # "largest_lease_by_property":       self._largest_lease_by_property,
            # "total_rent_by_property":          self._total_rent_by_property,
            # "average_rent_per_property":       self._average_rent_per_property,
            # "broker_count_per_property":       self._broker_count_per_property,
            # "properties_with_highest_rent":    self._properties_with_highest_rent,
            # "properties_with_highest_gci":     self._properties_with_highest_gci,


            # Aggregates
            "total_number_of_leases":          lambda **_: self._count_nodes("Lease"),
            "total_number_of_brokers":         lambda **_: self._count_nodes("Broker"),
            "total_number_of_properties":      lambda **_: self._count_nodes("Property"),
            "total_lease_area":                self._total_lease_area,
            "average_gci_all_leases":          lambda **_: self._avg("gci")(),
            "average_brokers_per_lease":       self._average_brokers_per_lease,
            "average_leases_per_property":     self._average_leases_per_property,

            # Distributions & lists
            "rent_distribution":               self._distribution("annual_rent"),
            "gci_distribution":                self._distribution("gci"),
            "top_10_highest_rent_leases":      self._top_n("annual_rent", 10, reverse=True),
            "bottom_10_lowest_rent_leases":    self._top_n("annual_rent", 10, reverse=False),
            # "compare_rent_between_brokers":    self._compare_between_brokers("annual_rent"),
            # "compare_gci_between_brokers":     self._compare_between_brokers("gci"),

            # Broker-Property
            # "brokers_by_property":             self._brokers_by_property,
            # "top_broker_per_property":         self._top_broker_per_property,
            # "broker_diversity_by_property":    self._broker_diversity_by_property,

            # Advanced cross-entity
            "broker_for_highest_gci_lease":    self._brokers_for_extreme_lease("gci", max),
            # "property_with_highest_total_rent": self._property_with_highest_total_rent,
            "broker_with_highest_total_gci":    self._top_broker("sum_gci"),
            # "lease_and_broker_with_highest_combined_score": self._lease_broker_highest_score,

            # Meta
            "list_all_brokers":                lambda **_: [n for n,d in self.graph.nodes(data=True) if d["type"]=="Broker"],
            "list_all_leases":                 lambda **_: [n for n,d in self.graph.nodes(data=True) if d["type"]=="Lease"],
            "list_all_properties":             lambda **_: [n for n,d in self.graph.nodes(data=True) if d["type"]=="Property"],
            "list_all_query_types":            lambda **_: list(self.handlers.keys()),
            "graph_summary_stats":             self._graph_summary_stats,
        }

    # ──────────────────── LLM ➜ JSON PARSE ──────────────────────────────────────
    @staticmethod
    def _strip_fences(text: str) -> str:
        return (
            text.replace("```json", "")
                .replace("```", "")
                .strip("`")
                .strip()
        )

    @staticmethod
    def _extract_json(text: str):
        # try whole text
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, list) else [obj]
        except Exception:
            pass
        # fallback greedy regex
        objs = re.findall(r'\{[^{}]+\}', text, flags=re.DOTALL)
        return [json.loads(o) for o in objs if o.strip().startswith("{")]

    def generate_query_from_prompt(self, user_prompt: str):
        prompt = f"{self.prompt}\n\nUser prompt: {user_prompt}"
        resp   = self.chat.send_message(prompt)
        raw    = resp.text
        # print("🔹 RAW LLM:\n", raw)  # ← helpful during dev

        clean  = self._strip_fences(raw)
        blocks = self._extract_json(clean)
        if not blocks:
            return [{"query_type": "unsupported", "params": {}}]

        queries = []
        for b in blocks:
            qt = b.get("query_type", "unsupported")
            queries.append({
                "query_type": qt if qt in self.handlers else "unsupported",
                "params":     b.get("params", {}) if isinstance(b.get("params", {}), dict) else {}
            })
        return queries

    # ────────────────────── PUBLIC EXECUTOR (used by wrapper) ───────────────────
    def execute(self, query_type: str, **params):
        handler = self.handlers.get(query_type)
        if not handler:
            return f"Unsupported query_type: {query_type}"
        try:
            return handler(**params)
        except Exception as e:
            return f"Error while running {query_type}: {e}"

    # ───────────────────────── GRAPH LOAD ───────────────────────────────────────
    def _load_graph(self, path):
        if path.endswith(".graphml"):
            return nx.read_graphml(path)
        if path.endswith(".gml"):
            return nx.read_gml(path)
        raise ValueError("Unsupported graph format")

    # ────────────────────────── HELPER UTILITIES ────────────────────────────────
    @staticmethod
    def _to_float(val):
        try:
            return float(str(val).replace("$", "").replace(",", ""))
        except Exception:
            return None

    def _lease_nodes(self):
        return [(n, d) for n, d in self.graph.nodes(data=True) if d.get("type") == "Lease"]

    def _broker_nodes(self):
        return [(n, d) for n, d in self.graph.nodes(data=True) if d.get("type") == "Broker"]

    # ───────────────────────── GENERIC HANDLER FACTORIES ────────────────────────
    def _avg(self, attr):
        def inner(**_):
            vals = [self._to_float(d.get(attr)) for _, d in self._lease_nodes()]
            vals = [v for v in vals if v is not None]
            return f"Average {attr.replace('_',' ')}: ${statistics.mean(vals):,.2f}" if vals else f"No valid {attr}"
        return inner

    def _sum(self, attr):
        def inner(**_):
            vals = [self._to_float(d.get(attr)) for _, d in self._lease_nodes()]
            vals = [v for v in vals if v is not None]
            return f"Total {attr.replace('_',' ')}: ${sum(vals):,.2f}" if vals else f"No valid {attr}"
        return inner

    def _extreme(self, attr, fn):
        def inner(**_):
            leases = [(n, self._to_float(d.get(attr))) for n, d in self._lease_nodes()]
            leases = [(n,v) for n,v in leases if v is not None]
            if not leases:  return f"No leases contain {attr}"
            node, val = fn(leases, key=lambda x: x[1])
            return f"{node} has the {('highest' if fn is max else 'lowest')} {attr.replace('_',' ')} of ${val:,.2f}"
        return inner

    def _top_n(self, attr, n, reverse=True):
        def inner(**_):
            leases = [(n, self._to_float(d.get(attr))) for n, d in self._lease_nodes()]
            leases = sorted([l for l in leases if l[1] is not None], key=lambda x: x[1], reverse=reverse)[:n]
            return [{ "lease": l, attr: v } for l, v in leases]
        return inner

    def _distribution(self, attr):
        def inner(**_):
            vals = [self._to_float(d.get(attr)) for _, d in self._lease_nodes()]
            vals = [v for v in vals if v is not None]
            return {"min": min(vals), "max": max(vals), "mean": statistics.mean(vals)} if vals else f"No {attr}"
        return inner

    def _brokers_for_extreme_lease(self, attr, fn):
        def inner(**_):
            leases = [(n, self._to_float(d.get(attr))) for n,d in self._lease_nodes()]
            leases = [l for l in leases if l[1] is not None]
            if not leases:  return "No data available"
            lease, val = fn(leases, key=lambda x: x[1])
            brokers = [b for b in self.graph.successors(lease) if self.graph.nodes[b].get("type")=="Broker"]
            names   = [self.graph.nodes[b].get("name", b) for b in brokers]
            return {"lease": lease, attr: val, "brokers": names}
        return inner

    def _top_broker(self, mode):
        def inner(**_):
            stats = {}
            for lease, d in self._lease_nodes():
                brokers = [b for b in self.graph.successors(lease) if self.graph.nodes[b].get("type")=="Broker"]
                for b in brokers:
                    stats.setdefault(b, {"count":0,"sum_rent":0,"sum_gci":0})
                    stats[b]["count"] += 1
                    stats[b]["sum_rent"] += self._to_float(d.get("annual_rent") or 0)
                    stats[b]["sum_gci"]  += self._to_float(d.get("gci") or 0)
            if not stats:
                return "No broker data"
            best = max(stats.items(), key=lambda x: x[1][mode])
            name = self.graph.nodes[best[0]].get("name", best[0])
            return { "broker": name, mode: best[1][mode] }
        return inner

    # ───────────────────────── SPECIFIC HANDLERS ────────────────────────────────
    def _brokers_for_lease(self, lease_id=None, **_):
        lease = next((n for n,_ in self._lease_nodes() if n.endswith(str(lease_id))), None)
        if not lease: return f"Lease {lease_id} not found"
        brokers = [b for b in self.graph.successors(lease) if self.graph.nodes[b].get("type")=="Broker"]
        return [self.graph.nodes[b].get("name", b) for b in brokers] or "No brokers linked"

    def _lease_details_by_id(self, lease_id=None, **_):
        node = next((n for n,_ in self._lease_nodes() if n.endswith(str(lease_id))), None)
        if not node:  return f"Lease {lease_id} not found"
        d = self.graph.nodes[node]
        return {k: d.get(k) for k in ("annual_rent","monthly_rent","gci","size_sqft")}

    def _leases_by_rent_range(self, min_rent=0, max_rent=1e12, **_):
        res = []
        for n,d in self._lease_nodes():
            rent = self._to_float(d.get("annual_rent"))
            if rent is not None and float(min_rent) <= rent <= float(max_rent):
                res.append({"lease": n, "annual_rent": rent})
        return res or "No leases in range"

    def _leases_by_gci_threshold(self, threshold=0, above=True, **_):
        res = []
        for n,d in self._lease_nodes():
            gci = self._to_float(d.get("gci"))
            if gci is not None and ((gci >= float(threshold)) if above else (gci <= float(threshold))):
                res.append({"lease": n, "gci": gci})
        return res or "No leases match criteria"

    def _lease_info_by_suite(self, address=None, floor=None, suite=None, **_):
        node = f"Property-{address}-{floor}-{suite}"
        if not self.graph.has_node(node):
            return f"Property {node} not found"
        leases = [u for u,v in self.graph.edges() if v == node and self.graph.nodes[u]["type"]=="Lease"]
        return [{ "lease": l, **self._lease_details_by_id(lease_id=l) } for l in leases] or "No leases for suite"

    # … (other property & broker helpers similar in style) …

    # ──────────────────────────── META HELPERS ─────────────────────────────────
    def _count_nodes(self, ntype):
        return sum(1 for _,d in self.graph.nodes(data=True) if d.get("type")==ntype)

    def _total_lease_area(self, **_):
        vals = [self._to_float(d.get("size_sqft")) for _,d in self._lease_nodes() if d.get("size_sqft")]
        return f"Total leased area: {sum(vals):,.0f} sqft" if vals else "No size data"

    def _average_brokers_per_lease(self, **_):
        counts = [len([b for b in self.graph.successors(l) if self.graph.nodes[b].get('type')=='Broker'])
                  for l,_ in self._lease_nodes()]
        return statistics.mean(counts) if counts else 0

    def _average_leases_per_property(self, **_):
        props = [n for n,d in self.graph.nodes(data=True) if d.get('type')=='Property']
        counts = [len([u for u,v in self.graph.edges() if v==p and self.graph.nodes[u]['type']=='Lease'])
                  for p in props]
        return statistics.mean(counts) if counts else 0

    def _graph_summary_stats(self, **_):
        return {
            "leases":   self._count_nodes("Lease"),
            "brokers":  self._count_nodes("Broker"),
            "properties": self._count_nodes("Property"),
            "edges":    self.graph.number_of_edges()
        }
    
    # ───── total GCI for one broker ───────────────────────────────
    def _total_gci_by_broker(self, broker_name=None, **_):
        if not broker_name:
            return "Provide broker_name param"

        broker = next(
            (b for b, _ in self._broker_nodes()
             if b == broker_name
             or self.graph.nodes[b].get("name", "").lower() == broker_name.lower()),
            None
        )
        if not broker:
            return f"Broker '{broker_name}' not found"

        total = sum(
            self._to_float(self.graph.nodes[l].get("gci") or 0)
            for l in self.graph.predecessors(broker)
            if self.graph.nodes[l].get("type") == "Lease"
        )
        return {
            "broker": self.graph.nodes[broker].get("name", broker),
            "total_gci": total
        }

