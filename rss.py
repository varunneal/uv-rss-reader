# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "rich",
#   "feedparser",
#   "html2text",
#   "python-dateutil",
#   "prompt-toolkit"
# ]
# ///

import locale
import textwrap
from datetime import datetime
import webbrowser
import os
import re
from math import ceil

import feedparser
from dateutil import parser
from rich import box
from rich.markdown import Markdown
from rich.prompt import IntPrompt
from rich.table import Table
from rich.live import Live
from rich.console import Console
from rich.layout import Layout as RichLayout
from rich.panel import Panel
from rich.text import Text

import html2text

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

locale.setlocale(locale.LC_TIME, '')


def slugify(text):
    """Convert text to a URL-friendly slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def get_date(article, pretty=False):
    _date = None
    if publish_date := article.get('published'):
        _date = parser.parse(publish_date)
    elif update_date := article.get('updated'):
        _date = parser.parse(update_date)
    elif not pretty:
        return datetime.now().strftime('%Y-%m-%d')

    if not _date:
        return "No date"
    return _date.strftime("%b %-d, %Y")


def save_as_markdown(article):
    """Save article content as a markdown file"""
    h = html2text.HTML2Text()
    h.ignore_links = False

    if not os.path.exists('articles'):
        os.makedirs('articles')

    title = article.get('title', 'Untitled')
    date = get_date(article, pretty=False)
    filename = f"articles/{date[:10]}-{slugify(title)}.md"

    content = article.get('content', [{'value': article.get('summary', 'No content available')}])[0]['value']
    markdown_content = h.handle(content)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write('---\n')
        f.write(f'title: "{title}"\n')
        f.write(f'date: {date}\n')
        f.write(f'url: {article.get("link", "")}\n')
        f.write('---\n\n')
        f.write(markdown_content)

    return filename


def display_article(article):
    """Display full article content with pagination"""
    console = Console(width=80)
    h = html2text.HTML2Text()
    h.ignore_links = False

    # Convert content to markdown
    content = article.get('content', [{'value': article.get('summary', 'No content available')}])[0]['value']
    markdown_content = h.handle(content)
    lines = markdown_content.split('\n')

    # Pagination
    CONTENT_HEIGHT = console.height - 30
    total_pages = ceil(len(lines) / CONTENT_HEIGHT)
    current_page = 1
    session = PromptSession()

    def get_page_content(page_num):
        """Get content for a specific page"""
        start_idx = (page_num - 1) * CONTENT_HEIGHT
        end_idx = start_idx + CONTENT_HEIGHT
        return '\n'.join(lines[start_idx:end_idx])

    def create_layout():
        """Create the complete layout with header, content, and footer"""
        layout = RichLayout()

        # Header
        header_text = Text()
        header_text.append(str(console.height) + "_ ")
        header_text.append(f"{article.get('title', 'No title')}\n", style="bold blue")
        header_text.append(f"{get_date(article, pretty=True)}\n", style="dim")
        header = Panel(header_text, border_style="blue")

        # Content
        content_text = Text(get_page_content(current_page))
        content_panel = Panel(
            content_text,
            title=f"Page {current_page} of {total_pages}",
            border_style="white"
        )

        # Footer
        footer_text = Text()
        footer_text.append("Navigation:\n", style="bold green")
        footer_text.append(
            "j: prev page | k: next page | o: open | s: save | q: quit")
        footer = Panel(footer_text, border_style="green")

        layout.split(
            RichLayout(header, size=4),
            RichLayout(content_panel),
            RichLayout(footer, size=4)
        )

        return layout

    def handle_command(command):
        """Handle user input commands"""
        nonlocal current_page

        if command == 'q':
            return False
        elif command == 'k' and current_page < total_pages:
            current_page += 1
        elif command == 'j' and current_page > 1:
            current_page -= 1
        elif command == 'o':
            webbrowser.open(article.get('link', ''))
            return True
        elif command == 's':
            filename = save_as_markdown(article)
            console.print(f"\n[green]Article saved as: {filename}[/green]")
            return False

        return True

    with Live(create_layout(), console=console, screen=True, refresh_per_second=4) as live:
        while True:
            # Get user input and clear buffer immediately
            command = session.prompt().lower().strip()

            result = handle_command(command)
            if not result:
                break

            live.update(create_layout())

    return


def truncate_text(text, max_width):
    """Truncate text to fit within max_width, preserving words"""
    if len(text) <= max_width:
        return text
    return text[:max_width - 3] + "..."

def display_feed(feed_url):
    """Display RSS feed content with pagination and fixed layout"""
    console = Console()
    feed = feedparser.parse(feed_url)

    LINES_PER_ENTRY = 3
    HEADER_FOOTER_LINES = 8
    ENTRIES_PER_PAGE = (console.height - HEADER_FOOTER_LINES) // LINES_PER_ENTRY

    total_pages = ceil(len(feed.entries) / ENTRIES_PER_PAGE)
    current_page = 1
    session = PromptSession()

    def get_page_entries(page_num):
        """Get entries for the current page"""
        start_idx = (page_num - 1) * ENTRIES_PER_PAGE
        end_idx = start_idx + ENTRIES_PER_PAGE
        return feed.entries[start_idx:end_idx]


    def create_table(entries):
        """Create table for current page of entries with strictly enforced 3-line height per entry"""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            padding=(0, 1),
            box=box.SIMPLE,
            # show_lines=True
        )

        table.add_column("#", style="dim")
        table.add_column("Date", style="dim")
        table.add_column("Title", style="bold")
        table.add_column("Summary")

        start_idx = (current_page - 1) * ENTRIES_PER_PAGE + 1
        for idx, entry in enumerate(entries, start_idx):
            # Format date
            date = get_date(entry, pretty=True)

            title = entry.get('title', 'No title')
            title = truncate_text(title, 70)

            summary = entry.get('summary', 'No summary')
            summary = summary.replace('<p>', '').replace('</p>', '')
            summary = truncate_text(summary, 120)

            table.add_row(
                str(idx),
                date,
                title,
                summary
            )

        table.row_styles = ["", "dim"]  # Alternate styles for better readability
        return table

    def create_layout():
        """Create the complete layout with header, content, and footer"""
        layout = RichLayout()

        header_text = Text()
        header_text.append(f"{feed.feed.title}\n", style="bold blue")
        header_text.append(f"Page {current_page} of {total_pages}", style="dim")
        header = Panel(header_text, border_style="blue")

        current_entries = get_page_entries(current_page)
        content = Panel(create_table(current_entries), border_style="white")

        footer_text = Text()
        footer_text.append("Options:\n", style="bold green")
        footer_text.append(f"Pick article (1-{len(feed.entries)}) | j: prev page | k: next page | q: quit")
        footer = Panel(footer_text, border_style="green")

        layout.split(
            RichLayout(header, size=4),
            RichLayout(content),
            RichLayout(footer, size=4)
        )
        return layout

    def handle_command(command):
        """Handle user input commands"""
        nonlocal current_page

        if command == 'q':
            return False  # Signal to exit
        elif command == 'k' and current_page < total_pages:
            current_page += 1
        elif command == 'j' and current_page > 1:
            current_page -= 1
        elif command.isdigit():
            article_num = int(command)
            if 1 <= article_num <= len(feed.entries):
                return ('article', article_num)
        return True  # Continue running

    with Live(create_layout(), console=console, screen=True, refresh_per_second=4) as live:
        while True:
            command = session.prompt().lower().strip()

            result = handle_command(command)
            if result is False:
                break
            elif isinstance(result, tuple) and result[0] == 'article':
                live.stop()
                display_article(feed.entries[result[1] - 1])
                live.start()

            live.update(create_layout())
    return


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python rss_reader.py <feed_url>")
        sys.exit(1)

    feed_url = sys.argv[1]
    display_feed(feed_url)

