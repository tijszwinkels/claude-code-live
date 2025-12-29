# claude-code-live

Live-updating transcript viewer for Claude Code sessions.

## Overview

Unlike static HTML generators, this tool provides real-time updates as your Claude Code session progresses. New messages appear automatically within ~1 second.

## Installation

```bash
uv tool install claude-code-live
```

Or run directly:

```bash
uvx claude-code-live
```

## Usage

```bash
# Watch most recent session (auto-detected)
claude-code-live

# Watch specific session file
claude-code-live --session ~/.claude/projects/.../session.jsonl

# Custom port
claude-code-live --port 8765

# Don't auto-open browser
claude-code-live --no-open
```

## Features

- **Live updates** - New messages appear automatically via Server-Sent Events
- **Auto-scroll** - Follows new messages when you're at the bottom
- **Resource-conscious** - Limits DOM nodes to prevent memory issues
- **Same styling** - Uses the same CSS as claude-code-transcripts

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run development server
uv run claude-code-live --debug
```

## Credits

This project is based on [claude-code-transcripts](https://github.com/simonw/claude-code-transcripts) by [Simon Willison](https://simonwillison.net/). The HTML rendering, CSS styling, and message formatting are adapted from that project.

## License

Apache 2.0
