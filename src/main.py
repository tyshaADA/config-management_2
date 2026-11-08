import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

MIN_DEPTH = 0


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
        print(f"Ошибка при скачивании POM-файла: {error}")
        sys.exit(1)


def parse_dependencies(pom_content):
    """Извлекает список прямых зависимостей из XML-содержимого POM-файла."""
    try:
        root = ET.fromstring(pom_content)
    except ET.ParseError as error:
        print(f"Ошибка парсинга XML: {error}")
        sys.exit(1)
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    dependencies = []
    deps_node = root.find(f"{namespace}dependencies")
    if deps_node is None:
        return dependencies
    for dep in deps_node.findall(f"{namespace}dependency"):
        group_node = dep.find(f"{namespace}groupId")
        artifact_node = dep.find(f"{namespace}artifactId")
        if group_node is not None and artifact_node is not None:
            group_text = (group_node.text or "").strip()
            artifact_text = (artifact_node.text or "").strip()
            dependencies.append(f"{group_text}:{artifact_text}")
    return dependencies


def main():
    """Запускает сбор и вывод прямых зависимостей пакета."""
    config = load_config()
    pom_url = build_pom_url(
        config["repo_url"],
        config["package_name"],
        config["package_version"],
    )
    pom_content = fetch_pom_xml(pom_url)
    dependencies = parse_dependencies(pom_content)
    print(f"Прямые зависимости для {config['package_name']}:")
    if not dependencies:
        print("Прямые зависимости не найдены.")
    for dependency in dependencies:
        print(f"- {dependency}")


if __name__ == "__main__":
    main()