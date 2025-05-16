import re

def parse_title(html_content: str):
    """Parses HTML content to extract name and track title."""
    if not html_content:
        return "N/A", "N/A"
    text = html_content.replace('<br>', '\n').strip()
    parts = text.split('\n')
    name = parts[0].strip()
    track_title = parts[1].strip() if len(parts) > 1 else "N/A"
    return name, track_title

def is_english(text: str) -> bool:
    """Checks if the given text is predominantly English."""
    if not text:
        return False
    # این یک بررسی ساده است، شاید نیاز به بهبود داشته باشد
    return bool(re.match(r'^[a-zA-Z0-9\s\-_()]+$', text.strip()))