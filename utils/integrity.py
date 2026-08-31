"""
FareGuard Data Integrity & Checksum Verification Utilities

Provides robust, chunked cryptographic hashing and file integrity validation.
"""

import hashlib
from pathlib import Path
from typing import Optional, Tuple


def calculate_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """
    Calculates the SHA-256 cryptographic hash of a file using chunked binary streaming.

    Args:
        file_path: Path to the target file.
        chunk_size: Byte size for streaming chunks (default 64KB).

    Returns:
        Hexadecimal SHA-256 digest string.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path is a directory.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found for hash calculation: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"Cannot calculate SHA-256 of directory: {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file_integrity(
    file_path: Path,
    expected_sha256: Optional[str] = None,
    expected_size_bytes: Optional[int] = None,
) -> Tuple[bool, str, dict]:
    """
    Verifies a file's existence, size, and SHA-256 checksum against expected values.

    Returns:
        Tuple of (is_valid: bool, status_message: str, details_dict: dict)
    """
    path = Path(file_path)
    if not path.exists():
        return False, "missing_file", {"error": f"File does not exist: {path}"}

    actual_size = path.stat().st_size
    actual_sha256 = calculate_sha256(path)

    details = {
        "file_path": str(path),
        "actual_size_bytes": actual_size,
        "actual_sha256": actual_sha256,
        "expected_size_bytes": expected_size_bytes,
        "expected_sha256": expected_sha256,
    }

    if expected_size_bytes is not None and actual_size != expected_size_bytes:
        return False, "integrity_mismatch_size", details

    if expected_sha256 is not None and actual_sha256.lower() != expected_sha256.lower():
        return False, "integrity_mismatch_hash", details

    return True, "verified", details
