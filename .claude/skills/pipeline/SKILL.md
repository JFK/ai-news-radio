---
name: pipeline
description: Run the next pending pipeline step for an episode — auto-detect, execute, monitor, and review
argument-hint: <episode_id>
---

# /pipeline — Run Next Pipeline Step

Run the next pending pipeline step for an episode.

## Arguments
- Episode ID (required): provided as argument (e.g., `/pipeline 42`)
- If no argument, ask the user for the episode ID

## Workflow

### Step 1: Check Status
Use `get_episode_status` to determine the current state of all pipeline steps.

### Step 2: Identify Next Action
Examine each step in order (collection → factcheck → analysis → script → voice → video):

- If a step is `needs_approval`: Show results summary and ask user to approve/reject
- If a step is `running`: Report it's still running and wait
- If a step is `pending` AND the previous step is `approved`: This is the next step to run
- If all steps are `approved` or the episode is `completed`: Report pipeline is complete

### Step 3: Run the Step
Use `run_step` with the identified step name.
- For voice step: Ask about TTS model/voice preferences if desired
- For video step: Ask about video_targets if this is a re-run

### Step 4: Monitor Completion
Poll with `get_episode_status` every 15-20 seconds until the step transitions from `running`.
Show brief progress updates.

### Step 5: Review Results
When the step completes (`needs_approval`):
- Use `get_step_detail` to get detailed output
- **factcheck**: Show fact-check scores per item, flag scores below 3
- **analysis**: Show severity summary, perspective count, media bias if present
- **script**: Show the episode script text for review
- **voice**: Report audio file generation status
- **video**: Report video/thumbnail generation status

### Step 6: Approval
Ask the user:
- "承認" / "approve" → `approve_step`
- "却下 [理由]" / "reject [reason]" → `reject_step`
- "除外 1,3" / "exclude 1,3" → `approve_step` with `excluded_item_ids`

After approval, ask: "次のステップに進みますか？"

## Notes
- If a step fails (resets to pending), show the error and ask whether to retry
- Always show the episode title and current pipeline state before taking action
