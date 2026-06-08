"""
Merge and organize files into a single dataset directory.

This script performs the following operations:

1. Scans `noisy_data/pdfs/` and selects only files with a `.pdf` extension.
2. Scans the following directories under `true_data/k8s_docs/`:
   - docx/
   - pdf/
   - html/
   and collects all files from them (no filtering by extension).

3. Moves all selected files into a new directory called `data/`.
   - If the `data/` directory does not exist, it is created automatically.
   - If multiple files share the same name, the script avoids overwriting
     by appending a numeric suffix (e.g., file.pdf → file_1.pdf).

Notes:
- Files are moved, not copied. Original files will no longer remain
  in their source directories after execution.
- The script assumes non-recursive directory structures (only top-level files are processed).
"""


import os
import shutil

DEST_DIR = "data"

# Source directories
NOISY_PDF_DIR = "noisy_data/pdfs"
TRUE_DATA_DIRS = [
    "true_data/k8s_docs/docx",
    "true_data/k8s_docs/pdf",
    "true_data/k8s_docs/html",
]

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_unique_path(dest_path):
    """Avoid overwriting files with same name"""
    base, ext = os.path.splitext(dest_path)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = f"{base}_{counter}{ext}"
        counter += 1
    return dest_path

def move_file(src_path, dest_dir):
    filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, filename)
    dest_path = get_unique_path(dest_path)
    shutil.move(src_path, dest_path)

def main():
    ensure_dir(DEST_DIR)

    # 1. Move only PDFs from noisy_data/pdfs
    for file in os.listdir(NOISY_PDF_DIR):
        if file.lower().endswith(".pdf"):
            src = os.path.join(NOISY_PDF_DIR, file)
            if os.path.isfile(src):
                move_file(src, DEST_DIR)

    # 2. Move all files from true_data subfolders
    for folder in TRUE_DATA_DIRS:
        for file in os.listdir(folder):
            src = os.path.join(folder, file)
            if os.path.isfile(src):
                move_file(src, DEST_DIR)

    print("All files moved successfully to 'data/'")

if __name__ == "__main__":
    main()