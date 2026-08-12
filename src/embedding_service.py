# """
# Shared OpenAI embedding service for transcript semantic search.

# This file manages one reusable OpenAI client and converts transcript
# text into vectors that CockroachDB can store and search.

# The workflow is:

# 1. main.py provides OPENAI_API_KEY.
# 2. configure_embedding_client() creates one shared OpenAI client.
# 3. transcripts.py sends transcript text to create_embedding().
# 4. OpenAI converts the text into a numerical embedding.
# 5. to_vector_literal() converts the embedding into CockroachDB format.
# 6. CockroachDB stores the vector with the transcript.
# 7. Semantic search compares new query vectors with stored vectors.
# 8. FastAPI closes the OpenAI client during application shutdown.

# """

# from openai import AsyncOpenAI

# from config import (
#     OPENAI_EMBEDDING_DIMENSIONS,
#     OPENAI_EMBEDDING_MODEL,
#     OPENAI_REQUEST_TIMEOUT_SECONDS,
# )


# # Store one shared OpenAI client for the application.
# #
# # It begins as None because main.py must provide OPENAI_API_KEY before
# # embeddings can be created.
# embedding_client: AsyncOpenAI | None = None


# def configure_embedding_client(
#     api_key: str,
# ) -> AsyncOpenAI:
#     """
#     Create and return the shared OpenAI client.

#     The client is created only once and reused for all embedding
#     requests. Reusing one client avoids opening a new network client
#     for every transcript turn.
#     """

#     global embedding_client

#     if not api_key or not api_key.strip():
#         raise ValueError(
#             "OPENAI_API_KEY cannot be empty."
#         )

#     # Create the client only when it has not already been configured.
#     if embedding_client is None:
#         embedding_client = AsyncOpenAI(
#             api_key=api_key.strip(),

#             # Stop waiting when an OpenAI request takes too long.
#             timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,

#             # Retry temporary network or service failures.
#             max_retries=2,
#         )

#     return embedding_client


# def get_embedding_client() -> AsyncOpenAI:
#     """
#     Return the configured OpenAI client.

#     Raise a clear error when main.py has not configured the client.
#     """

#     if embedding_client is None:
#         raise RuntimeError(
#             "Embedding client is not configured. "
#             "Call configure_embedding_client("
#             "OPENAI_API_KEY) in main.py."
#         )

#     return embedding_client


# async def close_embedding_client():
#     """
#     Close the shared OpenAI client during FastAPI shutdown.

#     This releases the client's underlying network connections.
#     """

#     global embedding_client

#     if embedding_client is None:
#         return

#     await embedding_client.close()
#     embedding_client = None


# def clean_embedding_text(
#     text: str,
# ) -> str:
#     """
#     Clean and validate one text value before embedding it.

#     Surrounding spaces are removed. Blank text is rejected.
#     """

#     if not isinstance(text, str):
#         raise TypeError(
#             "Embedding text must be a string."
#         )

#     cleaned_text = text.strip()

#     if not cleaned_text:
#         raise ValueError(
#             "Embedding text cannot be empty."
#         )

#     return cleaned_text


# async def create_embeddings(
#     texts: list[str],
# ) -> list[list[float]]:
#     """
#     Create one embedding for every text value in a list.

#     This helper supports tests and future batch processing. The normal
#     production transcript flow usually calls create_embedding() for
#     one transcript turn at a time.
#     """

#     if not texts:
#         raise ValueError(
#             "At least one text value is required."
#         )

#     # Clean every text value before sending it to OpenAI.
#     cleaned_texts = [
#         clean_embedding_text(text)
#         for text in texts
#     ]

#     # Send all supplied text values in one OpenAI request.
#     response = (
#         await get_embedding_client()
#         .embeddings.create(
#             model=OPENAI_EMBEDDING_MODEL,
#             input=cleaned_texts,
#             dimensions=(
#                 OPENAI_EMBEDDING_DIMENSIONS
#             ),
#         )
#     )

#     # OpenAI returns an index for each result.
#     # Sort by that index to preserve the original input order.
#     ordered_results = sorted(
#         response.data,
#         key=lambda item: item.index,
#     )

#     vectors = [
#         item.embedding
#         for item in ordered_results
#     ]

#     # Confirm that OpenAI returned one vector per text value.
#     if len(vectors) != len(cleaned_texts):
#         raise RuntimeError(
#             "Embedding result count does not "
#             "match input count."
#         )

#     # Confirm every vector fits the CockroachDB VECTOR column.
#     for vector in vectors:
#         if (
#             len(vector)
#             != OPENAI_EMBEDDING_DIMENSIONS
#         ):
#             raise RuntimeError(
#                 "Embedding dimension mismatch. "
#                 f"Expected "
#                 f"{OPENAI_EMBEDDING_DIMENSIONS}, "
#                 f"but received {len(vector)}."
#             )

#     return vectors


# async def create_embedding(
#     text: str,
# ) -> list[float]:
#     """
#     Create one embedding for one transcript or search query.

#     transcripts.py uses this function when:
#     - saving a transcript turn
#     - updating transcript text
#     - running semantic search
#     """

#     vectors = await create_embeddings(
#         [text]
#     )

#     return vectors[0]


# def to_vector_literal(
#     vector: list[float],
# ) -> str:
#     """
#     Convert a Python vector into CockroachDB VECTOR text format.

#     Example:

#         [0.12, -0.45, 0.78]

#     becomes:

#         "[0.12,-0.45,0.78]"
#     """

#     if (
#         len(vector)
#         != OPENAI_EMBEDDING_DIMENSIONS
#     ):
#         raise ValueError(
#             "Vector dimension mismatch. "
#             f"Expected "
#             f"{OPENAI_EMBEDDING_DIMENSIONS}, "
#             f"but received {len(vector)}."
#         )

#     # Use compact numeric formatting before building the SQL value.
#     values = [
#         format(value, ".10g")
#         for value in vector
#     ]

#     return "[" + ",".join(values) + "]"