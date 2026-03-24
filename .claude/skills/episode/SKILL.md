---
name: episode
description: Interactive episode creation workflow — search news, select articles, create episode, and optionally start factcheck
argument-hint: [topic]
---

# /episode — Episode Creation Workflow

Guide the user through creating a new episode step by step.

## Workflow

### Step 1: Topic Selection
If the user provided a topic as argument, use it. Otherwise ask what topic/theme they want to cover.

### Step 2: News Search
Use `search_news` to find articles about the topic:
- Search with source=brave (freshness=pw for past week by default)
- Also search with source=youtube to find video sources
- Run both searches in parallel if possible

Present results in a numbered list:
```
1. [Brave] タイトル — ソース名
   URL: https://...
2. [YouTube] タイトル — チャンネル名
   URL: https://youtube.com/...
```

### Step 3: Article Selection
Ask the user which articles to include:
- Accept comma-separated numbers: "1,3,5"
- Accept ranges: "1-5"
- Accept "all" for everything
- Accept additional search requests if results are insufficient

### Step 4: Episode Title
Ask for a title, or suggest one based on the selected articles.

### Step 5: Create Episode
Use `create_episode_from_articles` with the title and selected articles.

### Step 6: Next Steps
Show the created episode status and ask:
"ファクトチェックを実行しますか？"
If yes, use `run_step` with step_name=factcheck.

## Notes
- Always show article sources and URLs so the user can verify quality
- If search returns no results, suggest broadening the query or different keywords
- The user can cancel at any step by saying "cancel" or "やめる"
