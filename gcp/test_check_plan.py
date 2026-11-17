import unittest

from check_plan import check


class PlanSafetyTests(unittest.TestCase):
    def plan(self, actions):
        return {
            "format_version": "1.2",
            "resource_changes": [
                {"address": "google_sql_database_instance.main", "change": {"actions": actions}}
            ],
        }

    def test_addition_and_update_are_allowed(self):
        for actions in (["create"], ["update"], ["no-op"]):
            self.assertEqual(check(self.plan(actions)), [])

    def test_deletion_and_both_replacement_orders_are_rejected(self):
        for actions in (["delete"], ["delete", "create"], ["create", "delete"]):
            self.assertEqual(check(self.plan(actions)), ["google_sql_database_instance.main"])

    def test_invalid_or_incomplete_plans_are_rejected(self):
        for plan in (
            {},
            {"format_version": "1.2", "complete": False},
            {"format_version": "1.2", "errored": True},
        ):
            with self.assertRaises(ValueError):
                check(plan)


if __name__ == "__main__":
    unittest.main()
