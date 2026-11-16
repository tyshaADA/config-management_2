import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("src"))
from main import build_dependency_graph, get_load_order

DEPTH_FULL = 10
DEPTH_ONE = 1
DEPTH_ZERO = 0


def make_test_config(pkg, max_depth=DEPTH_FULL, filter_sub=""):
    """Формирует словарь конфигурации для тестового репозитория."""
    return {
        "package_name": pkg,
        "repo_url": "test_repo.txt",
        "test_mode": True,
        "package_version": "1.0",
        "ascii_tree_mode": True,
        "max_depth": max_depth,
        "filter_substring": filter_sub,
    }


class TestDependencyGraph(unittest.TestCase):
    """Тесты построения графа и порядка загрузки зависимостей."""

    def test_cycles_and_diamond_graph(self):
        """Проверяет обработку циклов и общих (ромбовидных) узлов."""
        config = make_test_config("A", filter_sub="TEST")
        graph = build_dependency_graph(config)
        self.assertIn("A", graph)
        self.assertIn("E", graph)
        self.assertIn("I", graph)
        self.assertNotIn("X_TEST", graph)
        self.assertNotIn("Y_TEST", graph)
        self.assertNotIn("Z", graph)

    def test_max_depth_limit(self):
        """Проверяет обрезку транзитивного графа по максимальной глубине."""
        config = make_test_config("A", max_depth=DEPTH_ONE)
        graph = build_dependency_graph(config)
        self.assertEqual(set(graph.keys()), {"A", "B", "C", "X_TEST"})
        self.assertEqual(graph["B"], [])

    def test_zero_depth(self):
        """Проверяет поведение при нулевой глубине анализа."""
        config = make_test_config("C", max_depth=DEPTH_ZERO)
        graph = build_dependency_graph(config)
        self.assertEqual(graph, {"C": []})

    def test_root_package_filtered(self):
        """Проверяет исключение корневого пакета, если он попал под фильтр."""
        config = make_test_config("X_TEST", filter_sub="TEST")
        graph = build_dependency_graph(config)
        self.assertEqual(graph, {})

    def test_isolated_component_load_order(self):
        """Проверяет порядок загрузки для простой ветки Z -> M."""
        config = make_test_config("Z")
        graph = build_dependency_graph(config)
        order = get_load_order(graph, "Z")
        self.assertEqual(order, ["M", "Z"])

    def test_load_order_dependencies_before_root(self):
        """Проверяет, что зависимости загружаются строго раньше корня."""
        config = make_test_config("A", filter_sub="TEST")
        graph = build_dependency_graph(config)
        order = get_load_order(graph, "A")
        self.assertEqual(order[-1], "A")
        self.assertLess(order.index("I"), order.index("F"))
        self.assertLess(order.index("F"), order.index("B"))


if __name__ == "__main__":
    unittest.main()