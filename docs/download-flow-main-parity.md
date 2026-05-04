# Download Flow Main-Branch Parity

## Summary

The web app download flow was changed to match the original `main.py` behavior exactly for link resolution and queueing.  
This fixed the "links resolve in logs but nothing enters the download queue" issue.

## What Was Changed

1. Episode link resolution now runs in `main.py` style:
- Resolve each selected episode in order.
- Select quality using the same fallback logic (`0` highest, `-1` lowest, exact match else highest).
- Resolve direct link immediately from the selected option.

2. Queue startup behavior now follows the same pattern:
- Collect resolved episode links.
- Sort by episode number.
- Enqueue tasks in order.

3. Optimization gates that could silently skip all tasks were removed from the critical path:
- No pre-queue duplicate/file-exists suppression in the API flow.
- No cached reuse of resolved episode options/direct links for this flow.
- No chunked/concurrent batch optimization in the core batch resolver path.

## Why It Works Now

The previous optimized flow could resolve links successfully but still end with zero queued tasks because of skip conditions (dedupe/file-exists/lock-state path interactions).  
By restoring the deterministic `main.py` sequence (resolve -> sort -> enqueue), every successfully resolved episode now reaches queue insertion directly.

In short:
- Before: valid links could be dropped before enqueue.
- Now: valid links are enqueued in episode order, same as the proven script behavior.

## Tradeoff

This parity-first flow is intentionally less optimized (fewer short-circuit skips and less concurrency), but it is more predictable and matches the known-good downloader behavior.
