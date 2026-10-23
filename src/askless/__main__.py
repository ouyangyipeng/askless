import argparse
from pathlib import Path

import uvicorn

from askless.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="AskLess local workbench")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=Path(".askless"))
    args = parser.parse_args()
    uvicorn.run(create_app(args.data_dir), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
