import json

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models
from app.config import generate_csrf_token
from app.config import session_serializer
from tests.utils import setup_auth_access_token


@pytest.mark.asyncio
async def test_micropub_create(
    client: TestClient,
    async_db_session: Session,
):
    # test that we create a note via micropub
    await setup_auth_access_token(async_db_session)

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer accesstoken",
    }

    body = {"type": ["h-entry"], "properties": {"content": ["Hello, World!"]}}
    response = client.post("/micropub", data=json.dumps(body), headers=headers)

    data = response.json()

    # assert success and the location of the new note
    assert response.status_code is 201
    assert "location" in response.headers

    new_path = f"/o/{response.headers.get("Location").split("/")[-1]}"
    res = client.get(new_path)

    # assert the new note is actually at the location
    assert "Hello, World!" in res.text
