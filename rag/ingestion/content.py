def separate_content_types(chunk):
    content_data = {
        "text": chunk.text,
        "tables": [],
        "images": [],
        "types": ["text"],
    }

    if hasattr(chunk.metadata, "orig_elements"):
        for element in chunk.metadata.orig_elements:
            element_type = type(element).__name__

            if element_type == "Table":
                content_data["types"].append("table")
                content_data["tables"].append(
                    getattr(element.metadata, "text_as_html", element.text)
                )

            elif element_type == "Image":
                if hasattr(element.metadata, "image_base64"):
                    content_data["types"].append("image")
                    content_data["images"].append(element.metadata.image_base64)

    content_data["types"] = list(set(content_data["types"]))
    return content_data
