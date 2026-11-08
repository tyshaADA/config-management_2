import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

MIN_DEPTH = 0
INITIAL_DEPTH = 0


def validate_config(config):
    """Проверяет наличие, типы и корректность параметров конфигурации."""
    required_keys = {
        "package_name": str,
        "repo_url": str,
        "test_mode": bool,
        "package_version": str,
        "ascii_tree_mode": bool,
        "max_depth": int,
        "filter_substring": str,
    }
    for key, expected_type in required_keys.items():
        if key not in config:
            print(f"Ошибка: Отсутствует параметр '{key}'.")
            sys.exit(1)
        if not isinstance(config[key], expected_type):
            print(
                f"Ошибка: Параметр '{key}' должен иметь тип "
                f"{expected_type.__name__}."
            )
            sys.exit(1)
    if config["max_depth"] < MIN_DEPTH:
        print("Ошибка: Параметр 'max_depth' не может быть отрицательным.")
        sys.exit(1)


def load_config(config_path="config.json"):
    """Загружает конфигурационный файл JSON."""
    if not os.path.exists(config_path):
        print(f"Ошибка: Файл '{config_path}' не найден.")
        sys.exit(1)
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as error:
        print(f"Ошибка: Некорректный формат JSON. {error}")
        sys.exit(1)
    validate_config(config)
    return config


def build_pom_url(repo_url, package_name, version):
    """Формирует прямой URL-адрес к POM-файлу пакета в Maven."""
    if not repo_url.endswith("/"):
        repo_url += "/"
    if ":" not in package_name:
        print("Ошибка: Имя пакета должно быть в формате groupId:artifactId.")
        sys.exit(1)
    group_id, artifact_id = package_name.split(":", 1)
    group_path = group_id.replace(".", "/")
    pom_name = f"{artifact_id}-{version}.pom"
    return f"{repo_url}{group_path}/{artifact_id}/{version}/{pom_name}"


def fetch_pom_xml(pom_url):
    """Скачивает содержимое POM-файла по указанному URL."""
    request = urllib.request.Request(
        pom_url, headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.read()
    except Exception as error:
        print(f"Ошибка при скачивании {pom_url}: {error}")
        return None


def extract_properties(root, namespace):
    """Извлекает словарь свойств (переменных версий) из POM-файла."""
    props = {}
    props_node = root.find(f"{namespace}properties")
    if props_node is not None:
        for prop in props_node:
            tag_name = prop.tag.replace(namespace, "")
            props[tag_name] = (prop.text or "").strip()
    return props


def resolve_version(raw_version, props):
    """Подставляет значение переменной версии из словаря свойств."""
    if raw_version.startswith("${") and raw_version.endswith("}"):
        prop_key = raw_version[2:-1]
        return props.get(prop_key, "")
    return raw_version


def extract_dep_item(dep_node, namespace, props):
    """Извлекает имя и актуальную версию зависимости из XML-узла."""
    group_node = dep_node.find(f"{namespace}groupId")
    artifact_node = dep_node.find(f"{namespace}artifactId")
    version_node = dep_node.find(f"{namespace}version")
    if group_node is None or artifact_node is None:
        return None
    group_text = (group_node.text or "").strip()
    artifact_text = (artifact_node.text or "").strip()
    raw_ver = ""
    if version_node is not None and version_node.text:
        raw_ver = version_node.text.strip()
    actual_ver = resolve_version(raw_ver, props)
    return f"{group_text}:{artifact_text}", actual_ver


def parse_maven_dependencies(pom_content):
    """Извлекает список кортежей (пакет, версия) из XML POM-файла."""
    if not pom_content:
        return []
    try:
        root = ET.fromstring(pom_content)
    except ET.ParseError:
        return []
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    props = extract_properties(root, namespace)
    deps_node = root.find(f"{namespace}dependencies")
    if deps_node is None:
        return []
    result = []
    for dep in deps_node.findall(f"{namespace}dependency"):
        item = extract_dep_item(dep, namespace, props)
        if item is not None:
            result.append(item)
    return result


def load_test_repository(file_path):
    """Загружает граф зависимостей из текстового тестового репозитория."""
    if not os.path.exists(file_path):
        print(f"Ошибка: Тестовый файл '{file_path}' не найден.")
        sys.exit(1)
    repo_graph = {}
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            clean_line = line.strip()
            if not clean_line or ":" not in clean_line:
                continue
            pkg, raw_deps = clean_line.split(":", 1)
            deps_list = [d.strip() for d in raw_deps.split(",") if d.strip()]
            repo_graph[pkg.strip()] = deps_list
    return repo_graph


def is_filtered(package_name, filter_substring):
    """Проверяет, должен ли пакет быть исключен по подстроке."""
    if not filter_substring:
        return False
    return filter_substring in package_name


def get_next_dependencies(pkg, version, config, test_repo):
    """Возвращает прямые зависимости пакета для текущего режима работы."""
    if config["test_mode"]:
        return [(dep, "") for dep in test_repo.get(pkg, [])]
    if not version:
        return []
    pom_url = build_pom_url(config["repo_url"], pkg, version)
    pom_xml = fetch_pom_xml(pom_url)
    return parse_maven_dependencies(pom_xml)


def build_dependency_graph(config):
    """Строит граф зависимостей алгоритмом DFS без рекурсии."""
    test_repo = {}
    if config["test_mode"]:
        test_repo = load_test_repository(config["repo_url"])
    start_pkg = config["package_name"]
    filter_sub = config["filter_substring"]
    graph = {}
    if is_filtered(start_pkg, filter_sub):
        return graph
    stack = [(start_pkg, config["package_version"], INITIAL_DEPTH)]
    visited = set()
    while stack:
        current_pkg, current_ver, depth = stack.pop()
        if current_pkg in visited:
            continue
        visited.add(current_pkg)
        graph[current_pkg] = []
        if depth >= config["max_depth"]:
            continue
        raw_deps = get_next_dependencies(
            current_pkg, current_ver, config, test_repo
        )
        for dep_name, dep_ver in raw_deps:
            if is_filtered(dep_name, filter_sub):
                continue
            graph[current_pkg].append(dep_name)
            if dep_name not in visited:
                stack.append((dep_name, dep_ver, depth + 1))
    return graph


def main():
    """Запускает построение и вывод графа зависимостей."""
    config = load_config()
    graph = build_dependency_graph(config)
    print(f"Граф зависимостей для '{config['package_name']}':")
    if not graph:
        print("Граф пуст (пакет отфильтрован или не найден).")
    for package, deps in graph.items():
        deps_str = ", ".join(deps) if deps else "нет зависимостей"
        print(f"  {package} -> [{deps_str}]")


if __name__ == "__main__":
    main()