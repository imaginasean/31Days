# Adding LLM-Powered Code Summarization

_A follow-up to the 31 Days of Vibe Coding Podcast Generator_

After building the initial podcast generator with rule-based code summarization, I wanted something better. The crude pattern matching ("The following Python code defines a function called...") wasn't cutting it for a podcast experience. Time to bring in the big guns: Claude.

## The Problem

The original code summarizer used simple pattern matching to describe code blocks:

```python
if "git " in code_text.lower():
    description_parts.append(f"The following {lang_name} commands show")
    if "commit" in code_text.lower():
        description_parts.append("how to commit changes")
```

This produced robotic, unhelpful descriptions. When you're driving and listening to a podcast, you don't want to hear "The following bash code shows Git operations in about 3 lines of code." You want context. You want to understand _why_ this code matters.

## The Conversation

Here's how the feature came together through conversation with Claude.

---

### Prompt 1: The Initial Request

> i want to update this app now. I want to change how we are handling code block. instead of removing them or summarizing them in a very crude way, i want to be able to process each code block with a call to an LLM to evaluate and provide a succint summary that will be clear in a podcast. To do this we will want to use vercel ai sdk and the anthropic adapter. YOU MUST USE VERSION 6+ of the vercel ai sdk and this will allow you to use the latest anthropic adatper. Keys are in the environment already as ANTHROPIC_API_KEY and ANTHROPIC_API_MODEL. Ask with questions, plan this out.

Claude caught something important right away: the Vercel AI SDK is JavaScript/TypeScript, but this project is Python. Rather than assume, it asked clarifying questions:

**Claude's Questions:**

1. **Language mismatch**: The Vercel AI SDK is JavaScript/TypeScript, but this project is Python. Would you prefer:

   - A) Add a Node.js/TypeScript processing step alongside the Python code
   - B) Use the Anthropic Python SDK directly instead (simpler, stays in Python)
   - C) Something else?

2. **Summary style**: What tone/detail level for code summaries?

   - Brief: "This code commits changes to git"
   - Detailed: "This bash command stages all files and creates a commit with the message 'WIP: before AI changes', creating a checkpoint you can restore to"
   - Technical: Include language names, function signatures, etc.?

3. **Caching**: Should we cache LLM-generated summaries so re-running doesn't re-process the same code blocks? (Saves API costs)

4. **Cost estimate**: With ~31 articles and potentially 5-15 code blocks each, that's 150-450+ API calls. Are you okay with that, or should we batch multiple code blocks per request?

---

### Prompt 2: The Clarifications

> 1 Good catch, B. 2 Detailed, but not function signatures unless it makes sense for clarity because it is hard to get that while listening to podcasts. 3 Yes, great idea. 4. This is fine for now, we will see what the cost is and go from there after the first run.

With these answers, Claude had everything needed to plan the implementation.

---

### Prompt 3: Approval

> this looks good

And we were off to the races.

---

## The Implementation

### New File: `code_summarizer.py`

The core of the feature is a new module that handles LLM-based summarization with caching:

```python
class CodeSummarizer:
    """Summarizes code blocks using Claude API with caching."""

    CACHE_FILE = "cache/code_summaries.json"

    SYSTEM_PROMPT = """You are summarizing code for a podcast. The listener cannot see the code and is driving, so they need clear, conversational descriptions.

Your task: Describe what the code does in 1-3 sentences.

Guidelines:
- Be specific but conversational, like you're explaining to a colleague
- Mention the programming language naturally
- Explain the purpose and key details that matter
- For shell/git commands, explain what each command does
- Avoid spelling out variable names character by character
- Don't include function signatures unless essential for understanding
- Don't say "this code" at the start - vary your phrasing
- Keep it concise - podcast listeners have limited attention
"""
```

The prompt was carefully crafted for podcast consumption. Key decisions:

- **Conversational tone**: "like you're explaining to a colleague"
- **No function signatures**: They're hard to follow in audio
- **Varied phrasing**: Avoids repetitive "This code..." openers
- **Language mentioned naturally**: "This Python function..." not "[Python]"

### Caching Strategy

Each code block gets hashed, and summaries are cached to avoid redundant API calls:

```python
def _hash_code(self, code: str, language: str) -> str:
    """Generate a hash for a code block."""
    content = f"{language}:{code}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

The cache lives in `cache/code_summaries.json`. After the first run, subsequent runs are nearly instant for unchanged code blocks.

### Updated `processor.py`

The processor now accepts an optional LLM summarizer:

```python
def __init__(
    self,
    summarize_code: bool = True,
    use_llm: bool = False,
    llm_summarizer=None,
    force_resummarize: bool = False
):
```

When `use_llm` is enabled, code blocks go through Claude instead of the rule-based fallback.

### New CLI Flags in `main.py`

Two new options make the feature accessible:

```python
parser.add_argument(
    "--use-llm",
    action="store_true",
    help="Use LLM (Claude) to generate detailed code block summaries"
)
parser.add_argument(
    "--resummarize",
    action="store_true",
    help="Force re-summarization of code blocks (ignore cache)"
)
```

## The Results

Here's a real example from Day 4 (Observability). The old rule-based output:

> [Code Example: The following code defines a function called trackAuthEvent.]

The new LLM-powered output:

> This is a requirements document outlining user authentication features alongside their observability needs. It specifies the standard auth flows like registration, login, and password reset, but pairs each with specific monitoring requirements—logging all auth events, tracking success rates, setting up alerts for anomalies like high failure rates, and tracing the full authentication flow for debugging.

Night and day difference. The LLM understands context, explains _why_ the code matters, and speaks naturally.

## Usage

```bash
# Generate with LLM code summaries
python main.py --use-llm --engine piper --voice amy

# Scrape only with LLM summaries (no audio)
python main.py --use-llm --scrape-only

# Force re-summarization (ignore cache)
python main.py --use-llm --resummarize --scrape-only

# Test with single day
python main.py --use-llm --scrape-only --day 4
```

## Files Changed

| File                 | Change                                                     |
| -------------------- | ---------------------------------------------------------- |
| `code_summarizer.py` | **New** - LLM summarization with caching                   |
| `processor.py`       | Updated to use CodeSummarizer when `--use-llm` flag is set |
| `main.py`            | Added `--use-llm` and `--resummarize` flags                |
| `requirements.txt`   | Added `anthropic>=0.40.0`                                  |
| `.env.example`       | Added `ANTHROPIC_API_KEY` and `ANTHROPIC_API_MODEL`        |
| `.gitignore`         | Added `cache/` directory                                   |

## Cost Considerations

With 31 articles averaging ~8 code blocks each, that's roughly 250 API calls. Using Claude Sonnet, this costs approximately $0.50-1.00 for the entire series. The caching means you only pay once per unique code block—re-runs are free.

## Lessons Learned

1. **Ask clarifying questions**: Claude caught the JavaScript/Python mismatch before writing any code
2. **Caching is essential**: LLM calls are expensive and slow; cache aggressively
3. **Prompt engineering matters**: The system prompt took iteration to get conversational, podcast-friendly output
4. **Fallbacks are important**: The rule-based summarizer remains as a fallback if the API fails

---

_This feature was built through a conversation with Claude, demonstrating the "vibe coding" approach the podcast itself teaches._
