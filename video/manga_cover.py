"""
Manga/manhwa cover background fetcher via AniList API.
Fetches cover art matching the post title and uses it as a background.
"""

from rich.console import Console

console = Console()


def get_manga_background(post_title: str, output_dir: str, width: int, height: int) -> str | None:
    """
    Fetch a manga cover image matching the post title via AniList GraphQL API
    and return the local path to the resized background image.

    Returns None if no match found or on any error.
    """
    import os
    import re
    import requests
    from PIL import Image, ImageFilter

    # Only attempt for manga/manhwa-related posts
    keywords = ["manga", "manhwa", "manhua", "chapter", "panel", "scan", "webtoon"]
    title_lower = post_title.lower()
    if not any(kw in title_lower for kw in keywords):
        return None

    # Extract likely manga title from post title
    # Remove common Reddit-style patterns like "[Question]", "(spoilers)", etc.
    clean_title = re.sub(r"[\[\(].*?[\]\)]", "", post_title).strip()
    search_term = clean_title[:50]

    query = """
    query ($search: String) {
      Media(search: $search, type: MANGA) {
        title { romaji english }
        coverImage { extraLarge large }
      }
    }
    """
    try:
        resp = requests.post(
            "https://graphql.anilist.co",
            json={"query": query, "variables": {"search": search_term}},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        media = data.get("data", {}).get("Media")
        if not media:
            return None

        cover_url = (
            media.get("coverImage", {}).get("extraLarge")
            or media.get("coverImage", {}).get("large")
        )
        if not cover_url:
            return None

        # Download cover image
        img_resp = requests.get(cover_url, timeout=15)
        img_resp.raise_for_status()

        os.makedirs(output_dir, exist_ok=True)
        cover_path = os.path.join(output_dir, "_manga_cover.jpg")
        with open(cover_path, "wb") as f:
            f.write(img_resp.content)

        # Resize and blur to fill 9:16 frame
        img = Image.open(cover_path).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=8))

        bg_path = os.path.join(output_dir, "_manga_bg.jpg")
        img.save(bg_path, "JPEG", quality=85)
        return bg_path

    except Exception as e:
        console.print(f"  [dim]Manga cover fetch failed: {e}[/dim]")
        return None
