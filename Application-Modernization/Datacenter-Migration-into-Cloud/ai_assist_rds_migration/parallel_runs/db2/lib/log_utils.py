#!/usr/bin/env python3
"""Logging utilities with sensitive data masking for DRS migration automation."""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from config_loader import LOGS_DIR, ensure_dirs

# Patterns for sensitive data masking
SENSITIVE_PATTERNS = [
    # Match password=xxx, "password": "xxx", etc.
    re.compile(
        r'((?:password|passwd|pwd|secret|key|token|credential)["\'\s]*[:=]\s*["\']?)([^"\'\s,}\]]+)',
        re.IGNORECASE,
    ),
    # Match AK/SK values in JSON
    re.compile(
        r'("(?:access_key|secret_key|ak|sk|accessKey|secretKey)"\s*:\s*")([^"]+)"',
        re.IGNORECASE,
    ),
]

# Keywords that indicate sensitive field names
SENSITIVE_KEYWORDS = frozenset({
    "password", "passwd", "pwd", "secret", "secret_key", "secretkey",
    "access_key", "accesskey", "ak", "sk", "token", "credential",
    "src_db_password", "tgt_db_password", "hw_secret_key", "hw_access_key",
})


def mask_sensitive(text):
    """Mask sensitive information in text.

    Args:
        text: Input text that may contain sensitive data.

    Returns:
        Text with sensitive values replaced by '***'.
    """
    if not isinstance(text, str):
        text = str(text)
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(r'\1***', text)
    return text


def mask_dict(data):
    """Mask sensitive fields in a dictionary.

    Args:
        data: Dictionary that may contain sensitive key-value pairs.

    Returns:
        New dictionary with sensitive values replaced by '***'.
    """
    if not isinstance(data, dict):
        return data
    masked = {}
    for k, v in data.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYWORDS:
            masked[k] = "***"
        elif isinstance(v, dict):
            masked[k] = mask_dict(v)
        elif isinstance(v, str):
            masked[k] = mask_sensitive(v)
        else:
            masked[k] = v
    return masked


class SensitiveFormatter(logging.Formatter):
    """Log formatter that automatically masks sensitive data."""

    def format(self, record):
        msg = super().format(record)
        return mask_sensitive(msg)


def get_logger(script_name):
    """Get a logger with the given script name.

    Args:
        script_name: Name of the script (used in log file name and log prefix).

    Returns:
        A configured logging.Logger instance.
    """
    ensure_dirs()
    logger = logging.getLogger(script_name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = SensitiveFormatter(
        f"[%(asctime)s] [%(levelname)s] [{script_name}] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    # File handler (DEBUG level)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"{script_name}_{timestamp}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = SensitiveFormatter(
        f"[%(asctime)s] [%(levelname)s] [{script_name}] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger


def log_api_call(logger, api_name, request_data=None, response_data=None):
    """Log an API call with sensitive data masked.

    Args:
        logger: Logger instance.
        api_name: Name of the API being called.
        request_data: Request payload (will be masked).
        response_data: Response data (will be masked).
    """
    req_str = ""
    resp_str = ""
    if request_data is not None:
        if isinstance(request_data, dict):
            req_str = json.dumps(mask_dict(request_data), ensure_ascii=False)
        else:
            req_str = mask_sensitive(str(request_data))
    if response_data is not None:
        if isinstance(response_data, dict):
            resp_str = json.dumps(mask_dict(response_data), ensure_ascii=False)
        else:
            resp_str = mask_sensitive(str(response_data))

    logger.debug(f"API Call: {api_name}")
    if req_str:
        logger.debug(f"  Request: {req_str}")
    if resp_str:
        logger.debug(f"  Response: {resp_str}")
