# Custom AI Skills

Skills expand the RahYar AI Developer Agent without installing arbitrary packages.

## Design / UI pack (installed)

| File | Focus |
|------|--------|
| `telegram_ux.md` | Baseline Telegram UX rules |
| `visual_hierarchy.md` | Message structure & density |
| `keyboard_design.md` | Inline keyboard layout |
| `persian_copy.md` | Persian microcopy |
| `student_journey_ux.md` | Student flows |
| `admin_panel_ux.md` | Owner admin panel |

Any skill with `tags: design, ux` is **auto-attached** when the owner uses 🎨 زیباسازی UI / design mode.

## How to add a skill

1. Create `.ai-agent/skills/<skill_id>.md`
2. Front-matter lines:

```text
title: عنوان فارسی
description: توضیح کوتاه
tools: read_file, list_tree
tags: design, ux
```

3. Body = system guidance injected into the agent.
4. Ship via PR (or ask the agent in feature mode).

## Security

- Skills are **prompt + allowed tools** only.
- No runtime `pip install` from the internet.
- `web_search` is read-only public search.
- Writes still only on `ai/*` + PR.

## Built-in skills

- `coding` — architecture / services / migrations
- `ui_polish` — core UI design brain
- `web_research` — public web research
- `debug` — production root-cause analysis
