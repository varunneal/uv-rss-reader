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
import os
import re
import textwrap
import webbrowser
from datetime import datetime
from math import ceil

import feedparser
import html2text
from dateutil import parser
from prompt_toolkit import PromptSession

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

locale.setlocale(locale.LC_TIME, '')


class RSSReader:
    def __init__(self):
        self.console = Console()
        self.session = PromptSession()
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        
    def calculate_text_lines(self, text, width):
        """Calculate how many lines a text will occupy given a width"""
        wrapped_lines = textwrap.wrap(text, width=width)
        return len(wrapped_lines)

    def truncate_text(self, text, max_width):
        """Truncate text to fit within max_width, preserving words"""
        if len(text) <= max_width:
            return text
        return textwrap.shorten(text, width=max_width, placeholder="…")

    def get_date(self, article, pretty=False):
        """Extract and format date from article"""
        for date_field in ('published', 'updated'):
            if date := article.get(date_field):
                try:
                    parsed_date = parser.parse(date)
                    return parsed_date.strftime("%b %-d, %Y") if pretty else parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        return "No date" if pretty else datetime.now().strftime('%Y-%m-%d')

    def save_article(self, article):
        """Save article as markdown file"""
        os.makedirs('articles', exist_ok=True)
        title = article.get('title', 'Untitled')
        date = self.get_date(article)
        filename = f"articles/{date}-{self.slugify(title)}.md"

        content = article.get('content', [{'value': article.get('summary', 'No content')}])[0]['value']
        markdown_content = self.h2t.handle(content)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f'---\ntitle: "{title}"\ndate: {date}\nurl: {article.get("link", "")}\n---\n\n{markdown_content}')
        return filename

    @staticmethod
    def slugify(text):
        """Convert text to URL-friendly slug"""
        text = text.lower()
        return re.sub(r'[-\s]+', '-', re.sub(r'[^\w\s-]', '', text)).strip('-')

    def create_layout(self, header_text, content, footer_text, header_size=4, footer_size=4):
        """Create a standard layout with header, content, and footer"""
        layout = Layout()
        layout.split(
            Layout(Panel(header_text, border_style="blue"), size=header_size),
            Layout(content),
            Layout(Panel(footer_text, border_style="green"), size=footer_size)
        )
        return layout

    def display_article(self, article):
        """Display full article content with pagination"""
        content = article.get('content', [{'value': article.get('summary', 'No content')}])[0]['value']
        lines = self.h2t.handle(content).split('\n')

        content_height = self.console.height - 16
        total_pages = ceil(len(lines) / content_height)
        current_page = 1

        def get_page_content(page):
            start_idx = (page - 1) * content_height
            return '\n'.join(lines[start_idx:start_idx + content_height])

        def create_current_layout():
            header = Text()
            header.append(f"{article.get('title', 'No title')}\n", style="bold blue")
            header.append(f"{self.get_date(article, pretty=True)}", style="dim")

            content_text = Text(get_page_content(current_page))
            content_panel = Panel(content_text, title=f"Page {current_page} of {total_pages}")

            footer = Text("Navigation:\no: open | j: prev page | k: next page | s: save | q: back")
            return self.create_layout(header, content_panel, footer)

        with Live(create_current_layout(), console=self.console, screen=True, refresh_per_second=4) as live:
            while True:
                command = self.session.prompt().lower().strip()

                if command == 'q':
                    break
                elif command == 'k' and current_page < total_pages:
                    current_page += 1
                elif command == 'j' and current_page > 1:
                    current_page -= 1
                elif command == 'o':
                    webbrowser.open(article.get('link', ''))
                elif command == 's':
                    filename = self.save_article(article)
                    self.console.print(f"\n[green]Article saved as: {filename}[/green]")
                    break

                live.update(create_current_layout())

    def display_feed(self, feed_url):
        feed = feedparser.parse(feed_url)
        MAX_SUMMARY_LENGTH, MAX_TITLE_LENGTH = 120, 70
        available_height = self.console.height - 10
        entries = feed.entries

        # Build pages inline
        pages, current_page, current_height = [], [], 1
        for entry in entries:
            summary = entry.get('summary', 'No summary').replace('<p>', '').replace('</p>', '')
            title = entry.get('title', 'No title')
            ttitle = self.truncate_text(title, MAX_TITLE_LENGTH)
            tsum = self.truncate_text(summary, MAX_SUMMARY_LENGTH)
            height = max(
                len(textwrap.wrap(ttitle, width=self.console.width // 4)),
                len(textwrap.wrap(tsum, width=self.console.width // 3))
            )
            if current_page and current_height + height > available_height:
                pages.append(current_page)
                current_page, current_height = [], 1
            current_page.append(entry)
            current_height += height
        if current_page:
            pages.append(current_page)

        def create_table(page_index):
            table = Table(show_header=True, header_style="bold magenta", padding=(0, 1), box=box.SIMPLE)
            table.add_column("#", style="dim")
            table.add_column("Date", style="dim")
            table.add_column("Title", style="bold")
            table.add_column("Summary")
            start_idx = sum(len(p) for p in pages[:page_index])
            for i, e in enumerate(pages[page_index]):
                t = self.truncate_text(e.get('title', 'No title'), MAX_TITLE_LENGTH)
                s = self.truncate_text(e.get('summary', 'No summary').replace('<p>', '').replace('</p>', ''),
                                       MAX_SUMMARY_LENGTH)
                table.add_row(
                    str(i + start_idx + 1),
                    self.get_date(e, pretty=True),
                    t,
                    s
                )
            return table

        cur = 0

        def layout():
            header = Text(f"{feed.feed.title}\n", style="bold blue")
            header.append(f"Page {cur + 1} of {len(pages)}", style="white")
            content = Panel(create_table(cur))
            footer = Text(f"Options:\nPick article (1-{len(entries)}) | j: prev | k: next | q: quit")
            return self.create_layout(header, content, footer)

        with Live(layout(), console=self.console, screen=True, refresh_per_second=4) as live:
            while True:
                cmd = self.session.prompt().lower().strip()
                if cmd == 'q':
                    break
                elif cmd == 'k' and cur < len(pages) - 1:
                    cur += 1
                elif cmd == 'j' and cur > 0:
                    cur -= 1
                elif cmd.isdigit():
                    n = int(cmd)
                    if 1 <= n <= len(entries):
                        live.stop()
                        self.display_article(entries[n - 1])
                        live.start()
                live.update(layout())


def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python rss_reader.py <feed_url>")
        sys.exit(1)

    reader = RSSReader()
    reader.display_feed(sys.argv[1])


if __name__ == "__main__":
    main()
