import json
import os
import sys

def load_config(config_path="config.json"):
    """Загружает и валидирует конфигурационный файл JSON."""
    if not os.path.exists(config_path):
        print(f"Ошибка: Файл '{config_path}' не найден.")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка: Некорректный формат JSON. {e}")
        sys.exit(1)

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
            print(f"Ошибка: Отсутствует обязательный параметр '{key}'.")
            sys.exit(1)
        if not isinstance(config[key], expected_type):
            print(
                f"Ошибка: Параметр '{key}' должен иметь тип "
                f"{expected_type.__name__}."
            )
            sys.exit(1)

    if config["max_depth"] < 0:
        print("Ошибка: Параметр 'max_depth' не может быть отрицательным.")
        sys.exit(1)

    return config

def main():
    print("=== Инициализация CLI-приложения ===")
    config = load_config()

    print("\nУспешно загруженные параметры конфигурации:")
    for key, value in config.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()