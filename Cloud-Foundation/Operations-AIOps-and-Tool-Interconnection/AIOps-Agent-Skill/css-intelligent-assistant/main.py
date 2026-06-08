"""Simplified CSS Elasticity Agent entrypoint."""

import logging
import sys

from config import get_settings
from engine import ElasticityEngine
from server import create_app, start_background_loop


def main():
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Settings loaded: cluster=%s min=%d max=%d step_out=%d step_in=%d",
                settings.cluster_id, settings.min_nodes, settings.max_nodes,
                settings.scale_out_step, settings.scale_in_step)

    engine = ElasticityEngine(settings)
    app = create_app(settings, engine)
    start_background_loop(engine, settings)

    logger.info("Starting dashboard on %s:%d", settings.server_host, settings.server_port)
    app.run(host=settings.server_host, port=settings.server_port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
