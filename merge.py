from pathlib import Path

# ========================
# CONFIG
# ========================

INPUT_DIRS = [
    Path("data"),
    Path("src/iFactory"),
]

TEXT_EXTENSIONS = {
    ".txt",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".csv",
    ".sql",
    ".xml",
    ".ini",
    ".toml",
    ".ui",
    ".qss",
    ".qrc",
    ".cfg",
}

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "node_modules",
    ".vscode",
    "dist",
    "build",
}

MAX_LINES = 5000
BOUNDARY = "\n" + "=" * 80 + "\n"


# ========================
# HELPERS
# ========================


def is_valid_file(file: Path) -> bool:
    if not file.is_file():
        return False

    if file.suffix.lower() not in TEXT_EXTENSIONS:
        return False

    for part in file.parts:
        if part in EXCLUDE_DIRS or part.endswith(".egg-info"):
            return False

    return True


def safe_read_text(file: Path) -> str:
    try:
        return file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "# [SKIPPED: encoding error or binary file]\n"


def render_file_block(base: Path, file: Path) -> str:
    relative_path = file.relative_to(base)

    header = f"{BOUNDARY}" f"```python\n" f"# File: {relative_path.as_posix()}\n"

    content = safe_read_text(file)

    footer = "\n```\n"

    return header + content.rstrip() + footer + "\n"


# ========================
# COLLECT FILES
# ========================

all_files: list[tuple[Path, Path]] = []

for base in INPUT_DIRS:
    if not base.exists():
        continue

    for f in sorted(base.rglob("*")):
        if is_valid_file(f):
            all_files.append((base, f))

if not all_files:
    print("Không tìm thấy file nào phù hợp.")
    raise SystemExit(0)


# ========================
# WRITE SPLIT FILES
# ========================

file_index = 1
current_lines = 0

out = Path(f"code_{file_index}.txt").open("w", encoding="utf-8")

out.write(
    "PROJECT SOURCE SNAPSHOT\n"
    "PURPOSE: AI analysis / refactor / production hardening\n"
    f"MAX_LINES_PER_FILE: {MAX_LINES}\n"
    f"SOURCE_ROOTS: {', '.join(str(p) for p in INPUT_DIRS)}\n"
    f"{BOUNDARY}"
)

for base, file in all_files:
    block = render_file_block(base, file)
    block_lines = block.count("\n") + 1

    if current_lines > 0 and current_lines + block_lines > MAX_LINES:
        out.close()
        file_index += 1
        current_lines = 0

        out = Path(f"code_{file_index}.txt").open("w", encoding="utf-8")
        out.write(
            "PROJECT SOURCE SNAPSHOT (CONTINUED)\n"
            f"PART: code_{file_index}.txt\n"
            f"{BOUNDARY}"
        )

    out.write(block)
    current_lines += block_lines

out.close()

print(f"Hoàn tất! Đã tạo {file_index} file: code_1.txt → code_{file_index}.txt")
