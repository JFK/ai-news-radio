---
name: publish
description: Publish a completed episode — export to Google Drive, generate note.com articles, mark as complete
argument-hint: <episode_id>
---

# /publish — Episode Publishing Workflow

Guide the user through publishing a completed episode.

## Arguments
- Episode ID (required): e.g., `/publish 42`

## Workflow

### Step 1: Check Readiness
Use `get_episode_status` to check which steps are approved.
Report what's available:

| Action | Requires |
|--------|----------|
| Google Drive Export | analysis approved |
| note.com Analysis Article | analysis approved |
| note.com Video Article | video approved |
| Mark Complete | any state (always available) |

### Step 2: Publishing Menu
Present available actions as numbered list:
```
利用可能な公開アクション:
1. Google Drive エクスポート
2. note.com 分析記事
3. note.com 動画紹介記事
4. 完了マーク
```

Ask which to perform. Allow multiple selections (e.g., "1,2,4").

### Step 3: Execute
Run selected actions in order:

1. **Google Drive**: Use `export_to_drive` with episode_id. Show the Drive URL.
2. **note.com Analysis**: Call `curl -s -X POST http://localhost:8000/api/episodes/{id}/note/analysis`. Show preview.
3. **note.com Video**: Call `curl -s -X POST http://localhost:8000/api/episodes/{id}/note/video`. Show preview.
4. **Mark Complete**: Use `toggle_complete` with episode_id.

### Step 4: Summary
Show a final summary:
- Drive file URL (if exported)
- Note article titles and hashtags (if generated)
- Episode final status

## Notes
- If Google Drive is not authenticated, skip that option and explain setup
- Always execute "Mark Complete" last (after other exports)
- Show cost of each action if tokens were used
