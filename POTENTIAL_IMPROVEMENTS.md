# Potential Improvements

- Intent Mapper: add a retry when no tool calls or clarification is produced, and cap the number of tool selections to avoid runaway invocations.
- Compliance Expert: truncate or whitelist large retrieved-data blobs in the human message (top fields, first N list items) to reduce token bloat and hallucination risk.
- Review Agent: if model reports very low confidence (e.g., <0.4) without choosing `human_review`, auto-upgrade the status to `human_review` to prevent low-confidence passes.
- Coordinator: log raw invalid JSON when a retry is triggered (for debugging only, not user-facing state).
