import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models
from app.config import generate_csrf_token
from app.config import session_serializer
from tests.utils import setup_auth_application_client
from tests.utils import setup_auth_auth_token


def test_oauth_registration(
    client: TestClient,
):
    # test we can register an application
    register_client_request = {
        "client_name": "testclient",
        "redirect_uris": ["testuri"],
    }

    response = client.post(
        "/oauth/register",
        headers={"Content-Type": "application/json", "charset": "utf-8"},
        json=register_client_request,
    )
    data = response.json()
    assert "client_id" in data
    assert "client_secret" in data


@pytest.mark.asyncio
async def test_oauth_authorize(
    client: TestClient,
    async_db_session: Session,
):
    # test that when logged in, we can see the authorize app page with all the relevant good bits
    await setup_auth_application_client(async_db_session)

    confirmation = {
        "client_id": "testclientid",
        "scope": "create",
        "redirect_uri": "testuri",
        "csrf_token": generate_csrf_token(),
        "state": "",
        "code_challenge": "",
        "code_challenge_method": "",
    }

    logged_in_cookie = {"session": session_serializer.dumps({"is_logged_in": True})}
    pageresponse = client.get(
        "/auth?client_id=testclientid&redirect_uri=testuri&response_type=code&scope=create",
        cookies=logged_in_cookie,
    )
    data = pageresponse.text
    for f in confirmation.keys():
        assert f in data

    # confirm that we can actually authorize the app, and get an auth code back.
    response = client.post(
        "/admin/indieauth",
        headers={"charset": "utf-8"},
        cookies=logged_in_cookie,
        data=confirmation,
    )
    assert response.status_code is 200
    assert "code=" in response.headers.get("refresh")


@pytest.mark.asyncio
async def test_oauth_access_token(
    client: TestClient,
    async_db_session: Session,
):
    # test that we can get an access token
    await setup_auth_auth_token(async_db_session)

    token_request = {
        "client_id": "testclientid",
        "code": "accesscode",
        "redirect_uri": "testuri",
    }

    logged_in_cookie = {"session": session_serializer.dumps({"is_logged_in": True})}
    response = client.post("/token", data=token_request)

    data = response.json()
    assert response.status_code is 200
    assert "access_token" in data
    assert "refresh_token" in data


# TODO: add refresh token test
# TODO: add indiauth client tests
