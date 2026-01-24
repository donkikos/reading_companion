import os
from contextlib import contextmanager
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency
    sync_playwright = None


BASE_URL = os.environ.get("E2E_BASE_URL")
FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_EPUB = FIXTURES_DIR / "minimal.epub"
INVALID_EPUB = FIXTURES_DIR / "invalid.epub"
BOOK_TITLE = "Minimal Fixture"


if sync_playwright is None or not BASE_URL:
    pytest.skip(
        "Playwright not installed or E2E_BASE_URL not set; skipping UI tests.",
        allow_module_level=True,
    )


@contextmanager
def _page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        yield page
        browser.close()


def _upload_epub(page, path):
    file_input = page.locator("#file-upload")
    file_input.set_input_files(str(path))
    page.wait_for_selector("#progress-text")


def _wait_for_book_card(page):
    page.wait_for_selector(f".book-card:has-text('{BOOK_TITLE}')", timeout=120000)
    return page.locator(f".book-card:has-text('{BOOK_TITLE}')")


def test_ui_delete_confirmation_flow():
    with _page() as page:
        _upload_epub(page, VALID_EPUB)
        card = _wait_for_book_card(page)

        page.once("dialog", lambda dialog: dialog.dismiss())
        card.locator("button.delete-btn").click()
        assert card.is_visible() is True

        page.once("dialog", lambda dialog: dialog.accept())
        card.locator("button.delete-btn").click()
        card.wait_for(state="detached", timeout=120000)


def test_ui_ingestion_progress_and_error_state():
    with _page() as page:
        _upload_epub(page, VALID_EPUB)
        _wait_for_book_card(page)

        _upload_epub(page, INVALID_EPUB)
        page.wait_for_function(
            "document.querySelector('#progress-text') && "
            "document.querySelector('#progress-text').innerText.startsWith('Error')",
            timeout=120000,
        )
