import asyncio
import json
import logging

from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import jsonify, make_response, Quart, request
from werkzeug.exceptions import HTTPException

from bobux_economy import errors

app = Quart(__name__)


@app.route("/", methods=["POST"])
async def hello():
    req = await request.get_json(force=True)
    return req


@app.errorhandler(HTTPException)
async def handle_http_exception(ex: HTTPException):
    response = ex.get_response()
    response.data = json.dumps({
        "http_error": {
            "code": ex.code,
            "name": ex.name,
            "description": ex.description
        }
    })
    response.content_type = "application/json"
    return response

@app.errorhandler(errors.Failed)
async def handle_failure(ex: errors.Failed):
    return make_response(jsonify({
        "error": {
            "type": type(ex).__name__,
            "message": ex.message,
            "http_status": ex.http_status
        }
    }), ex.http_status)


async def run():
    config = Config()
    config.bind = "0.0.0.0:42069"
    app._logger = logging.getLogger("http_api")
    config.accesslog = app.logger
    config.access_log_format = "%(m)s %(U)s -> %(s)s [from %(a)s @ %(h)s]"
    config.errorlog = app.logger

    async def shutdown_trigger():
        # Wait for this coroutine to be cancelled
        await asyncio.Event().wait()
    await serve(app, config, shutdown_trigger=shutdown_trigger)
