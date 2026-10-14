"""Enforce actual peer locality before dispatching the optional MCP transport."""

from ipaddress import ip_address

from starlette.responses import PlainTextResponse


class LoopbackOnly:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            peer = scope.get("client")
            allowed = False
            if isinstance(peer, (tuple, list)) and len(peer) == 2:
                host, port = peer
                if (
                    isinstance(host, str)
                    and "%" not in host
                    and isinstance(port, int)
                    and not isinstance(port, bool)
                    and 0 <= port <= 65535
                ):
                    try:
                        allowed = ip_address(host).is_loopback
                    except ValueError:
                        pass
            if not allowed:
                await PlainTextResponse("MCP requires a loopback peer", status_code=403)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)
