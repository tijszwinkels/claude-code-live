## Commit Transcripts

On every commit, publish a gist of the conversation transcript and add the preview URL to the commit message.

Generate a short, unique verification phrase in the conversation, then run:

```bash
uvx vibedeck html --phrase "YOUR_PHRASE" --gist
```

This searches sessions from today and yesterday and exports if exactly one match is found.

**Safety:** DO NOT generate transcript gists if the conversation contains secrets, API keys, .env files, logs, or database queries. When in doubt, DO NOT generate the transcript and explain why.

**Always** generate the transcript when committing, unless there are safety concerns.

Example commit message format:

```
feat: add user authentication

- Implemented login/logout flow
- Added session management

transcript: https://gisthost.github.io/?abc123/index.html
```
