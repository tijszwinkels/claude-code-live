# Claude Code Instructions

## Development

### Test-Driven Development (TDD)

Always write tests before implementing new functionality:

1. **Write failing tests first** - Define expected behavior in tests before writing code
2. **Run tests to confirm they fail** - `uv run pytest tests/ -v`
3. **Implement the minimal code** to make tests pass
4. **Refactor** while keeping tests green
5. **Run full test suite** before committing: `uv run pytest`

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_export.py -v

# Run with coverage
uv run pytest --cov=src/claude_code_session_explorer
```

## Commit Transcripts

On every commit, publish a gist of the conversation transcript and add the preview URL to the commit message.

### Find Your Session File

**For Claude Code sessions:**
```bash
# Find the project directory
ls ~/.claude/projects/ | grep $(basename $PWD)

# List recent sessions (most recent first)
ls -t ~/.claude/projects/-home-claude-projects-claude-code-session-explorer/*.jsonl | head -5
```

**For OpenCode sessions:**
```bash
# List recent OpenCode sessions (most recent first)
ls -lt ~/.local/share/opencode/storage/message/ | head -10
```

### Generate and Upload Transcript

**For Claude Code sessions:**
```bash
# Using this project's built-in export (recommended)
uv run claude-code-session-explorer html "$(ls -t ~/.claude/projects/-home-claude-projects-claude-code-session-explorer/*.jsonl | head -1)" --gist

# Or with explicit session file
uv run claude-code-session-explorer html ~/.claude/projects/-home-claude-projects-claude-code-session-explorer/SESSION_ID.jsonl --gist
```

**For OpenCode sessions:**
```bash
# Using session ID directly (e.g., ses_xxx)
uv run claude-code-session-explorer html ses_461e502a0ffez5ZvcUYkCT4iaj --gist

# Or find the most recent session and export it
uv run claude-code-session-explorer html "$(ls -t ~/.local/share/opencode/storage/message/ | head -1)" --gist
```

The command outputs:
- `Gist: https://gist.github.com/...` - the raw gist URL
- `Preview: https://gisthost.github.io/?GIST_ID/index.html` - the preview URL to use

### Add to Commit Message

Add the preview URL to the commit message footer:
```
transcript: https://gisthost.github.io/?GIST_ID/index.html
```

### Safety: DO NOT generate transcript gists if ANY of these conditions apply:
- Transcript contains secrets, API keys, passwords, or tokens
- A `.env` file or any config file containing secrets was read
- Log files were read
- Database queries were executed
- Any other potentially sensitive information was accessed

When in doubt, skip the transcript.
