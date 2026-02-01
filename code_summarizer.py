"""
LLM-powered code block summarization for podcast-friendly audio.

Uses Claude API to generate detailed, conversational summaries of code blocks
that are clear when listened to (not read).
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class CodeSummarizer:
    """Summarizes code blocks using Claude API with caching."""
    
    CACHE_FILE = "cache/code_summaries.json"
    
    # System prompt for code summarization
    SYSTEM_PROMPT = """You are summarizing code for a podcast. The listener cannot see the code and is driving, so they need clear, conversational descriptions.

Your task: Describe what the code does in 1-3 sentences.

Guidelines:
- Be specific but conversational, like you're explaining to a colleague
- Mention the programming language naturally (e.g., "This Python function..." or "These bash commands...")
- Explain the purpose and key details that matter
- For shell/git commands, explain what each command does
- Avoid spelling out variable names character by character
- Don't include function signatures unless essential for understanding
- Don't say "this code" at the start - vary your phrasing
- Keep it concise - podcast listeners have limited attention

Examples of good summaries:
- "Here we define a Python function that validates email addresses using a regex pattern, returning True if the format is valid."
- "These git commands create a checkpoint: first staging all changes, then committing with a work-in-progress message so you can easily roll back if needed."
- "The configuration object sets up the project context including the tech stack, file patterns, and testing framework preferences."
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        cache_enabled: bool = True
    ):
        """
        Initialize the code summarizer.
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use (defaults to ANTHROPIC_API_MODEL env var or claude-sonnet-4-20250514)
            cache_enabled: Whether to cache summaries (default True)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("ANTHROPIC_API_MODEL", "claude-sonnet-4-20250514")
        self.cache_enabled = cache_enabled
        self.cache = {}
        self.client = None
        
        # Stats tracking
        self.stats = {
            "cache_hits": 0,
            "api_calls": 0,
            "errors": 0
        }
        
        if self.cache_enabled:
            self._load_cache()
    
    def _get_client(self):
        """Lazy-load the Anthropic client."""
        if self.client is None:
            if not self.api_key:
                raise ValueError(
                    "Anthropic API key not found. "
                    "Set ANTHROPIC_API_KEY environment variable."
                )
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Run: pip install anthropic"
                )
        return self.client
    
    def _load_cache(self):
        """Load cached summaries from disk."""
        cache_path = Path(self.CACHE_FILE)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"  Loaded {len(self.cache)} cached code summaries")
            except (json.JSONDecodeError, IOError) as e:
                print(f"  Warning: Could not load cache: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cached summaries to disk."""
        cache_path = Path(self.CACHE_FILE)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def _hash_code(self, code: str, language: str) -> str:
        """Generate a hash for a code block."""
        content = f"{language}:{code}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def summarize(
        self,
        code: str,
        language: str = "",
        context: str = "",
        force_refresh: bool = False
    ) -> str:
        """
        Summarize a code block for podcast audio.
        
        Args:
            code: The code to summarize
            language: Programming language (e.g., "python", "bash")
            context: Optional context about the article/topic
            force_refresh: If True, ignore cache and regenerate
            
        Returns:
            A podcast-friendly summary of the code
        """
        # Generate cache key
        cache_key = self._hash_code(code, language)
        
        # Check cache first (unless force refresh)
        if self.cache_enabled and not force_refresh and cache_key in self.cache:
            self.stats["cache_hits"] += 1
            return self.cache[cache_key]
        
        # Call LLM for summary
        try:
            summary = self._call_llm(code, language, context)
            self.stats["api_calls"] += 1
            
            # Cache the result
            if self.cache_enabled:
                self.cache[cache_key] = summary
                self._save_cache()
            
            return summary
            
        except Exception as e:
            self.stats["errors"] += 1
            print(f"    Warning: LLM summarization failed: {e}")
            # Fall back to basic description
            return self._fallback_summary(code, language)
    
    def _call_llm(self, code: str, language: str, context: str) -> str:
        """Call Claude API to summarize code."""
        client = self._get_client()
        
        # Build the user prompt
        lang_str = language if language else "code"
        user_prompt = f"Summarize this {lang_str} for a podcast listener:\n\n```{language}\n{code}\n```"
        
        if context:
            user_prompt += f"\n\nContext: This appears in an article about {context}."
        
        # Call the API
        message = client.messages.create(
            model=self.model,
            max_tokens=256,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Extract the response text
        return message.content[0].text.strip()
    
    def _fallback_summary(self, code: str, language: str) -> str:
        """Generate a basic fallback summary if LLM fails."""
        lang_name = {
            "python": "Python",
            "py": "Python", 
            "javascript": "JavaScript",
            "js": "JavaScript",
            "typescript": "TypeScript",
            "ts": "TypeScript",
            "bash": "Bash",
            "sh": "shell",
            "shell": "shell",
            "sql": "SQL",
            "json": "JSON",
            "html": "HTML",
            "css": "CSS",
            "git": "Git",
        }.get(language.lower(), language or "code")
        
        lines = len(code.strip().split("\n"))
        return f"[A {lang_name} example with {lines} lines - see the article for details.]"
    
    def get_stats(self) -> dict:
        """Get summarization statistics."""
        return {
            **self.stats,
            "cache_size": len(self.cache)
        }
    
    def clear_cache(self):
        """Clear the summary cache."""
        self.cache = {}
        cache_path = Path(self.CACHE_FILE)
        if cache_path.exists():
            cache_path.unlink()
        print("  Cache cleared")


def main():
    """Test the code summarizer."""
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set. Please set it in .env file.")
        return
    
    summarizer = CodeSummarizer()
    
    # Test with a few code samples
    test_cases = [
        {
            "code": """git add -A
git commit -m "WIP: before AI changes to auth"
""",
            "language": "bash",
            "context": "using Git as an undo button for AI mistakes"
        },
        {
            "code": r"""def validate_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
""",
            "language": "python",
            "context": "input validation"
        },
        {
            "code": """## Project
[One paragraph: what you're building, tech stack, key patterns]

## Current State
Working on: [feature/phase]
What's done: [completed parts]
What's next: [current task]
""",
            "language": "markdown",
            "context": "context management for AI conversations"
        }
    ]
    
    print("Testing CodeSummarizer...\n")
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['language']} code")
        print(f"Context: {test['context']}")
        print("-" * 40)
        
        summary = summarizer.summarize(
            code=test["code"],
            language=test["language"],
            context=test["context"]
        )
        
        print(f"Summary: {summary}")
        print()
    
    print("Stats:", summarizer.get_stats())


if __name__ == "__main__":
    main()
