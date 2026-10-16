import logging

import uvicorn

from . import config
from .server import build_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    print(f"Voicebox client on http://{config.HOST}:{config.PORT} (Voicebox: {config.VOICEBOX_URL})")
    uvicorn.run(build_app(), host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
