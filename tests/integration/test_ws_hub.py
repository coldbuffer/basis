import asyncio
import threading

from basis.domain.tenancy.realtime.hub import GraphWsHub


class _FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.closed = False
        self.close_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code


def test_disconnect_user_from_workspace_closes_matching_sockets() -> None:
    async def run() -> None:
        hub = GraphWsHub()
        socket = _FakeWebSocket()
        await hub.connect("kb-1", socket, "user-a")
        other = _FakeWebSocket()
        await hub.connect("kb-1", other, "user-b")

        closed = await hub.disconnect_user_from_workspace("kb-1", "user-a")
        assert closed == 1
        assert socket.sent[-1]["type"] == "access_revoked"
        assert socket.close_code == 4403
        assert other.closed is False

    asyncio.run(run())


def test_disconnect_user_closes_all_workspace_sockets() -> None:
    async def run() -> None:
        hub = GraphWsHub()
        a = _FakeWebSocket()
        b = _FakeWebSocket()
        await hub.connect("kb-a", a, "user-x")
        await hub.connect("kb-b", b, "user-x")

        closed = await hub.disconnect_user("user-x")
        assert closed == 2
        assert a.close_code == 4403
        assert b.close_code == 4403

    asyncio.run(run())


def test_broadcast_only_reaches_target_workspace_room() -> None:
    async def run() -> None:
        hub = GraphWsHub()
        a = _FakeWebSocket()
        b = _FakeWebSocket()
        await hub.connect("kb-a", a, "user-1")
        await hub.connect("kb-b", b, "user-1")

        await hub.broadcast(
            "kb-a",
            {"type": "projection_updated", "workspace_id": "kb-a", "projection_revision": 3},
        )

        assert len(a.sent) == 1
        assert a.sent[0]["workspace_id"] == "kb-a"
        assert b.sent == []

    asyncio.run(run())


def test_try_broadcast_without_event_loop_is_noop() -> None:
    hub = GraphWsHub()
    hub.try_broadcast("kb-1", {"type": "projection_updated", "workspace_id": "kb-1"})


def test_try_broadcast_from_worker_thread() -> None:
    async def run() -> None:
        hub = GraphWsHub()
        socket = _FakeWebSocket()
        await hub.connect("kb-1", socket, "user-a")

        done = threading.Event()

        def worker() -> None:
            hub.try_broadcast(
                "kb-1",
                {"type": "projection_updated", "workspace_id": "kb-1", "projection_revision": 9},
            )
            done.set()

        threading.Thread(target=worker).start()
        for _ in range(50):
            if socket.sent:
                break
            await asyncio.sleep(0.02)
        assert done.is_set()
        assert socket.sent[-1]["type"] == "projection_updated"
        assert socket.sent[-1]["projection_revision"] == 9

    asyncio.run(run())
