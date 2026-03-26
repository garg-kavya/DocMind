"""Centralized prompt templates."""
from __future__ import annotations

SYSTEM_PROMPT = """\
You are a precise document assistant. Answer questions using ONLY the provided \
source documents. Every factual claim must be supported by citing the source \
with [Source N] where N is the source number.

Rules:
- Base your answer ONLY on the provided context. Do not use prior knowledge.
- Cite every fact with [Source N].
- If the answer is not in the context, say: \
"I could not find relevant information in the uploaded documents."
- Be concise and factual."""

CONTEXT_TEMPLATE = """\
Source Documents:
{context_block}"""

NO_CONTEXT_RESPONSE = (
    "I could not find relevant information in the uploaded documents "
    "to answer your question. Please try rephrasing or ensure the "
    "relevant document has been uploaded."
)

QUERY_REFORMULATION_PROMPT = """\
Given the conversation history below and a follow-up question, rewrite the \
follow-up into a self-contained standalone question that includes all necessary \
context from the history. Do NOT answer — only reformulate.

Conversation history:
{history}

Follow-up question: {question}

Standalone question:"""


def build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks into a numbered source block."""
    parts = []
    for chunk in chunks:
        header = (
            f"[Source {chunk['rank']}] "
            f"({chunk['document_name']}, "
            f"Page {chunk['page_numbers']}, "
            f"Chunk {chunk['chunk_index']})"
        )
        parts.append(f"{header}\n{chunk['text']}")
    return "\n\n".join(parts)
