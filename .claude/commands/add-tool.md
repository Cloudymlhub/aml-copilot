---
description: Add a new data retrieval tool to the system
---

Help me add a new data retrieval tool to the AML Copilot system.

Steps:
1. Ask me what data the tool should retrieve
2. Identify which repository to update (or if we need a new one)
3. Implement the repository method following the repository pattern
4. Update the DataRetrievalAgent to support the new tool
5. Update the IntentMapper prompt to recognize when this tool is needed
6. Create a test case for the new tool

Make sure:
- Follow repository pattern (no direct SQL in agents)
- Use dependency injection
- Add proper error handling
- Update type hints and docstrings
- Consider caching if appropriate
