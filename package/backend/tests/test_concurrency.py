import asyncio
import unittest

from app.services.concurrency import ConcurrencyManager


class ConcurrencyManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_limit_queues_without_blocking_another_user(self):
        manager = ConcurrencyManager(max_concurrent=2)

        self.assertTrue(await manager.acquire("user-1-a", user_id=1, user_limit=1))
        waiting = asyncio.create_task(
            manager.acquire("user-1-b", user_id=1, user_limit=1, timeout=2)
        )
        await asyncio.sleep(0.02)

        self.assertTrue(await manager.acquire("user-2-a", user_id=2, user_limit=1))
        status = await manager.get_status("user-1-b")
        self.assertEqual(status["current_users"], 2)
        self.assertEqual(status["queue_length"], 1)
        self.assertEqual(status["your_position"], 1)

        await manager.release("user-1-a")
        self.assertTrue(await asyncio.wait_for(waiting, timeout=1))
        await manager.release("user-1-b")
        await manager.release("user-2-a")

    async def test_increasing_user_limit_activates_waiting_task(self):
        manager = ConcurrencyManager(max_concurrent=3)
        self.assertTrue(await manager.acquire("first", user_id=7, user_limit=1))
        waiting = asyncio.create_task(
            manager.acquire("second", user_id=7, user_limit=1, timeout=2)
        )
        await asyncio.sleep(0.02)

        await manager.update_user_limit(7, 2)
        self.assertTrue(await asyncio.wait_for(waiting, timeout=1))
        self.assertEqual(manager.get_active_count(), 2)
        await manager.release("first")
        await manager.release("second")

    async def test_cancel_queued_task_does_not_release_running_slot(self):
        manager = ConcurrencyManager(max_concurrent=1)
        self.assertTrue(await manager.acquire("active", user_id=1, user_limit=1))
        waiting = asyncio.create_task(
            manager.acquire("queued", user_id=2, user_limit=1, timeout=2)
        )
        await asyncio.sleep(0.02)

        self.assertTrue(await manager.cancel_queued("queued"))
        self.assertFalse(await asyncio.wait_for(waiting, timeout=1))
        self.assertTrue(manager.is_active("active"))
        await manager.release("active")


if __name__ == "__main__":
    unittest.main()
