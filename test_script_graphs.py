from Agents.genai_wrapper import GenAIWrapper

wrapper = GenAIWrapper()
wrapper.load_graph()

# print(
#     wrapper.generate(
#         "Who handled the lease with the highest rent and what is the rent amount?"
#     )
# )

# print(wrapper.generate("What is the average annual rent across all leases?"))

print(wrapper.generate("What are the properties on Broadway?"))
