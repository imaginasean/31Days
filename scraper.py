"""
Web scraper for 31 Days of Vibe Coding articles.
Fetches articles from https://31daysofvibecoding.com and extracts content.
"""

import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


@dataclass
class Article:
    """Represents a single article from the 31 Days series."""
    day: int
    title: str
    date: str
    url: str
    content: str
    prev_url: Optional[str] = None
    next_url: Optional[str] = None


class VibeCodingScraper:
    """Scraper for 31 Days of Vibe Coding website."""
    
    BASE_URL = "https://31daysofvibecoding.com"
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize the scraper.
        
        Args:
            delay: Seconds to wait between requests (be respectful to the server)
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Podcast Generator Bot)"
        })
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a page and return parsed BeautifulSoup object.
        
        Args:
            url: URL to fetch
            
        Returns:
            BeautifulSoup object or None if fetch failed
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            time.sleep(self.delay)  # Be respectful
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def discover_article_urls(self) -> list[str]:
        """
        Discover all article URLs by crawling from a known article.
        
        Returns:
            List of article URLs in order (Day 1 to Day 31)
        """
        # Start with the home page to find any article link
        print("Discovering article URLs...")
        
        # Known URL pattern: /2026/01/DD/slug/
        # We'll try to find articles by checking common patterns
        discovered = {}
        
        # First, try to find articles from the homepage
        soup = self.fetch_page(self.BASE_URL)
        if soup:
            # Find any links that match the article pattern
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/2026/01/" in href:
                    full_url = urljoin(self.BASE_URL, href)
                    day = self._extract_day_from_url(full_url)
                    if day:
                        discovered[day] = full_url
        
        # Crawl from discovered articles to find more
        urls_to_check = list(discovered.values())
        checked = set()
        
        while urls_to_check:
            url = urls_to_check.pop(0)
            if url in checked:
                continue
            checked.add(url)
            
            soup = self.fetch_page(url)
            if not soup:
                continue
            
            # Find navigation links (prev/next)
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text().lower()
                
                # Check for article links
                if "/2026/01/" in href:
                    full_url = urljoin(self.BASE_URL, href)
                    day = self._extract_day_from_url(full_url)
                    if day and day not in discovered:
                        discovered[day] = full_url
                        urls_to_check.append(full_url)
                        print(f"  Found Day {day}: {full_url}")
            
            # Stop if we've found all 31 days
            if len(discovered) >= 31:
                break
        
        # Sort by day number and return URLs
        sorted_days = sorted(discovered.keys())
        return [discovered[day] for day in sorted_days]
    
    def _extract_day_from_url(self, url: str) -> Optional[int]:
        """Extract day number from URL based on date pattern."""
        # Pattern: /2026/01/DD/
        match = re.search(r"/2026/01/(\d{2})/", url)
        if match:
            return int(match.group(1))
        return None
    
    def parse_article(self, url: str) -> Optional[Article]:
        """
        Parse a single article page.
        
        Args:
            url: Article URL
            
        Returns:
            Article object or None if parsing failed
        """
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        # Extract title (usually in h1)
        title_tag = soup.find("h1")
        title = title_tag.get_text().strip() if title_tag else "Unknown Title"
        
        # Extract day number from title or URL
        day_match = re.search(r"Day\s+(\d+)", title)
        if day_match:
            day = int(day_match.group(1))
        else:
            day = self._extract_day_from_url(url) or 0
        
        # Extract date
        date = ""
        date_pattern = re.compile(r"Jan\s+\d+,\s+2026")
        for text in soup.stripped_strings:
            if date_pattern.search(text):
                date = date_pattern.search(text).group()
                break
        
        # Extract main content
        content = self._extract_content(soup)
        
        # Find navigation links
        prev_url = None
        next_url = None
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text().lower()
            if "←" in text or "prev" in text or "day " in text and int(re.search(r"day\s+(\d+)", text).group(1) if re.search(r"day\s+(\d+)", text) else "0") < day:
                if "/2026/01/" in href:
                    prev_url = urljoin(self.BASE_URL, href)
            elif "→" in text or "next" in text:
                if "/2026/01/" in href:
                    next_url = urljoin(self.BASE_URL, href)
        
        return Article(
            day=day,
            title=title,
            date=date,
            url=url,
            content=content,
            prev_url=prev_url,
            next_url=next_url
        )
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """
        Extract the main article content from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Raw HTML content of the article
        """
        # Remove navigation, header, footer, etc.
        for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()
        
        # Try to find the main content area
        # Look for article tag or main content div
        main_content = soup.find("article")
        if not main_content:
            main_content = soup.find("main")
        if not main_content:
            # Fall back to the body
            main_content = soup.find("body")
        
        if main_content:
            return str(main_content)
        
        return str(soup)
    
    def scrape_all(self) -> list[Article]:
        """
        Scrape all 31 articles.
        
        Returns:
            List of Article objects
        """
        urls = self.discover_article_urls()
        print(f"\nFound {len(urls)} articles. Starting to scrape...")
        
        articles = []
        for i, url in enumerate(urls, 1):
            print(f"Scraping article {i}/{len(urls)}: {url}")
            article = self.parse_article(url)
            if article:
                articles.append(article)
                print(f"  ✓ {article.title}")
            else:
                print(f"  ✗ Failed to parse")
        
        return articles


def main():
    """Test the scraper."""
    scraper = VibeCodingScraper(delay=1.0)
    
    # Test with a single known article
    print("Testing scraper with Day 7 article...")
    article = scraper.parse_article("https://31daysofvibecoding.com/2026/01/07/context-management/")
    
    if article:
        print(f"\nTitle: {article.title}")
        print(f"Day: {article.day}")
        print(f"Date: {article.date}")
        print(f"Content length: {len(article.content)} chars")
        print(f"Prev URL: {article.prev_url}")
        print(f"Next URL: {article.next_url}")
    else:
        print("Failed to parse article")


if __name__ == "__main__":
    main()
