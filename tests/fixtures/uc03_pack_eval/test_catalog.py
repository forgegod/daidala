"""Frozen behavior checks for the canonical UC-03 fixture."""

import unittest

from resource_fixture.catalog import resource_names


class ResourceNamesTests(unittest.TestCase):
    def test_returns_only_sorted_top_level_text_resources(self) -> None:
        self.assertEqual(resource_names(), ("alpha.txt", "beta.txt"))


if __name__ == "__main__":
    unittest.main()
