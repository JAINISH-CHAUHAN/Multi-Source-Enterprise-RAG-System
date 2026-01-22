from unstructured.chunking.title import chunk_by_title


def create_chunks_by_title(elements):
    return chunk_by_title(
        elements,
        max_characters=3000,
        new_after_n_chars=2400,
        combine_text_under_n_chars=500,
    )
