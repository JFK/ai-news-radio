---
name: status
description: Quick overview of all episodes and their pipeline progress with actionable items
---

# /status — Episode Status Overview

Show a quick overview of all episodes and highlight actionable items.

## Workflow

### Step 1: Health Check
Use `health_check` to verify the backend is running.
If not healthy, report the error and suggest `docker compose up -d`.

### Step 2: List Episodes
Use `list_episodes` to get all episodes.

### Step 3: Present Dashboard
For each episode, show a one-line pipeline progress bar using these icons:
- `[v]` = approved
- `[?]` = needs_approval
- `[~]` = running
- `[ ]` = pending
- `[x]` = rejected

Format:
```
#ID [status] タイトル (作成日)
  [v]collection [v]factcheck [?]analysis [ ]script [ ]voice [ ]video
```

### Step 4: Action Items
Highlight items that need attention:
- Steps with `needs_approval` → "Episode #X の Y ステップが承認待ちです"
- Steps with `running` → "Episode #X の Y ステップが実行中です"
- Rejected steps → "Episode #X の Y ステップが却下されました"

If no pending actions: "All clear — アクション待ちのエピソードはありません。"

### Step 5: Quick Actions
If there are actionable items, suggest:
- "承認・実行: `/pipeline {episode_id}`"
- "新規作成: `/episode`"
