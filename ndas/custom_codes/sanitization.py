"""
Input sanitization utilities for NDAS.

Provides functions to sanitize user input to prevent XSS attacks and other
security vulnerabilities. Uses bleach library for HTML sanitization.
"""

import re
import bleach
from pathlib import Path


# Allowed HTML tags and attributes for rich text fields
# Based on common medical/clinical documentation needs
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
    'a', 'span', 'div',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'span': ['class'],
    'div': ['class'],
    'p': ['class'],
    'table': ['class', 'border', 'cellpadding', 'cellspacing'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'tel']


def sanitize_html(html_content: str, strip: bool = False) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.

    Removes potentially dangerous HTML tags and attributes while preserving
    safe formatting tags suitable for medical documentation.

    Args:
        html_content (str): Raw HTML content to sanitize
        strip (bool): If True, strip all disallowed tags instead of escaping them.
                     Defaults to False (escape disallowed tags).

    Returns:
        str: Sanitized HTML content safe for rendering

    Example:
        >>> sanitize_html('<p>Hello</p><script>alert("XSS")</script>')
        '<p>Hello</p>&lt;script&gt;alert("XSS")&lt;/script&gt;'

        >>> sanitize_html('<p>Hello</p><script>alert("XSS")</script>', strip=True)
        '<p>Hello</p>alert("XSS")'
    """
    if not html_content:
        return ''

    # Clean HTML using bleach
    cleaned = bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=strip,
    )

    # Linkify URLs if they're allowed
    if 'a' in ALLOWED_TAGS:
        cleaned = bleach.linkify(
            cleaned,
            parse_email=True,
            skip_tags=['pre', 'code'],
        )

    return cleaned


def sanitize_plain_text(text: str, max_length: int = None) -> str:
    """
    Sanitize plain text by removing HTML tags and normalizing whitespace.

    Suitable for fields that should contain only plain text (names, titles, etc.)
    without any HTML markup.

    Args:
        text (str): Raw text to sanitize
        max_length (int, optional): Maximum length to truncate to. Defaults to None (no limit).

    Returns:
        str: Sanitized plain text

    Example:
        >>> sanitize_plain_text('John <script>alert("XSS")</script> Doe')
        'John  Doe'

        >>> sanitize_plain_text('  Multiple   spaces  ')
        'Multiple spaces'
    """
    if not text:
        return ''

    # Remove all HTML tags
    cleaned = bleach.clean(text, tags=[], strip=True)

    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())

    # Truncate if max_length specified
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(' ', 1)[0] + '...'

    return cleaned


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent directory traversal and other file system attacks.

    Removes potentially dangerous characters and ensures the filename is safe
    for use in the file system.

    Args:
        filename (str): Raw filename to sanitize
        max_length (int): Maximum length for filename. Defaults to 255 (most filesystem limit).

    Returns:
        str: Sanitized filename safe for use in file system

    Example:
        >>> sanitize_filename('../../../etc/passwd')
        'etc_passwd'

        >>> sanitize_filename('my file (2024).pdf')
        'my_file_2024.pdf'

        >>> sanitize_filename('report<script>.pdf')
        'report_script.pdf'
    """
    if not filename:
        return 'unnamed_file'

    # Get the file extension
    path = Path(filename)
    name = path.stem
    ext = path.suffix

    # Remove any path components (prevent directory traversal)
    name = Path(name).name

    # Remove potentially dangerous characters
    # Keep only alphanumeric, underscores, hyphens, and dots
    name = re.sub(r'[^\w\s\-.]', '_', name)

    # Replace multiple underscores/spaces with single underscore
    name = re.sub(r'[_\s]+', '_', name)

    # Remove leading/trailing underscores and dots
    name = name.strip('_.')

    # Ensure we have a valid name
    if not name:
        name = 'unnamed_file'

    # Sanitize extension (remove dots and dangerous characters)
    ext = re.sub(r'[^\w]', '', ext.lower())
    if ext:
        ext = '.' + ext

    # Combine name and extension
    sanitized = name + ext

    # Truncate to max length (accounting for extension)
    if len(sanitized) > max_length:
        max_name_length = max_length - len(ext)
        sanitized = name[:max_name_length] + ext

    return sanitized


def sanitize_sql_like_pattern(pattern: str) -> str:
    """
    Sanitize user input for use in SQL LIKE queries.

    Escapes special characters that have meaning in SQL LIKE patterns
    to prevent SQL injection and unexpected behavior.

    Args:
        pattern (str): Raw pattern to sanitize

    Returns:
        str: Sanitized pattern safe for SQL LIKE queries

    Example:
        >>> sanitize_sql_like_pattern('test%data')
        'test\\%data'

        >>> sanitize_sql_like_pattern('user_name')
        'user\\_name'
    """
    if not pattern:
        return ''

    # Escape special SQL LIKE characters
    # % matches any string, _ matches any single character
    pattern = pattern.replace('\\', '\\\\')  # Escape backslash first
    pattern = pattern.replace('%', '\\%')
    pattern = pattern.replace('_', '\\_')

    return pattern


def sanitize_search_query(query: str, max_length: int = 200) -> str:
    """
    Sanitize search query input to prevent injection attacks.

    Removes special characters that could be used in injection attacks
    while preserving normal search functionality.

    Args:
        query (str): Raw search query
        max_length (int): Maximum query length. Defaults to 200.

    Returns:
        str: Sanitized search query

    Example:
        >>> sanitize_search_query('patient <script>alert("XSS")</script>')
        'patient'

        >>> sanitize_search_query('john  doe   test')
        'john doe test'
    """
    if not query:
        return ''

    # Remove HTML tags
    cleaned = bleach.clean(query, tags=[], strip=True)

    # Remove special characters that could be used in injection
    # Keep alphanumeric, spaces, and basic punctuation for names/terms
    cleaned = re.sub(r'[^\w\s\-.,@()]', '', cleaned)

    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())

    # Truncate to max length
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(' ', 1)[0]

    return cleaned.strip()
