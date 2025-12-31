import re
import unicodedata


def sanitize_filename(filename: str) -> str:
    """파일명을 안전한 ASCII 문자열로 변환."""
    if not filename:
        return "converted"

    name_without_ext = filename.rsplit(".", 1)[0]
    normalized = unicodedata.normalize("NFKD", name_without_ext)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", ascii_name)
    safe_name = re.sub(r"_+", "_", safe_name)
    safe_name = safe_name.strip("_")

    if not safe_name:
        safe_name = "converted"

    if len(safe_name) > 50:
        safe_name = safe_name[:50]

    return safe_name
