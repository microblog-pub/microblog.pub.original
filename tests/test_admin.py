import typing

import starlette
from fastapi.testclient import TestClient

from activitypub import activitypub as ap
from app.config import generate_csrf_token
from app.main import app
from tests.utils import generate_admin_session_cookies


def test_admin_endpoints_are_authenticated(client: TestClient) -> None:
    routes_tested = []

    for route in app.routes:
        route = typing.cast(starlette.routing.Route, route)
        if not route.path.startswith("/admin") or route.path == "/admin/login":
            continue

        for method in route.methods:  # type: ignore
            resp = client.request(method, route.path, follow_redirects=False)

            # Admin routes should redirect to the login page
            assert resp.status_code == 302, f"{method} {route.path} is unauthenticated"
            assert resp.headers.get("Location", "").startswith(
                "http://testserver/admin/login"
            )
            routes_tested.append((method, route.path))

    assert len(routes_tested) > 0


def test_public_works_authenticated(client: TestClient) -> None:
    response = client.post(
        "/admin/actions/new",
        data={
            "content": "hello",
            "redirect_url": "http://testserver/",
            "visibility": ap.VisibilityEnum.PUBLIC.name,
            "csrf_token": generate_csrf_token(),
        },
        cookies=generate_admin_session_cookies(),
        follow_redirects=False,
    )
    assert response.status_code == 302
    resp = client.get("/", cookies=generate_admin_session_cookies())
    assert resp.status_code == 200
