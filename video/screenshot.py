"""
Reddit screenshot capture using Playwright.

Navigates to actual Reddit posts and captures screenshots of
the post title and individual comments, just like the original
RedditVideoMakerBot. No API key needed - uses browser directly.
"""

import os
from pathlib import Path

from rich.console import Console

console = Console()


def capture_post_screenshots(
    post,
    segments: list[dict],
    output_dir: str,
    theme: str = "dark",
    **kwargs,
) -> list[dict]:
    """
    Capture Reddit post/comment screenshots using Playwright.

    For Reddit posts: navigates to the actual Reddit page and screenshots elements.
    For text file posts: falls back to Pillow card rendering.

    Args:
        post: RedditPost or TextFilePost
        segments: TTS segments list
        output_dir: Directory to save PNG screenshots
        theme: "dark" or "light"

    Returns:
        segments with 'card_path' added to each entry
    """
    os.makedirs(output_dir, exist_ok=True)

    # Check if this is a real Reddit post (has a valid URL/permalink)
    has_reddit_url = (
        hasattr(post, "url")
        and post.url
        and ("reddit.com" in post.url or post.id and len(post.id) < 15)
    )

    # Use Pillow card renderer: produces clean, readable individual cards
    # (Playwright Reddit screenshots capture the entire comment thread DOM
    # including all replies, resulting in unreadable full-page screenshots)
    from video.card_renderer import render_cards_for_post
    return render_cards_for_post(
        post, segments, output_dir,
        font_path=kwargs.get("font_path"),
        title_font_size=kwargs.get("title_font_size", 48),
        comment_font_size=kwargs.get("comment_font_size", 40),
    )


def _capture_from_reddit(
    post,
    segments: list[dict],
    output_dir: str,
    theme: str = "dark",
) -> list[dict]:
    """Capture actual Reddit screenshots using Playwright."""
    from playwright.sync_api import sync_playwright

    console.print("  [cyan]Capturing Reddit screenshots via Playwright...[/cyan]")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--ignore-certificate-errors",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        color_scheme = "dark" if theme == "dark" else "light"

        context = browser.new_context(
            viewport={"width": 800, "height": 2000},
            device_scale_factor=2,
            color_scheme=color_scheme,
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Inject JS before any page script to hide webdriver fingerprint
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        context.add_cookies([{
            "name": "over18",
            "value": "1",
            "domain": ".reddit.com",
            "path": "/",
        }])

        page = context.new_page()

        # Use old Reddit which is simpler HTML and less likely to be blocked
        post_url = f"https://old.reddit.com/comments/{post.id}"
        console.print(f"  [dim]Navigating to: {post_url}[/dim]")
        page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Detect Cloudflare / network security block
        page_text = page.evaluate("() => document.body ? document.body.innerText : ''")
        if any(phrase in page_text for phrase in [
            "blocked by network security",
            "cf-error",
            "Enable JavaScript and cookies",
            "Checking your browser",
            "Just a moment",
        ]):
            browser.close()
            raise RuntimeError("Reddit page blocked by security (Cloudflare). Falling back to card renderer.")

        if theme == "dark":
            page.evaluate("""
                document.cookie = 'theme=dark; domain=.reddit.com; path=/';
            """)

        # Try to dismiss any popups/banners
        _dismiss_popups(page)

        # Screenshot the post title/content
        title_path = os.path.join(output_dir, "card_00.png")
        _screenshot_post_title(page, title_path)

        if os.path.exists(title_path):
            for seg in segments:
                if seg.get("type") == "title":
                    seg["card_path"] = title_path
                    break

        # Screenshot each comment
        comment_idx = 0
        for i, seg in enumerate(segments):
            if seg.get("type") != "comment":
                if seg.get("type") == "body" and not seg.get("card_path"):
                    # Body text - use title screenshot or render card
                    seg["card_path"] = title_path if os.path.exists(title_path) else None
                continue

            comment_id = None
            # Try to find the comment by matching text in post.comments
            if comment_idx < len(post.comments):
                comment_id = post.comments[comment_idx].id
                comment_idx += 1

            card_path = os.path.join(output_dir, f"card_{i:02d}.png")

            if comment_id:
                success = _screenshot_comment(page, comment_id, card_path)
                if success:
                    seg["card_path"] = card_path
                    continue

            # Fallback for this comment: render with Pillow
            from video.card_renderer import render_comment_card
            card_img = render_comment_card(
                body=seg["text"],
                author=seg.get("author", "Anonymous"),
                score=seg.get("score", 0),
            )
            card_img.save(card_path, "PNG")
            seg["card_path"] = card_path

        browser.close()

    # Fill any segments missing card_path with Pillow fallback
    _fill_missing_cards(segments, output_dir)

    captured = sum(1 for s in segments if s.get("card_path"))
    console.print(f"  [green][OK][/green] Captured {captured} screenshot(s)")
    return segments


def _dismiss_popups(page):
    """Try to dismiss common Reddit popups and overlays."""
    try:
        # Dismiss cookie consent
        for selector in [
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("Reject non-essential")',
            '[data-testid="close-button"]',
        ]:
            elem = page.locator(selector).first
            if elem.is_visible(timeout=1000):
                elem.click()
                page.wait_for_timeout(500)
    except Exception:
        pass

    try:
        # Dismiss "Use App" / login prompts
        for selector in [
            'button:has-text("Continue")',
            'button:has-text("Not now")',
            'shreddit-experience-tree',
        ]:
            elem = page.locator(selector).first
            if elem.is_visible(timeout=500):
                elem.click()
                page.wait_for_timeout(300)
    except Exception:
        pass


def _screenshot_post_title(page, output_path: str) -> bool:
    """Screenshot the post title/content area."""
    # old.reddit.com selectors first, then new Reddit (shreddit)
    selectors = [
        ".thing.link",           # old Reddit post container
        "#siteTable .thing",     # old Reddit
        ".Post",                 # new Reddit
        "shreddit-post",         # new Reddit shreddit
        '[data-testid="post-container"]',
        '[data-test-id="post-content"]',
        "article",
    ]

    for selector in selectors:
        if not selector:
            continue
        try:
            elem = page.locator(selector).first
            if elem.is_visible(timeout=2000):
                # Scroll element into view and screenshot
                elem.scroll_into_view_if_needed(timeout=2000)
                elem.screenshot(path=output_path)
                console.print(f"  [green][OK][/green] Post title screenshot ({selector})")
                return True
        except Exception:
            continue

    # Fallback: scroll to top, wait for content, then crop below the header
    try:
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        # Try to find the post content bounding box to crop precisely
        post_y = page.evaluate("""() => {
            const selectors = ['shreddit-post', 'article', '[data-test-id="post-content"]'];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    return { y: Math.max(0, rect.top), height: Math.min(rect.height, 800) };
                }
            }
            return { y: 80, height: 600 };
        }""")

        y = int(post_y.get("y", 80))
        h = int(post_y.get("height", 600))
        h = max(200, min(h, 900))

        page.screenshot(
            path=output_path,
            clip={"x": 0, "y": y, "width": 800, "height": h},
        )
        console.print(f"  [dim]Post title: used page crop fallback (y={y}, h={h})[/dim]")
        return True
    except Exception as e:
        console.print(f"  [yellow]Post title screenshot failed: {e}[/yellow]")
        return False


def _screenshot_comment(page, comment_id: str, output_path: str) -> bool:
    """Screenshot a specific comment by ID."""
    selectors = [
        f"#thing_t1_{comment_id}",              # old Reddit
        f".comment[data-fullname='t1_{comment_id}']",  # old Reddit
        f"#t1_{comment_id}",
        f'[thingid="t1_{comment_id}"]',
        f'shreddit-comment[thingid="t1_{comment_id}"]',
    ]

    for selector in selectors:
        try:
            elem = page.locator(selector).first
            if elem.is_visible(timeout=2000):
                elem.screenshot(path=output_path)
                return True
        except Exception:
            continue

    return False


def _fill_missing_cards(segments: list[dict], output_dir: str):
    """Fill any segments missing card_path with Pillow-rendered cards."""
    from video.card_renderer import render_title_card, render_comment_card

    for i, seg in enumerate(segments):
        if seg.get("card_path") and os.path.exists(seg["card_path"]):
            continue

        card_path = os.path.join(output_dir, f"card_{i:02d}.png")

        if seg.get("type") == "title":
            card_img = render_title_card(
                title=seg["text"],
                author=seg.get("author", "Author"),
                score=seg.get("score", 0),
                subreddit=seg.get("subreddit", "roblox"),
            )
        else:
            card_img = render_comment_card(
                body=seg["text"],
                author=seg.get("author", "Anonymous"),
                score=seg.get("score", 0),
            )

        card_img.save(card_path, "PNG")
        seg["card_path"] = card_path
