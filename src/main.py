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

import sys
from pathlib import Path
import time
from dotenv import load_dotenv

from manager.system_manager import SystemManager
from logger.set_logger import operation_logger


def main():
    try:
        # ? Since __init__() for every class will activate them, no need to do anything here.
        project_root = Path(__file__).resolve().parents[1]
        load_dotenv(project_root / ".env")

        main_system_manager: SystemManager = SystemManager()
        operation_logger.info(
            f"{main_system_manager} has been started."
        )

        # Start working
        while True:
            time.sleep(0.5)  # Sleep to reduce the cpu usage.
    except RuntimeError as e:
        operation_logger.critical(
            f"{__name__}: function main() has raised an RuntimeError: {str(e)}"
        )
        sys.exit(1)
    except Exception as e:
        operation_logger.critical(
            f"{__name__}: function main() has raised an Unexpected error starting the system: {str(e)}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
