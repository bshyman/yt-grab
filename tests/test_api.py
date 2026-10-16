import dataclasses

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app

ID = "dQw4w9WgXcQ"


@pytest.fixture
def make_client(tmp_path):
    def make(**overrides):
        (tmp_path / "music").mkdir(exist_ok=True)
        settings = dataclasses.replace(
            load_settings(),
            data_dir=tmp_path / "data",
            music_dir=tmp_path / "music",
            admin_password="hunter2",
            converters=(),
            **overrides,
        )
        # no `with` = lifespan never runs = no workers, jobs just sit queued
        return TestClient(create_app(settings))

    return make


def as_user(login):
    return {"tailscale-user-login": login}


def admin(client):
    assert client.post("/api/login", json={"password": "hunter2"}).status_code == 200
    return client


def test_friend_cant_add_to_library(make_client):
    c = make_client()
    r = c.post("/api/jobs", json={"video_id": ID, "mode": "library"}, headers=as_user("friend@x"))
    assert r.status_code == 403


def test_admin_can_add_to_library(make_client):
    c = admin(make_client())
    r = c.post("/api/jobs", json={"video_id": ID, "mode": "library"})
    assert r.status_code == 200
    assert r.json()["status"] == "queued"


def test_wrong_password(make_client):
    c = make_client()
    assert c.post("/api/login", json={"password": "nope"}).status_code == 401
    assert c.get("/api/me").json()["admin"] is False


def test_daily_limit(make_client):
    c = make_client(daily_limit=2)
    h = as_user("friend@x")
    for _ in range(2):
        assert c.post("/api/jobs", json={"video_id": ID}, headers=h).status_code == 200
    assert c.post("/api/jobs", json={"video_id": ID}, headers=h).status_code == 429
    # someone else still has their quota
    assert c.post("/api/jobs", json={"video_id": ID}, headers=as_user("other@x")).status_code == 200


def test_admin_skips_limit(make_client):
    c = admin(make_client(daily_limit=1))
    for _ in range(3):
        assert c.post("/api/jobs", json={"video_id": ID}).status_code == 200


def test_jobs_are_per_user(make_client):
    c = make_client()
    job = c.post("/api/jobs", json={"video_id": ID}, headers=as_user("a@x")).json()
    assert [j["id"] for j in c.get("/api/jobs", headers=as_user("a@x")).json()["jobs"]] == [job["id"]]
    assert c.get("/api/jobs", headers=as_user("b@x")).json()["jobs"] == []
    assert c.get(f"/api/jobs/{job['id']}/file", headers=as_user("b@x")).status_code == 404


def test_rejects_bad_video_id(make_client):
    c = make_client()
    assert c.post("/api/jobs", json={"video_id": "../../etc"}).status_code == 422


def test_playlist_link_explains_itself(make_client):
    c = make_client()
    r = c.get("/api/search", params={"q": "https://www.youtube.com/playlist?list=PL123"})
    assert r.status_code == 400
    assert "playlist" in r.json()["detail"]
