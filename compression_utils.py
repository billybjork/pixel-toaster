import re

def extract_target_file_size(query: str) -> int | None:
    """
    Extracts a target file size from the query.
    Looks for patterns like "max file size of 5mb" or "max file size 500kb".
    Returns the size in bytes, or None if not found.
    """
    pattern = r"max file size(?: of)?\s*(\d+(?:\.\d+)?)\s*(kb|mb|gb)"
    match = re.search(pattern, query, re.IGNORECASE)
    if match:
        size = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "kb":
            return int(size * 1024)
        elif unit == "mb":
            return int(size * 1024 * 1024)
        elif unit == "gb":
            return int(size * 1024 * 1024 * 1024)
    return None

def needs_compression(query: str) -> bool:
    """
    Returns True if the query includes any trigger words
    indicating a compression or file size reduction request.
    """
    lower = query.lower()
    return any(trigger in lower for trigger in ["compress", "smaller", "reduce", "minimize"])
