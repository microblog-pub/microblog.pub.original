from unittest import mock

import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import activitypub.models
from activitypub import activitypub as ap
from app import models
from app import webfinger
from activitypub.actor import LOCAL_ACTOR
from app.config import generate_csrf_token
from tests.utils import generate_admin_session_cookies
from tests.utils import setup_inbox_note
from tests.utils import setup_outbox_note
from tests.utils import setup_remote_actor
from tests.utils import setup_remote_actor_as_follower


def test_outbox__no_activities(
    db: Session,
    client: TestClient,
) -> None:
    response = client.get("/outbox", headers={"Accept": ap.AP_CONTENT_TYPE})

    assert response.status_code == 200

    json_response = response.json()
    assert json_response["totalItems"] == 0
    assert json_response["orderedItems"] == []


def test_send_follow_request(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    response = client.post(
        "/admin/actions/follow",
        data={
            "redirect_url": "http://testserver/",
            "ap_actor_id": ra.ap_id,
            "csrf_token": generate_csrf_token(),
        },
        cookies=generate_admin_session_cookies(),
        follow_redirects=False,
    )

    # Then the server returns a 302
    assert response.status_code == 302
    assert response.headers.get("Location") == "http://testserver/"

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Follow"
    assert outbox_object.activity_object_ap_id == ra.ap_id

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == ra.inbox_url


def test_send_delete__reverts_side_effects(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    # who is a follower
    follower = setup_remote_actor_as_follower(ra)
    actor = follower.actor

    # with a note that has existing replies
    inbox_note = setup_inbox_note(actor)
    # with a bogus counter
    inbox_note.replies_count = 5
    db.commit()

    # and 2 local replies
    setup_outbox_note(
        to=[ap.AS_PUBLIC],
        cc=[LOCAL_ACTOR.followers_collection_id],  # type: ignore
        in_reply_to=inbox_note.ap_id,
    )
    outbox_note2 = setup_outbox_note(
        to=[ap.AS_PUBLIC],
        cc=[LOCAL_ACTOR.followers_collection_id],  # type: ignore
        in_reply_to=inbox_note.ap_id,
    )
    db.commit()

    # When deleting one of the replies
    response = client.post(
        "/admin/actions/delete",
        data={
            "redirect_url": "http://testserver/",
            "ap_object_id": outbox_note2.ap_id,
            "csrf_token": generate_csrf_token(),
        },
        cookies=generate_admin_session_cookies(),
        follow_redirects=False,
    )

    # Then the server returns a 302
    assert response.status_code == 302
    assert response.headers.get("Location") == "http://testserver/"

    # And the Delete activity was created in the outbox
    outbox_object = db.execute(
        select(activitypub.models.OutboxObject).where(activitypub.models.OutboxObject.ap_type == "Delete")
    ).scalar_one()
    assert outbox_object.ap_type == "Delete"
    assert outbox_object.activity_object_ap_id == outbox_note2.ap_id

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == ra.inbox_url

    # And the replies count of the replied object was refreshed correctly
    db.refresh(inbox_note)
    assert inbox_note.replies_count == 1


def test_send_create_activity__no_content(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "redirect_url": "http://testserver/",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
            },
            cookies=generate_admin_session_cookies(),
        )

    # Then the server returns a 422
    assert response.status_code == 422


def test_send_create_activity__with_attachment(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "content": "hello",
                "redirect_url": "http://testserver/",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
            },
            files=[
                ("files", ("attachment.txt", "hello")),
            ],
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Note"
    assert outbox_object.summary is None
    assert outbox_object.content == "<p>hello</p>\n"
    assert len(outbox_object.attachments) == 1
    attachment = outbox_object.attachments[0]
    assert attachment.type == "Document"

    attachment_response = client.get(attachment.url)
    assert attachment_response.status_code == 200
    assert attachment_response.content == b"hello"

    upload = db.execute(select(activitypub.models.Upload)).scalar_one()
    assert upload.content_hash == (
        "324dcf027dd4a30a932c441f365a25e86b173defa4b8e58948253471b81b72cf"
    )

    outbox_attachment = db.execute(select(activitypub.models.OutboxObjectAttachment)).scalar_one()
    assert outbox_attachment.upload_id == upload.id
    assert outbox_attachment.outbox_object_id == outbox_object.id
    assert outbox_attachment.filename == "attachment.txt"


def test_send_create_activity__no_content_with_cw_and_attachments(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "content_warning": "cw",
                "redirect_url": "http://testserver/",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
            },
            files={"files": ("attachment.txt", "hello")},
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Note"
    assert outbox_object.summary is None
    assert outbox_object.content == "<p>cw</p>\n"
    assert len(outbox_object.attachments) == 1


def test_send_create_activity__no_followers_and_with_mention(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "redirect_url": "http://testserver/",
                "content": "hi @toto@example.com",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
            },
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Note"

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == ra.inbox_url


def test_send_create_activity__with_followers(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    # who is a follower
    follower = setup_remote_actor_as_follower(ra)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "redirect_url": "http://testserver/",
                "content": "hi followers",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
            },
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Note"

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == follower.actor.inbox_url


def test_send_create_activity__question__one_of(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    # who is a follower
    follower = setup_remote_actor_as_follower(ra)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "redirect_url": "http://testserver/",
                "content": "hi followers",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
                "poll_type": "oneOf",
                "poll_duration": "5",
                "poll_answer_1": "A",
                "poll_answer_2": "B",
            },
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Question"
    assert outbox_object.is_one_of_poll is True
    assert len(outbox_object.poll_items) == 2
    assert {pi["name"] for pi in outbox_object.poll_items} == {"A", "B"}
    assert outbox_object.is_poll_ended is False

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == follower.actor.inbox_url


def test_send_create_activity__question__any_of(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    # who is a follower
    follower = setup_remote_actor_as_follower(ra)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "redirect_url": "http://testserver/",
                "content": "hi followers",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
                "poll_type": "anyOf",
                "poll_duration": "10",
                "poll_answer_1": "A",
                "poll_answer_2": "B",
                "poll_answer_3": "C",
                "poll_answer_4": "D",
            },
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Question"
    assert outbox_object.is_one_of_poll is False
    assert len(outbox_object.poll_items) == 4
    assert {pi["name"] for pi in outbox_object.poll_items} == {"A", "B", "C", "D"}
    assert outbox_object.is_poll_ended is False

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == follower.actor.inbox_url


def test_send_create_activity__article(
    db: Session,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    # given a remote actor
    ra = setup_remote_actor(respx_mock)

    # who is a follower
    follower = setup_remote_actor_as_follower(ra)

    with mock.patch.object(webfinger, "get_actor_url", return_value=ra.ap_id):
        response = client.post(
            "/admin/actions/new",
            data={
                "redirect_url": "http://testserver/",
                "content": "hi followers",
                "visibility": ap.VisibilityEnum.PUBLIC.name,
                "csrf_token": generate_csrf_token(),
                "name": "Article",
            },
            cookies=generate_admin_session_cookies(),
            follow_redirects=False,
        )

    # Then the server returns a 302
    assert response.status_code == 302

    # And the Follow activity was created in the outbox
    outbox_object = db.execute(select(activitypub.models.OutboxObject)).scalar_one()
    assert outbox_object.ap_type == "Article"
    assert outbox_object.ap_object["name"] == "Article"

    # And an outgoing activity was queued
    outgoing_activity = db.execute(select(activitypub.models.OutgoingActivity)).scalar_one()
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == follower.actor.inbox_url
