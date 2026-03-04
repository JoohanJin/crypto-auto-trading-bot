# STANDARD LIBRARY
import json
from pathlib import Path
from typing import Any

# CUSTOM LIBRARY
from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)


class StrategyFetcher:
    def __init__(self, config_path: str | Path, name: str | None = None) -> None:
        self.name: str = name if name else "STRATEGY_FETCHER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        self.config_path = Path(config_path)

    def load_strategies(self) -> dict[str, Any]:
        """
        Load strategies configuration from a JSON file.
        """
        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                config = json.load(file)
                strategies: list[dict[str, Any]] = config.get("strategies", [])
                self.logger.info(
                    f"[STRATEGY_LOAD] Count: {len(strategies)} | Source: {self.config_path}"
                )
                return config
        except FileNotFoundError:
            self.logger.critical(
                f"[STRATEGY_ERROR] load_strategies() | Error: FileNotFoundError: {self.config_path}"
            )
            return {"strategies": []}
        except json.JSONDecodeError as e:
            self.logger.critical(
                f"[STRATEGY_ERROR] load_strategies() | Error: JSONDecodeError: {e!s}"
            )
            return {"strategies": []}
        except Exception as e:
            self.logger.critical(
                f"[STRATEGY_ERROR] load_strategies() | Error: {type(e).__name__}: {e!s}"
            )
            return {"strategies": []}
