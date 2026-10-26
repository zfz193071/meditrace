import io
import logging
import logging.config

from uvicorn.protocols.utils import get_path_with_query_string

from referral_review.operations.access_logging import access_log_config


def test_uvicorn_callback_logs_keep_path_and_status_without_credentials():
    output = io.StringIO()
    config = access_log_config()
    config["handlers"]["access"]["stream"] = output
    logger = logging.getLogger("uvicorn.access")
    previous = (logger.handlers[:], logger.level, logger.propagate)
    try:
        logging.config.dictConfig(config)
        path = get_path_with_query_string({"path": "/api/v1/auth/github/callback",
            "query_string": b"code=synthetic-code-sentinel&state=synthetic-state-sentinel"})
        logger.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1234", "GET", path, "1.1", 303)
        logged = output.getvalue()
        assert "/api/v1/auth/github/callback" in logged and "303" in logged
        assert "synthetic-code-sentinel" not in logged
        assert "synthetic-state-sentinel" not in logged
        assert "?" not in logged
        logger.info("unexpected secret-bearing access message")
        assert "unexpected" not in output.getvalue()
    finally:
        logger.handlers, logger.level, logger.propagate = previous
