from Agents.genai_wrapper import GenAIWrapper

wrapper = GenAIWrapper()
wrapper.load_graph()

print(
    wrapper.generate(
        "Who handled the lease with the highest rent and what is the broker's name?"
    )
)

print(wrapper.generate("What is the average annual rent across all leases?"))
