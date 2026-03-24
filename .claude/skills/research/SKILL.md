---
name: research
description: Deep multi-source research on a topic using Brave Search and YouTube, with synthesis report
argument-hint: <topic>
context: fork
---

# /research — Deep Multi-Source Research

Conduct thorough research on a topic using multiple sources and present a synthesis.

## Arguments
- Topic (required): e.g., `/research 熊本TSMC最新動向`

## Workflow

### Step 1: Query Expansion
From the user's topic, generate 3-5 search queries covering different angles:
- Main topic query (Japanese if Japanese topic)
- Related background / historical context query
- Opposing or critical perspective query
- English query (if the topic has international relevance)

### Step 2: Parallel Search
Run all queries in parallel using `search_news`:
- Brave searches with freshness=pm (past month)
- At least one YouTube search for the main topic
Present a combined, deduplicated list of sources.

### Step 3: Synthesis
Analyze the collected results and present:
1. **概要**: What is happening and why it matters
2. **タイムライン**: Key events in chronological order
3. **複数の視点**: At least 2-3 viewpoints with supporting sources
4. **情報ギャップ**: What is unclear or missing from available sources
5. **ソース品質**: Which sources appear most reliable and why

### Step 4: Episode Suggestion
Ask the user if they want to create an episode from the research results.
If yes, recommend which articles to include and use `create_episode_from_articles`.

## Notes
- Clearly attribute each claim to its source
- Flag potentially biased sources
- Acknowledge what you could NOT find or verify
- Present the synthesis in Japanese (matching the project's target audience)
