"""Unit tests for conversation memory, session isolation, and thread safety."""

import concurrent.futures
import unittest

from riverwood.memory import ConversationStore


class MemoryStoreTests(unittest.TestCase):
    def test_session_isolation(self) -> None:
        store = ConversationStore(max_turns=5)
        store.append("session-a", "User A question", "Agent A answer")
        store.append("session-b", "User B question", "Agent B answer")

        messages_a = store.as_messages("session-a")
        messages_b = store.as_messages("session-b")

        self.assertEqual(len(messages_a), 2)
        self.assertEqual(messages_a[0]["content"], "User A question")
        self.assertEqual(messages_a[1]["content"], "Agent A answer")

        self.assertEqual(len(messages_b), 2)
        self.assertEqual(messages_b[0]["content"], "User B question")
        self.assertEqual(messages_b[1]["content"], "Agent B answer")

        # Cross-session contamination check
        self.assertNotIn("User B", [m["content"] for m in messages_a])
        self.assertNotIn("User A", [m["content"] for m in messages_b])

    def test_turn_limit_eviction(self) -> None:
        store = ConversationStore(max_turns=2)
        store.append("session-1", "Q1", "A1")
        store.append("session-1", "Q2", "A2")
        store.append("session-1", "Q3", "A3")

        messages = store.as_messages("session-1")
        # Should keep only 2 turns (4 messages: Q2, A2, Q3, A3)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["content"], "Q2")
        self.assertEqual(messages[2]["content"], "Q3")

    def test_capacity_lru_eviction(self) -> None:
        store = ConversationStore(max_turns=5, max_sessions=2)
        store.append("s1", "Q1", "A1")
        store.append("s2", "Q2", "A2")
        self.assertEqual(store.session_count(), 2)

        # Access s1 so s2 becomes older
        _ = store.as_messages("s1")

        # Adding s3 should evict s2
        store.append("s3", "Q3", "A3")
        self.assertEqual(store.session_count(), 2)
        self.assertEqual(len(store.as_messages("s1")), 2)
        self.assertEqual(len(store.as_messages("s3")), 2)
        self.assertEqual(len(store.as_messages("s2")), 0)  # Evicted

    def test_clear_session(self) -> None:
        store = ConversationStore()
        store.append("s1", "Q1", "A1")
        store.append("s2", "Q2", "A2")

        store.clear("s1")
        self.assertEqual(len(store.as_messages("s1")), 0)
        self.assertEqual(len(store.as_messages("s2")), 2)

        store.clear()
        self.assertEqual(store.session_count(), 0)

    def test_concurrent_access_thread_safety(self) -> None:
        store = ConversationStore(max_turns=10, max_sessions=50)

        def worker(idx: int) -> None:
            session_id = f"session-{idx % 10}"
            for turn in range(20):
                store.append(session_id, f"User {turn}", f"Agent {turn}")
                _ = store.as_messages(session_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(30)]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        self.assertLessEqual(store.session_count(), 10)


if __name__ == "__main__":
    unittest.main()
