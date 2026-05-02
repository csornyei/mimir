from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from shared.logger import logger


class WSSender:
    """Fault-tolerant wrapper around a WebSocket connection.

    After the first send failure (disconnect or stale connection), all
    subsequent sends are silent no-ops. Handlers can check `closed` to
    skip expensive work, but must never abort processing based on it —
    the pipeline always runs to completion and saves to the DB.
    """

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    async def send(self, msg: dict) -> None:
        if self._closed:
            return
        try:
            await self._ws.send_json(msg)
        except WebSocketDisconnect:
            self._closed = True
        except RuntimeError:
            # Raised when sending on a closed/closing connection
            self._closed = True
        except Exception as e:
            logger.warning(
                "ws_sender_unexpected_error", error=str(e), error_type=type(e).__name__
            )
            self._closed = True
