import tiktoken

encoding = tiktoken.get_encoding("o200k_base") # o200k_base is the encoding used by GPT-4o / gpt-realtime family models.
sample_text = "How many tokens does this sentence use?"
#Input token, output token. Input token
print(len(encoding.encode(sample_text)))

