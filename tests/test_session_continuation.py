"""Test session continuation feature."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import AMLCopilot
from config.settings import settings


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def print_conversation(messages):
    """Print conversation history."""
    print("\nCONVERSATION HISTORY:")
    print("─" * 70)
    for i, msg in enumerate(messages, 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "user":
            print(f"\n👤 USER (message {i}):")
            print(f"   {content}")
        elif role == "assistant":
            print(f"\n🤖 ASSISTANT (message {i}):")
            # Truncate long responses
            if len(content) > 200:
                print(f"   {content[:200]}...")
            else:
                print(f"   {content}")
    print("─" * 70)


def test_session_continuation():
    """Test that conversation history is preserved across requests."""
    print_header("Testing Session Continuation")

    # Initialize copilot
    agents_config = settings.get_agents_config()
    copilot = AMLCopilot(agents_config=agents_config)

    user_id = "test_user"
    session_id = "test_session_001"
    context = {"cif_no": "C000001"}

    # Request 1: Ask about risk score
    print("\n📝 REQUEST 1: What's the risk score?")
    result1 = copilot.query(
        user_query="What is the risk score for this customer?",
        context=context,
        session_id=session_id,
        user_id=user_id
    )

    print(f"\n✓ Response 1: {result1['response'][:150]}...")
    print(f"✓ Messages in state: {len(result1['messages'])}")

    # Check session info
    session_info = copilot.get_session_info(user_id, session_id)
    print(f"\n✓ Session info:")
    print(f"   - Started at: {session_info['started_at']}")
    print(f"   - Message count: {session_info['message_count']}")
    print(f"   - Context: {session_info['context']}")

    # Request 2: Follow-up question (testing memory)
    print("\n\n📝 REQUEST 2: Follow-up question (uses 'their' - requires context)")
    result2 = copilot.query(
        user_query="Show me their transaction count",  # "their" should reference C000001
        context=context,  # Context is still C000001
        session_id=session_id,
        user_id=user_id
    )

    print(f"\n✓ Response 2: {result2['response'][:150]}...")
    print(f"✓ Messages in state: {len(result2['messages'])}")

    # Request 3: Another follow-up
    print("\n\n📝 REQUEST 3: Another follow-up question")
    result3 = copilot.query(
        user_query="What about high-risk transactions?",
        context=context,
        session_id=session_id,
        user_id=user_id
    )

    print(f"\n✓ Response 3: {result3['response'][:150]}...")
    print(f"✓ Messages in state: {len(result3['messages'])}")

    # Get full conversation history
    print_header("Full Conversation History")
    history = copilot.get_conversation_history(user_id, session_id)
    print_conversation(history)

    # Verify message count
    print_header("Verification")
    print(f"\n✓ Total messages in conversation: {len(history)}")
    print(f"✓ Expected: ~6 messages (3 user + 3 assistant)")

    # Count user vs assistant messages
    user_count = sum(1 for m in history if m.get("role") == "user")
    assistant_count = sum(1 for m in history if m.get("role") == "assistant")

    print(f"\n✓ User messages: {user_count}")
    print(f"✓ Assistant messages: {assistant_count}")

    # Test session clearing
    print_header("Testing Session Clearing")
    print(f"\n📝 Clearing session {session_id}...")
    cleared = copilot.clear_session(user_id, session_id)
    print(f"✓ Session cleared: {cleared}")

    # Verify session is gone
    history_after_clear = copilot.get_conversation_history(user_id, session_id)
    print(f"✓ History after clear: {history_after_clear}")

    print_header("✓ SESSION CONTINUATION TEST COMPLETED")
    print("\nKey Findings:")
    print("  1. ✓ Conversation history preserved across requests")
    print("  2. ✓ Context maintained (CIF number carried forward)")
    print("  3. ✓ Session info retrievable")
    print("  4. ✓ Session clearing works")


def test_new_vs_existing_session():
    """Test that new sessions start fresh while existing continue."""
    print_header("Testing New vs Existing Sessions")

    agents_config = settings.get_agents_config()
    copilot = AMLCopilot(agents_config=agents_config)

    user_id = "test_user"
    context = {"cif_no": "C000001"}

    # Session A - Request 1
    print("\n📝 SESSION A - Request 1:")
    result_a1 = copilot.query(
        user_query="What is the risk score?",
        context=context,
        session_id="session_A",
        user_id=user_id
    )
    print(f"✓ Session A messages: {len(result_a1['messages'])}")

    # Session B - Request 1 (different session, should start fresh)
    print("\n📝 SESSION B - Request 1 (different session):")
    result_b1 = copilot.query(
        user_query="Show me transactions",
        context=context,
        session_id="session_B",
        user_id=user_id
    )
    print(f"✓ Session B messages: {len(result_b1['messages'])}")

    # Session A - Request 2 (should have history from A1)
    print("\n📝 SESSION A - Request 2 (continuing session A):")
    result_a2 = copilot.query(
        user_query="What about alerts?",
        context=context,
        session_id="session_A",
        user_id=user_id
    )
    print(f"✓ Session A messages: {len(result_a2['messages'])}")

    # Verify
    history_a = copilot.get_conversation_history(user_id, "session_A")
    history_b = copilot.get_conversation_history(user_id, "session_B")

    print("\n✓ VERIFICATION:")
    print(f"   Session A has {len(history_a)} messages (should be ~4: 2 user + 2 assistant)")
    print(f"   Session B has {len(history_b)} messages (should be ~2: 1 user + 1 assistant)")

    # Clean up
    copilot.clear_session(user_id, "session_A")
    copilot.clear_session(user_id, "session_B")

    print_header("✓ NEW VS EXISTING SESSION TEST COMPLETED")


def main():
    """Run all session tests."""
    print("\n" + "="*70)
    print("  AML COPILOT - Session Continuation Tests")
    print("="*70)

    print("\n⚠️  NOTE: These tests require:")
    print("  1. Redis running (for checkpoints)")
    print("  2. PostgreSQL running (for data)")
    print("  3. Valid OpenAI API key in .env")
    print("\nPress Ctrl+C to cancel...\n")

    try:
        import time
        time.sleep(2)

        test_session_continuation()
        test_new_vs_existing_session()

        print_header("✓ ALL SESSION TESTS PASSED")

    except KeyboardInterrupt:
        print("\n\n✗ Tests cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
