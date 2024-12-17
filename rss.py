# /// script
# dependencies = [
#   "rich",
#   "feedparser",
#   "html2text"
# ]
# ///

import feedparser
from datetime import datetime
import textwrap
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich.prompt import IntPrompt
import html2text
import webbrowser
import os
import re

def slugify(text):
    """Convert text to a URL-friendly slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def save_as_markdown(article):
    """Save article content as a markdown file"""
    h = html2text.HTML2Text()
    h.ignore_links = False
    
    # Create articles directory if it doesn't exist
    if not os.path.exists('articles'):
        os.makedirs('articles')
    
    # Generate filename from title
    title = article.get('title', 'Untitled')
    date = article.get('published', datetime.now().strftime('%Y-%m-%d'))
    filename = f"articles/{date[:10]}-{slugify(title)}.md"
    
    # Get content
    content = article.get('content', [{'value': article.get('summary', 'No content available')}])[0]['value']
    markdown_content = h.handle(content)
    
    # Create markdown file with frontmatter
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('---\n')
        f.write(f'title: "{title}"\n')
        f.write(f'date: {date}\n')
        f.write(f'url: {article.get("link", "")}\n')
        f.write('---\n\n')
        f.write(markdown_content)
    
    return filename

def format_date(date_str):
    """Convert date string to a more readable format"""
    try:
        dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return date_str

def display_article(article):
    """Display full article content"""
    console = Console()
    h = html2text.HTML2Text()
    h.ignore_links = False
    
    while True:
        console.clear()
        console.print(f"\n[bold blue]{article.get('title', 'No title')}[/bold blue]")
        console.print(f"[dim]{format_date(article.get('published', 'No date'))}\n[/dim]")
        
        # Get and convert content
        content = article.get('content', [{'value': article.get('summary', 'No content available')}])[0]['value']
        markdown_content = h.handle(content)
        
        # Display content
        console.print(Markdown(markdown_content))
        
        # Show options
        console.print("\n[bold green]Options:[/bold green]")
        console.print("1. Open in browser")
        console.print("2. Save as markdown")
        console.print("3. Return to list")
        
        choice = IntPrompt.ask("Choose an option", choices=["1", "2", "3"], default="3")
        if choice == 1:
            webbrowser.open(article.get('link', ''))
        elif choice == 2:
            filename = save_as_markdown(article)
            console.print(f"\n[green]Article saved as: {filename}[/green]")
            input("\nPress Enter to continue...")
        else:
            break

def display_feed(feed_url):
    """Display RSS feed content in a formatted table"""
    console = Console()
    
    # Parse the feed
    feed = feedparser.parse(feed_url)
    
    while True:
        console.clear()
        # Create and style the table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Date", style="dim", width=4)
        table.add_column("Title", style="bold", width=10)
        table.add_column("Summary", width=20)
        
        # Add entries to table
        for idx, entry in enumerate(feed.entries, 1):
            date = format_date(entry.get('published', 'No date'))
            title = entry.get('title', 'No title')
            summary = entry.get('summary', 'No summary')
            summary = summary.replace('<p>', '').replace('</p>', '')
            summary = textwrap.shorten(summary, width=150, placeholder="...")
            
            table.add_row(str(idx), date, title, summary)
        
        # Print feed title and table
        console.print(f"\n[bold blue]{feed.feed.title}[/bold blue]\n")
        console.print(table)
        console.print(f"\nTotal entries: [bold green]{len(feed.entries)}[/bold green]")
        
        # Show options
        console.print("\n[bold green]Options:[/bold green]")
        console.print("Enter article number to read (1-{})".format(len(feed.entries)))
        console.print("Or enter 'q' to quit")
        
        choice = input("\nYour choice: ").lower()
        if choice == 'q':
            break
        try:
            article_num = int(choice)
            if 1 <= article_num <= len(feed.entries):
                display_article(feed.entries[article_num - 1])
        except ValueError:
            continue

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python rss_reader.py <feed_url>")
        sys.exit(1)
    
    feed_url = sys.argv[1]
    display_feed(feed_url)


