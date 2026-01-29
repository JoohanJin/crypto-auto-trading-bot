# STANDARD LIBRARY
import json
from pathlib import Path
from typing import Any, Dict, List

# CUSTOM LIBRARY
from infrastructure.logging.set_logger import operation_logger


class StrategyFetcher:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)

    def load_strategies(self) -> dict[str, Any]:
        """
        Load strategies configuration from a JSON file.
        """
        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                config = json.load(file)
                strategies: List[Dict[str, Any]] = config.get("strategies", [])
                operation_logger.info(
                    f"{__name__} - Loaded {len(strategies)} strategies from {self.config_path}"
                )
                return config
        except FileNotFoundError:
            operation_logger.critical(f"{__name__} - Strategy config not found: {self.config_path}")
            return {"strategies": []}
        except json.JSONDecodeError as e:
            operation_logger.critical(
                f"{__name__} - Failed to decode strategy config {self.config_path}: {str(e)}"
            )
            return {"strategies": []}
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - Unexpected error loading strategies: {str(e)}"
            )
            return {"strategies": []}
