"""Error classification helpers for BDI modules."""


def is_validation_output_error(error: Exception) -> bool:
    """Return True when an exception indicates structured output validation issues."""
    error_msg = str(error).lower()
    return "output validation" in error_msg or "validation error" in error_msg


__all__ = [
    "is_validation_output_error",
]
