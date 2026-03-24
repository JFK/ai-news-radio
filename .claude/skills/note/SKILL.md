---
name: note
description: Generate a note.com article from an episode — prerequisite checks, generation, preview, and cover image
argument-hint: <episode_id> [analysis|video]
---

# /note — Generate note.com Article

Generate a note.com article from an episode's analysis or video data.

## Arguments
- Episode ID (required): e.g., `/note 42`
- Article type (optional): "analysis" or "video"

## Workflow

### Step 1: Check Prerequisites
Use `get_episode_status` to verify:
- For analysis article: analysis step must be `approved`
- For video article: video step must be `needs_approval` or `approved`

If prerequisites are not met, explain what needs to happen first.
Offer to run missing steps with `/pipeline`.

### Step 2: Auto-detect Type
If article type was not specified:
- If video step is completed/approved: ask "分析記事と動画紹介記事のどちらを生成しますか？"
- If only analysis is approved: default to analysis article

### Step 3: Generate Article
Call the backend API:
```bash
curl -s -X POST http://localhost:8000/api/episodes/{episode_id}/note/{article_type}
```
Parse the response JSON for the markdown content.

### Step 4: Preview
Display the generated markdown article.
Highlight:
- Title (first H1 line)
- Hashtags (usually the last line)
- Embedded YouTube URLs (if any)
- Approximate word count

### Step 5: Cover Image (Optional)
Ask: "カバー画像も生成しますか？ (Y/n)"
If yes:
```bash
curl -s -X POST http://localhost:8000/api/episodes/{episode_id}/note/{article_type}/cover
```
Show the image path from the response.

### Step 6: Usage Instructions
Tell the user:
- The markdown is ready to paste into note.com's editor
- Copy hashtags separately for note.com's tag field
- Cover image path for upload
- Remind to review formatting after pasting

## Notes
- Note article generation is not exposed via MCP tools, so use REST API directly via curl
- Always display the full article for user review
