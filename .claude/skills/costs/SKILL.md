---
name: costs
description: Show API cost summary with breakdown by provider and step, plus optimization suggestions
argument-hint: [today|week|month|episode_id]
---

# /costs — Cost Summary and Optimization

Show API cost statistics and provide optimization suggestions.

## Arguments
- Period (optional): "today", "week", "month", or an episode ID number
- Default: past 7 days

## Workflow

### Step 1: Gather Data
Use `get_cost_stats` with appropriate filters:
- "today" → from_date = today
- "week" → from_date = 7 days ago
- "month" → from_date = 30 days ago
- Number → episode_id filter

### Step 2: Present Summary
Format results as a clear report:

```
=== API Cost Report (期間: YYYY-MM-DD 〜 YYYY-MM-DD) ===

Total: $X.XX (約 ¥XXX)

Provider別:
  - OpenAI:    $X.XX (XX%)
  - Anthropic: $X.XX (XX%)
  - Google:    $X.XX (XX%)
  - Brave:     $X.XX (XX%)

Step別:
  - collection: $X.XX
  - factcheck:  $X.XX
  - analysis:   $X.XX
  - script:     $X.XX
  - voice:      $X.XX
  - video:      $X.XX
```

Use 1 USD ≈ 150 JPY as rough conversion.

### Step 3: Optimization Suggestions
Based on the data:
- If factcheck/analysis costs are high → suggest lighter models
- If voice costs dominate → note alternative TTS providers
- If video/imagen costs are high → mention static fallback option
- Flag any unusually expensive episodes

## Notes
- Present costs with appropriate precision ($0.0012, not $0.00)
- Always include the date range in the header
