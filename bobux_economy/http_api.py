import asyncio
import json
import logging

from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import request, Quart
from werkzeug.exceptions import HTTPException

app = Quart(__name__)


@app.route("/", methods=["POST"])
async def hello():
    req = await request.get_json(force=True)
    return req


@app.errorhandler(HTTPException)
async def handle_http_exception(ex: HTTPException):
    response = ex.get_response()
    response.data = json.dumps({
        "error": {
            "code": ex.code,
            "name": ex.name,
            "description": ex.description
        }
    })
    response.content_type = "application/json"
    return response


async def run():
    config = Config()
    config.bind = "0.0.0.0:42069"
    config.accesslog = logging.getLogger("http_api")
    config.access_log_format = "%(m)s %(U)s -> %(s)s [from %(a)s @ %(h)s]"
    config.errorlog = config.accesslog

    async def shutdown_trigger():
        # Wait for this coroutine to be cancelled
        await asyncio.Event().wait()
    await serve(app, config, shutdown_trigger=shutdown_trigger)
