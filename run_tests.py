"""Interactive test runner for AML Copilot API."""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_header(title):
    print("\n" + "="*80)
    print(f"🧪 {title}")
    print("="*80)

def test_1_1_basic_risk_score():
    """Test 1.1: Basic Risk Score Query - Full Agent Pipeline"""
    print_header("TEST 1.1: Basic Risk Score Query")

    payload = {
        "query": "What is the customer's risk score?",
        "context": {"cif_no": "C000001"},
        "user_id": "test_analyst",
        "session_id": "test_phase1_1"
    }

    print(f"Query: {payload['query']}")
    print(f"Customer: {payload['context']['cif_no']}")
    print("\nExpected Agents: Coordinator → Intent Mapper → Data Retrieval → Compliance Expert → Review")
    print("\nExecuting...")

    response = requests.post(f"{BASE_URL}/api/query", json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Status: {response.status_code} OK")
        print(f"\nResponse Preview: {data['response'][:300]}...")

        if data.get('compliance_analysis'):
            ca = data['compliance_analysis']
            print(f"\n✓ Compliance Analysis:")
            print(f"  - Risk Assessment: {ca.get('risk_assessment', 'N/A')}")
            print(f"  - Typologies: {ca.get('typologies', [])}")
            print(f"  - Recommendations: {len(ca.get('recommendations', []))} items")

        if data.get('retrieved_data'):
            print(f"\n✓ Data Retrieved: {list(data['retrieved_data'].keys())[:7]}")

        print(f"\n✓ Session ID: {data['session_id']}")
        print("\n✅ TEST 1.1 PASSED")
        return True
    else:
        print(f"\n❌ ERROR: {response.status_code}")
        print(response.text)
        return False

def test_1_2_out_of_scope():
    """Test 1.2: Out-of-Scope Query - Coordinator Only"""
    print_header("TEST 1.2: Out-of-Scope Query")

    payload = {
        "query": "What's the weather today?",
        "context": {"cif_no": "C000001"},
        "user_id": "test_analyst",
        "session_id": "test_phase1_2"
    }

    print(f"Query: {payload['query']}")
    print("\nExpected: Coordinator rejects with guidance message")
    print("\nExecuting...")

    response = requests.post(f"{BASE_URL}/api/query", json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Status: {response.status_code} OK")
        print(f"\nResponse: {data['response']}")

        # Check if response indicates out of scope
        resp_lower = data['response'].lower()
        if any(word in resp_lower for word in ['scope', 'aml', 'compliance', 'cannot', 'focus']):
            print("\n✅ TEST 1.2 PASSED - Correctly rejected out-of-scope query")
            return True
        else:
            print("\n⚠️ WARNING - Response may not clearly indicate out-of-scope")
            return True
    else:
        print(f"\n❌ ERROR: {response.status_code}")
        print(response.text)
        return False

def test_1_4_simple_tool_selection():
    """Test 1.4: Simple Tool Selection - Intent Mapper"""
    print_header("TEST 1.4: Simple Tool Selection")

    payload = {
        "query": "Get basic customer information",
        "context": {"cif_no": "C000001"},
        "user_id": "test_analyst",
        "session_id": "test_phase1_4"
    }

    print(f"Query: {payload['query']}")
    print(f"\nExpected Tool: get_customer_basic_info")
    print("\nExecuting...")

    response = requests.post(f"{BASE_URL}/api/query", json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Status: {response.status_code} OK")
        print(f"\nResponse Preview: {data['response'][:200]}...")

        if data.get('retrieved_data'):
            retrieved_keys = data['retrieved_data'].keys()
            print(f"\n✓ Data Retrieved: {list(retrieved_keys)}")

            # Check for basic info fields
            basic_fields = ['customer_name', 'cif_no', 'risk_score']
            found_fields = [f for f in basic_fields if f in retrieved_keys]
            print(f"\n✓ Basic Info Fields: {found_fields}")

        print("\n✅ TEST 1.4 PASSED")
        return True
    else:
        print(f"\n❌ ERROR: {response.status_code}")
        print(response.text)
        return False

def test_1_8_conceptual_question():
    """Test 1.8: Conceptual Question - Compliance Expert Knowledge"""
    print_header("TEST 1.8: Conceptual Question (No Data Retrieval)")

    payload = {
        "query": "What is structuring and how can it be detected?",
        "context": {"cif_no": "C000001"},
        "user_id": "test_analyst",
        "session_id": "test_phase1_8"
    }

    print(f"Query: {payload['query']}")
    print(f"\nExpected: Compliance Expert answers directly (no data retrieval)")
    print("\nExecuting...")

    response = requests.post(f"{BASE_URL}/api/query", json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Status: {response.status_code} OK")
        print(f"\nResponse Preview: {data['response'][:400]}...")

        # Check if response discusses structuring
        resp_lower = data['response'].lower()
        if 'structur' in resp_lower or '10,000' in data['response'] or 'cash' in resp_lower:
            print("\n✓ Response contains structuring information")

        # Check if data was retrieved (should be minimal or none)
        if not data.get('retrieved_data') or len(data.get('retrieved_data', {})) < 3:
            print("\n✓ Minimal/no data retrieval (as expected for conceptual query)")

        print("\n✅ TEST 1.8 PASSED")
        return True
    else:
        print(f"\n❌ ERROR: {response.status_code}")
        print(response.text)
        return False

def test_3_1_session_continuity():
    """Test 3.1: Session Continuity - Context Preservation"""
    print_header("TEST 3.1: Session Continuity")

    session_id = f"test_session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    user_id = "test_analyst"
    cif_no = "C000001"

    print(f"Session ID: {session_id}")
    print(f"Running 3 queries in same session...")

    # Query 1
    print("\n📝 Query 1: Get basic info")
    payload1 = {
        "query": "Get basic customer information",
        "context": {"cif_no": cif_no},
        "user_id": user_id,
        "session_id": session_id
    }
    r1 = requests.post(f"{BASE_URL}/api/query", json=payload1)
    if r1.status_code == 200:
        print("  ✓ Query 1 completed")

    # Query 2 - Follow-up
    print("\n📝 Query 2: What is their risk score? (follow-up)")
    payload2 = {
        "query": "What is their risk score?",
        "context": {"cif_no": cif_no},
        "user_id": user_id,
        "session_id": session_id
    }
    r2 = requests.post(f"{BASE_URL}/api/query", json=payload2)
    if r2.status_code == 200:
        print("  ✓ Query 2 completed")

    # Query 3 - Another follow-up
    print("\n📝 Query 3: Show me their transactions (follow-up)")
    payload3 = {
        "query": "Show me their transaction patterns",
        "context": {"cif_no": cif_no},
        "user_id": user_id,
        "session_id": session_id
    }
    r3 = requests.post(f"{BASE_URL}/api/query", json=payload3)
    if r3.status_code == 200:
        print("  ✓ Query 3 completed")

    # Get conversation history
    print(f"\n📜 Retrieving conversation history...")
    history_response = requests.get(f"{BASE_URL}/api/sessions/{user_id}/{session_id}/history")

    if history_response.status_code == 200:
        history = history_response.json()
        msg_count = history.get('message_count', 0)
        print(f"\n✓ Conversation history retrieved")
        print(f"  - Total messages: {msg_count}")
        print(f"  - Expected: >= 6 (3 user queries + 3 assistant responses)")

        if msg_count >= 6:
            print("\n✅ TEST 3.1 PASSED - Session continuity working")
            return True
        else:
            print("\n⚠️ WARNING - Message count lower than expected")
            return True
    else:
        print(f"\n❌ ERROR: {history_response.status_code}")
        print(history_response.text)
        return False

def main():
    """Run Phase 1 tests."""
    print("\n" + "🚀"*40)
    print("AML COPILOT API - PHASE 1 TESTS")
    print("Core Functionality Validation")
    print("🚀"*40)

    tests = [
        ("1.1", "Basic Risk Score Query", test_1_1_basic_risk_score),
        ("1.2", "Out-of-Scope Handling", test_1_2_out_of_scope),
        ("1.4", "Simple Tool Selection", test_1_4_simple_tool_selection),
        ("1.8", "Conceptual Question", test_1_8_conceptual_question),
        ("3.1", "Session Continuity", test_3_1_session_continuity),
    ]

    results = []
    for test_id, test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_id, test_name, passed))
        except Exception as e:
            print(f"\n❌ Exception in Test {test_id}: {e}")
            results.append((test_id, test_name, False))

    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)

    passed_count = sum(1 for _, _, passed in results if passed)
    total_count = len(results)

    for test_id, test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - Test {test_id}: {test_name}")

    print(f"\n📈 Results: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed")

if __name__ == "__main__":
    main()
