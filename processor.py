"""
Content processor for converting HTML articles to audio-friendly text.
Handles code block summarization and text cleanup for TTS.
"""

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, NavigableString


@dataclass
class ProcessedArticle:
    """Article processed for audio conversion."""
    day: int
    title: str
    date: str
    text: str
    char_count: int
    word_count: int


class ContentProcessor:
    """Processes HTML content into audio-friendly text."""
    
    # Language names for code block descriptions
    LANGUAGE_NAMES = {
        "python": "Python",
        "py": "Python",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "jsx": "JavaScript",
        "typescript": "TypeScript",
        "ts": "TypeScript",
        "tsx": "TypeScript",
        "bash": "Bash",
        "sh": "shell",
        "shell": "shell",
        "sql": "SQL",
        "json": "JSON",
        "html": "HTML",
        "css": "CSS",
        "yaml": "YAML",
        "yml": "YAML",
        "markdown": "Markdown",
        "md": "Markdown",
        "git": "Git",
        "": "code",
    }
    
    def __init__(
        self,
        summarize_code: bool = True,
        use_llm: bool = False,
        llm_summarizer=None,
        force_resummarize: bool = False
    ):
        """
        Initialize the processor.
        
        Args:
            summarize_code: If True, summarize code blocks. If False, skip them entirely.
            use_llm: If True, use LLM for code summarization (requires llm_summarizer).
            llm_summarizer: CodeSummarizer instance for LLM-based summarization.
            force_resummarize: If True, ignore cache and regenerate all summaries.
        """
        self.summarize_code = summarize_code
        self.use_llm = use_llm
        self.llm_summarizer = llm_summarizer
        self.force_resummarize = force_resummarize
        self._current_context = ""  # Set during processing for LLM context
    
    def process(self, html_content: str, day: int, title: str, date: str) -> ProcessedArticle:
        """
        Process HTML content into audio-friendly text.
        
        Args:
            html_content: Raw HTML content
            day: Day number
            title: Article title
            date: Article date
            
        Returns:
            ProcessedArticle with cleaned text
        """
        # Set context for LLM summarization
        clean_title = re.sub(r"^Day\s+\d+:\s*", "", title)
        self._current_context = clean_title
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove unwanted elements
        self._remove_unwanted_elements(soup)
        
        # Process code blocks before extracting text
        self._process_code_blocks(soup)
        
        # Extract and clean text
        text = self._extract_text(soup)
        
        # Clean up the text for audio
        text = self._clean_for_audio(text)
        
        # Add intro
        intro = self._create_intro(day, title, date)
        full_text = f"{intro}\n\n{text}"
        
        # Add outro
        outro = self._create_outro(day)
        full_text = f"{full_text}\n\n{outro}"
        
        return ProcessedArticle(
            day=day,
            title=title,
            date=date,
            text=full_text,
            char_count=len(full_text),
            word_count=len(full_text.split())
        )
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove elements that shouldn't be in the audio version."""
        # Remove scripts, styles, navigation
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        
        # Remove subscription forms
        for form in soup.find_all("form"):
            form.decompose()
        
        # Remove image tags (can't read images)
        for img in soup.find_all("img"):
            img.decompose()
        
        # Remove "Get new articles in your inbox" section and similar
        for element in soup.find_all(string=re.compile(r"Get new articles|Subscribe|Unsubscribe", re.I)):
            parent = element.find_parent()
            if parent:
                # Try to find the containing section
                section = parent.find_parent(["div", "section", "aside"])
                if section:
                    section.decompose()
                else:
                    parent.decompose()
    
    def _process_code_blocks(self, soup: BeautifulSoup) -> None:
        """Replace code blocks with audio-friendly descriptions."""
        # Handle <pre><code> blocks
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                code_text = code.get_text()
                language = self._detect_language(code)
                description = self._describe_code_block(code_text, language)
                
                # Replace with description paragraph
                new_p = soup.new_tag("p")
                new_p.string = description
                pre.replace_with(new_p)
            else:
                # Pre without code - just describe as a code example
                code_text = pre.get_text()
                description = self._describe_code_block(code_text, "")
                new_p = soup.new_tag("p")
                new_p.string = description
                pre.replace_with(new_p)
        
        # Handle inline code (backticks) - keep them but clean up
        for code in soup.find_all("code"):
            # For inline code, just keep the text
            code_text = code.get_text()
            code.replace_with(code_text)
    
    def _detect_language(self, code_tag) -> str:
        """Detect the programming language from code tag classes."""
        classes = code_tag.get("class", [])
        for cls in classes:
            if cls.startswith("language-"):
                return cls.replace("language-", "")
            if cls.startswith("lang-"):
                return cls.replace("lang-", "")
        return ""
    
    def _describe_code_block(self, code_text: str, language: str) -> str:
        """
        Create an audio-friendly description of a code block.
        
        Args:
            code_text: The actual code
            language: Detected programming language
            
        Returns:
            A spoken description of what the code does
        """
        if not self.summarize_code:
            lang_name = self.LANGUAGE_NAMES.get(language.lower(), language or "code")
            return f"[{lang_name} code example - see the article for details]"
        
        # Use LLM summarizer if available
        if self.use_llm and self.llm_summarizer:
            try:
                summary = self.llm_summarizer.summarize(
                    code=code_text,
                    language=language,
                    context=self._current_context,
                    force_refresh=self.force_resummarize
                )
                return summary
            except Exception as e:
                print(f"    Warning: LLM summarization failed, using fallback: {e}")
                # Fall through to rule-based summarization
        
        # Fallback: Rule-based summarization
        return self._rule_based_summary(code_text, language)
    
    def _rule_based_summary(self, code_text: str, language: str) -> str:
        """
        Create a rule-based summary of code (fallback when LLM is not available).
        
        Args:
            code_text: The actual code
            language: Detected programming language
            
        Returns:
            A natural, audio-friendly description of what the code does
        """
        # Get friendly language name
        lang_name = self.LANGUAGE_NAMES.get(language.lower(), language or "code")
        lines = code_text.strip().split("\n")
        num_lines = len(lines)
        
        # For template-style code with markdown headers, extract key sections
        if "##" in code_text or "**" in code_text:
            headers = re.findall(r"(?:##\s*|^\*\*)([\w\s]+)(?:\*\*)?", code_text, re.MULTILINE)
            if headers:
                sections = ", ".join(h.strip() for h in headers[:4])
                if len(headers) > 4:
                    sections += ", and more"
                return f"Here is a template that includes sections for: {sections}."
        
        # Check for common patterns and build a natural sentence
        if "git " in code_text.lower():
            if "commit" in code_text.lower():
                return f"Here we have {lang_name} commands showing how to commit changes."
            elif "checkout" in code_text.lower():
                return f"Here we have {lang_name} commands for switching branches."
            elif "restore" in code_text.lower():
                return f"Here we have {lang_name} commands for restoring files."
            elif "diff" in code_text.lower():
                return f"Here we have {lang_name} commands for viewing changes."
            elif "stash" in code_text.lower():
                return f"Here we have {lang_name} commands for stashing changes."
            else:
                return f"Here we have {lang_name} commands for Git operations."
        
        if "def " in code_text or "function " in code_text:
            func_match = re.search(r"(?:def|function)\s+(\w+)", code_text)
            if func_match:
                return f"Next is a {lang_name} function called {func_match.group(1)}."
            return f"Next is a {lang_name} function definition."
        
        if "class " in code_text:
            class_match = re.search(r"class\s+(\w+)", code_text)
            if class_match:
                return f"Next is a {lang_name} class called {class_match.group(1)}."
            return f"Next is a {lang_name} class definition."
        
        if code_text.strip().startswith("#") or code_text.strip().startswith("//"):
            return f"Here is a {lang_name} template or configuration example."
        
        if "import " in code_text or "from " in code_text or "require(" in code_text:
            return f"Here we have some {lang_name} imports and setup code."
        
        # Generic fallback with natural phrasing
        if num_lines > 10:
            return f"Here is a {lang_name} example spanning about {num_lines} lines."
        else:
            if lang_name == "code":
                return "Here is a code example."
            return f"Here is a {lang_name} code example."
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract text from soup, preserving paragraph structure."""
        # Get all text, joining with newlines for paragraphs
        paragraphs = []
        
        for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
            text = element.get_text(separator=" ", strip=True)
            if text:
                # Add emphasis for headers
                if element.name in ["h1", "h2", "h3"]:
                    text = f"\n{text}\n"
                paragraphs.append(text)
        
        # If no paragraphs found, fall back to all text
        if not paragraphs:
            return soup.get_text(separator="\n", strip=True)
        
        return "\n\n".join(paragraphs)
    
    def _clean_for_audio(self, text: str) -> str:
        """Clean text for better audio output."""
        # Unwrap legacy [Code Example: ...] markers — keep the description, drop brackets
        text = re.sub(r"\[Code Example:\s*(.*?)\]", r"\1", text)
        
        # Remove any remaining square brackets (TTS tries to pronounce them)
        text = text.replace("[", "").replace("]", "")
        
        # Remove URLs (they're not useful in audio)
        text = re.sub(r"https?://\S+", "", text)
        
        # Remove email addresses
        text = re.sub(r"\S+@\S+\.\S+", "", text)
        
        # Convert common symbols to words
        text = text.replace("&", " and ")
        text = text.replace("→", " leads to ")
        text = text.replace("←", " back to ")
        text = text.replace("✓", " check ")
        text = text.replace("✗", " x ")
        text = text.replace("•", ". ")
        
        # Clean up quotes and apostrophes
        text = text.replace(""", '"')
        text = text.replace(""", '"')
        text = text.replace("'", "'")
        text = text.replace("'", "'")
        
        # Remove markdown-style formatting
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # Italic
        text = re.sub(r"`(.+?)`", r"\1", text)  # Inline code
        
        # Clean up file paths - make them speakable
        text = re.sub(r"(\w+)/(\w+)", r"\1 slash \2", text)  # folder/file -> folder slash file
        text = re.sub(r"\.(\w{2,4})(?=\s|$|\))", r" dot \1", text)  # .py -> dot py
        
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        
        # Remove standalone punctuation
        text = re.sub(r"^\s*[•\-\*]\s*$", "", text, flags=re.MULTILINE)
        
        # Clean up empty lines
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        
        return "\n\n".join(lines)
    
    def _create_intro(self, day: int, title: str, date: str) -> str:
        """Create an intro for the episode."""
        # Clean the title (remove "Day X:" if present)
        clean_title = re.sub(r"^Day\s+\d+:\s*", "", title)
        
        return (
            f"Welcome to Day {day} of 31 Days of Vibe Coding. "
            f"Today's topic is: {clean_title}."
        )
    
    def _create_outro(self, day: int) -> str:
        """Create an outro for the episode."""
        if day < 31:
            return (
                f"That's it for Day {day}. "
                f"Join us tomorrow for Day {day + 1}. "
                "Thanks for listening to 31 Days of Vibe Coding."
            )
        else:
            return (
                "Congratulations! You've completed 31 Days of Vibe Coding. "
                "Thanks for listening to the entire series. "
                "Now go build something amazing with AI."
            )


def main():
    """Test the processor with sample content."""
    sample_html = """
    <article>
        <h1>Day 1: Introduction to Vibe Coding</h1>
        <p>Welcome to the first day of our journey into AI-assisted development.</p>
        
        <h2>Getting Started</h2>
        <p>Here's a simple example:</p>
        
        <pre><code class="language-python">
def hello_world():
    print("Hello, Vibe Coding!")
        </code></pre>
        
        <p>This code shows a basic function. You can also use git commands:</p>
        
        <pre><code class="language-bash">
git add -A
git commit -m "Initial commit"
        </code></pre>
        
        <p>For more info, visit https://example.com</p>
    </article>
    """
    
    processor = ContentProcessor(summarize_code=True)
    result = processor.process(sample_html, day=1, title="Day 1: Introduction to Vibe Coding", date="Jan 1, 2026")
    
    print("Processed Text:")
    print("=" * 50)
    print(result.text)
    print("=" * 50)
    print(f"\nCharacter count: {result.char_count}")
    print(f"Word count: {result.word_count}")


if __name__ == "__main__":
    main()
