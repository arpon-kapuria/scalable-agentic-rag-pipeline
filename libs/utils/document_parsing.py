from pipelines.ingestion.loaders.docx import parse_docx_bytes
from pipelines.ingestion.loaders.html import parse_html_bytes


def parse_document(file_bytes: bytes, filename: str):
    """
    Routes DOCX/HTML to the correct parser based on file extension. PDF is
    NOT routed here — it returns a different shape (structured elements
    for section-aware chunking, not flat text) and is called directly from
    main.py's process_batch via pipelines/ingestion/loaders/opendataloader_pdf.py.
    DOCX/HTML stay on the old flat-text loaders until a later phase swaps
    them to OpenDataLoader too (Phase 3/4 scope is PDF-only).
    """
    ext = filename.lower().split(".")[-1]

    if ext == "docx":
        return parse_docx_bytes(file_bytes, filename)

    elif ext in ["html", "htm"]:
        return parse_html_bytes(file_bytes, filename)

    else:
        raise ValueError(f"Unsupported file type for parse_document: {ext} (pdf goes through opendataloader_pdf.py)")