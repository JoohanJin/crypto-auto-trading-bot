"""
MIT License

Copyright (c) 2025 JoohanJin (Joe)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse

# Standard Library
import sys
import time

# Custom Library
from src import VERSION
from src.infrastructure.logging.set_logger import get_logger, set_global_log_level
from src.infrastructure.system_manager import SystemManager


logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="AutoCryptoTrading Bot")
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging (overrides .env)"
    )
    parser.add_argument(
        "--log-level", "-l",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set specific log level"
    )
    parser.add_argument(
        "--disable-trade", "-dt",
        action="store_true",
        help="Disable trade execution (Dry Run)"
    )

    args = parser.parse_args()

    try:
        # Resolve log level: CLI > Default(INFO)
        if args.debug:
            set_global_log_level("DEBUG")
        elif args.log_level:
            set_global_log_level(args.log_level)
        else:
            # Force INFO if no arguments provided, ensuring predictable default behavior
            set_global_log_level("INFO")

        # Load environment variables
        logger.info(f"[APP_START] AutoCryptoTrading Bot Version: {VERSION} | Loading environment configuration")

        # Initialize SystemManager
        # Pass disable_trade flag to SystemManager
        SystemManager(
            name="MAIN_APP",
            disable_trade=args.disable_trade
        )
        logger.info(f"[APP_INIT_COMPLETE] Application initialized | Status: ready | Trade Execution: {'DISABLED' if args.disable_trade else 'ENABLED'}")

        # Start main event loop
        logger.info("[APP_LOOP_START] Entering main event loop")
        while True:
            time.sleep(0.5)  # Sleep to reduce CPU usage

    except KeyboardInterrupt:
        logger.warning("[APP_SHUTDOWN] User interrupt received | Action: graceful shutdown")
        sys.exit(0)
    except RuntimeError as e:
        logger.critical(f"[MAIN_RUNTIME_ERROR] RuntimeError | Error: RuntimeError: {e!s}")
        sys.exit(1)
    except Exception as e:
        logger.critical(
            f"[APP_STARTUP_ERROR] Unexpected error during startup | Error: {type(e).__name__}: {e!s}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
