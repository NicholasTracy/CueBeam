import pytest
from httpx import AsyncClient
from cuebeam.web.app import make_app



class DummyManager:
    def status(self):
        return {}

    def reload_media(self):
        pass

    def ensure_idle_playing(self):
        pass

    def pause_toggle(self):
        pass

    def skip(self):
        pass

    def trigger_event(self):
        pass

    def trigger_random(self):
        pass

    def shutdown_pi(self):
        pass

    def reboot_pi(self):
        pass

    cfg = {}



   
    a@pytest.mark.asyncio
async def test_ping_endpoint():
        app = make_app(DummyManager())
    async with AsyncClient(app=app, base_url="http://test") as client:
    
        response = await client.get("/api/ping")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
