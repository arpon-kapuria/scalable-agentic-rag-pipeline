"""
Two-stage split: (1) group markdown text into sections at heading
boundaries (# / ## / ### from OpenDataLoader's markdown output), (2)
recursively character-split within each section only if it exceeds
chunk_size. This is the FloTorch 2026 benchmark's winning approach for
academic papers specifically (recursive 512-token splitting, 69%
end-to-end accuracy on 50 papers, vs 54% for pure semantic chunking) —
section-awareness prevents unrelated sections from bleeding into one
chunk, recursive splitting inside a section avoids the extra inference
cost of semantic chunking for no measured benefit on this document type.

Known limitation, not fixed here: a long section with no sub-headings
(e.g. a "Results" covering several experiments) still gets chunked by
size alone within that section — same limitation flat recursive
splitting always had, just now bounded per-section instead of per-doc.
"""
import re
from typing import Any, Dict, List, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def split_markdown_by_sections(
    markdown_text: str, chunk_size: int = 512, overlap: int = 50
) -> List[Dict[str, Any]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    sections = _group_by_headings(markdown_text)

    chunks = []
    for section_index, (heading_path, content) in enumerate(sections):
        if not content.strip():
            continue

        sub_docs = splitter.create_documents([content])
        for chunk_index, sub_doc in enumerate(sub_docs):
            chunks.append(
                {
                    "text": sub_doc.page_content,
                    "metadata": {
                        "section": heading_path,
                        "section_index": section_index,
                        "chunk_index": chunk_index,
                    },
                }
            )

    return chunks


def _group_by_headings(markdown_text: str) -> List[Tuple[str, str]]:
    """Yields (heading_path, content) tuples. heading_path is e.g.
    'Results > Experiment 2' — built from a stack keyed by heading level
    (# = 1, ## = 2, ...) so nested subsections keep their parent context."""
    heading_stack: List[Tuple[int, str]] = []  # (level, text)
    current_content: List[str] = []
    sections: List[Tuple[str, str]] = []

    def flush():
        if current_content:
            path = " > ".join(h[1] for h in heading_stack) or "Document"
            sections.append((path, "\n".join(current_content)))

    for line in markdown_text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            current_content.clear()
            level = len(match.group(1))
            text = match.group(2).strip()
            # Pop any headings at the same or deeper level — a new ##
            # replaces the previous ## and everything under it.
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
        else:
            current_content.append(line)

    flush()
    return sections
