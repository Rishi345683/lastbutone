import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DATABASE_FILE.close()
os.environ["COSTOPTI_DB_PATH"] = _DATABASE_FILE.name

from app.database import (
    get_connection,
    initialize_database,
    list_saved_audit_logs,
    list_saved_recommendations,
    update_recommendation,
)
from app.simulator import (
    analyze_resources,
    decide_recommendation,
    execute_recommendation,
    ensure_demo_recommendation,
    list_metrics,
    list_recommendations,
    list_virtual_machines,
)


class BackendWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        initialize_database()
        with get_connection() as connection:
            connection.execute("DELETE FROM audit_logs")
            connection.execute("DELETE FROM recommendations")

    def tearDown(self) -> None:
        pass

    def test_simulator_has_resources_and_weekly_metrics(self) -> None:
        self.assertEqual(len(list_virtual_machines()), 20)
        self.assertEqual(len(list_metrics()), 140)
        self.assertEqual(len(analyze_resources()), 20)

    def test_underutilized_resources_generate_recommendations(self) -> None:
        recommendations = list_recommendations()
        self.assertEqual(len(recommendations), 12)
        self.assertTrue(
            all(item.status == "pending_approval" for item in recommendations)
        )
        self.assertEqual(len(list_saved_recommendations()), 12)

    def test_demo_seed_resets_one_recommendation_without_duplicates(self) -> None:
        recommendations = list_recommendations()
        for recommendation in recommendations:
            recommendation.status = "optimized"
            update_recommendation(recommendation)

        ensure_demo_recommendation()
        ensure_demo_recommendation()

        refreshed = list_saved_recommendations()
        pending = [item for item in refreshed if item.status == "pending_approval"]
        self.assertEqual(len(pending), 3)
        self.assertEqual(len({item.resource_id for item in refreshed}), 12)
        self.assertEqual(pending[0].waiting_period_hours, 3)
        self.assertTrue(all(item.approval_deadline for item in pending))
        self.assertEqual(len({item.resource_id for item in pending}), 3)

    def test_demo_seed_fills_partial_pending_batch(self) -> None:
        recommendations = list_recommendations()
        for recommendation in recommendations:
            recommendation.status = "optimized"
            update_recommendation(recommendation)

        first_pending = recommendations[0]
        first_pending.status = "pending_approval"
        update_recommendation(first_pending)
        ensure_demo_recommendation()

        pending = [
            item
            for item in list_saved_recommendations()
            if item.status == "pending_approval"
        ]
        self.assertEqual(len(pending), 3)
        self.assertEqual(len({item.resource_id for item in pending}), 3)

    def test_execution_requires_approval_and_persists_audit(self) -> None:
        recommendation = list_recommendations()[0]
        virtual_machine = next(
            item for item in list_virtual_machines()
            if item.id == recommendation.resource_id
        )
        expected_resize = (
            f"Resized {virtual_machine.vcpus} vCPU/{virtual_machine.ram_gb} GB RAM to "
            f"{max(1, virtual_machine.vcpus // 2)} vCPU/{max(1, virtual_machine.ram_gb // 2)} GB RAM"
        )
        self.assertEqual(
            execute_recommendation(recommendation.id),
            "recommendation_not_approved",
        )

        approved = decide_recommendation(recommendation.id, "approved")
        self.assertIsNotNone(approved)
        result = execute_recommendation(recommendation.id)

        self.assertIsNotNone(result)
        self.assertEqual(result[0].status, "optimized")
        audit_logs = list_saved_audit_logs()
        self.assertEqual(len(audit_logs), 2)
        self.assertEqual(audit_logs[0].action, "approval_decision")
        self.assertEqual(audit_logs[0].status, "approved")
        self.assertIn("Planned optimization:", audit_logs[0].message)
        self.assertIn(expected_resize, result[3])

    def test_expired_recommendation_is_auto_optimized(self) -> None:
        recommendation = list_recommendations()[0]
        recommendation.approval_deadline = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
        update_recommendation(recommendation)

        refreshed = list_recommendations()

        self.assertEqual(refreshed[0].status, "optimized")
        self.assertEqual(len(list_saved_audit_logs()), 1)
        self.assertIn("Resized ", list_saved_audit_logs()[0].message)


if __name__ == "__main__":
    unittest.main()
