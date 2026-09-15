# Custom AI Skills

Skills expand the RahYar AI Developer Agent without installing arbitrary packages.

## How to add a skill

1. Create a markdown file: `.ai-agent/skills/<skill_id>.md`
2. Optional front-matter style lines at the top:

```text
title: عنوان فارسی
description: توضیح کوتاه
tools: web_search, read_file, list_tree
```

3. The rest of the file is injected into the agent system prompt when the skill is active.
4. Open a PR (or ask the agent in feature mode to add the file).

## Security

- Skills are **prompt + allowed tools** only.
- The agent **never** runs `pip install` from the internet on the host.
- `web_search` is read-only public search (DuckDuckGo).
- Write path still only commits on `ai/*` and opens a PR.

## Built-in skills

- `coding` — Clean Architecture / services / migrations
- `ui_polish` — Persian Telegram UX, keyboards, copy
- `web_research` — public web research
- `debug` — production log root-cause analysis
