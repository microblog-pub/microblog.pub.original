import asyncio
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import fastapi
import httpx
import respx
from sqlalchemy.orm import Session


from app import activitypub as ap
from app import actor
from app import httpsig
from app import models
from app.actor import LOCAL_ACTOR
from app.ap_object import RemoteObject
from app.config import session_serializer
from app.database import AsyncSession
from app.database import async_session
from app.incoming_activities import fetch_next_incoming_activity
from app.incoming_activities import process_next_incoming_activity
from app.main import app
from tests import factories


@contextmanager
def mock_httpsig_checker(
    ra: actor.RemoteActor,
    has_valid_signature: bool = True,
    is_ap_actor_gone: bool = False,
):
    async def httpsig_checker(
        request: fastapi.Request,
    ) -> httpsig.HTTPSigInfo:
        return httpsig.HTTPSigInfo(
            has_valid_signature=has_valid_signature,
            signed_by_ap_actor_id=ra.ap_id,
            is_ap_actor_gone=is_ap_actor_gone,
        )

    app.dependency_overrides[httpsig.httpsig_checker] = httpsig_checker
    try:
        yield
    finally:
        del app.dependency_overrides[httpsig.httpsig_checker]


def generate_admin_session_cookies() -> dict[str, Any]:
    return {"session": session_serializer.dumps({"is_logged_in": True})}


def setup_remote_actor(
    respx_mock: respx.MockRouter,
    base_url="https://example.com",
    also_known_as=None,
) -> actor.RemoteActor:
    ra = factories.RemoteActorFactory(
        base_url=base_url,
        username="toto",
        public_key="pk",
        also_known_as=also_known_as if also_known_as else [],
    )
    respx_mock.get(ra.ap_id + "/outbox").mock(
        return_value=httpx.Response(
            200,
            json={
                "@context": ap.AS_EXTENDED_CTX,
                "id": f"{ra.ap_id}/outbox",
                "type": "OrderedCollection",
                "totalItems": 0,
                "orderedItems": [],
            },
        )
    )
    respx_mock.get(ra.ap_id).mock(return_value=httpx.Response(200, json=ra.ap_actor))
    return ra


def setup_remote_actor_as_follower(ra: actor.RemoteActor) -> models.Follower:
    actor = factories.ActorFactory.from_remote_actor(ra)

    follow_id = uuid4().hex
    follow_from_inbox = RemoteObject(
        factories.build_follow_activity(
            from_remote_actor=ra,
            for_remote_actor=LOCAL_ACTOR,
            outbox_public_id=follow_id,
        ),
        ra,
    )
    inbox_object = factories.InboxObjectFactory.from_remote_object(
        follow_from_inbox, actor
    )

    follower = factories.FollowerFactory(
        inbox_object_id=inbox_object.id,
        actor_id=actor.id,
        ap_actor_id=actor.ap_id,
    )
    return follower


def setup_remote_actor_as_following(ra: actor.RemoteActor) -> models.Following:
    actor = factories.ActorFactory.from_remote_actor(ra)

    follow_id = uuid4().hex
    follow_from_outbox = RemoteObject(
        factories.build_follow_activity(
            from_remote_actor=LOCAL_ACTOR,
            for_remote_actor=ra,
            outbox_public_id=follow_id,
        ),
        LOCAL_ACTOR,
    )
    outbox_object = factories.OutboxObjectFactory.from_remote_object(
        follow_id, follow_from_outbox
    )

    following = factories.FollowingFactory(
        outbox_object_id=outbox_object.id,
        actor_id=actor.id,
        ap_actor_id=actor.ap_id,
    )
    return following


def setup_remote_actor_as_following_and_follower(
    ra: actor.RemoteActor,
) -> tuple[models.Following, models.Follower]:
    actor = factories.ActorFactory.from_remote_actor(ra)

    follow_id = uuid4().hex
    follow_from_outbox = RemoteObject(
        factories.build_follow_activity(
            from_remote_actor=LOCAL_ACTOR,
            for_remote_actor=ra,
            outbox_public_id=follow_id,
        ),
        LOCAL_ACTOR,
    )
    outbox_object = factories.OutboxObjectFactory.from_remote_object(
        follow_id, follow_from_outbox
    )

    following = factories.FollowingFactory(
        outbox_object_id=outbox_object.id,
        actor_id=actor.id,
        ap_actor_id=actor.ap_id,
    )

    follow_id = uuid4().hex
    follow_from_inbox = RemoteObject(
        factories.build_follow_activity(
            from_remote_actor=ra,
            for_remote_actor=LOCAL_ACTOR,
            outbox_public_id=follow_id,
        ),
        ra,
    )
    inbox_object = factories.InboxObjectFactory.from_remote_object(
        follow_from_inbox, actor
    )

    follower = factories.FollowerFactory(
        inbox_object_id=inbox_object.id,
        actor_id=actor.id,
        ap_actor_id=actor.ap_id,
    )

    return following, follower


def setup_outbox_note(
    content: str = "Hello",
    to: list[str] | None = None,
    cc: list[str] | None = None,
    tags: list[ap.RawObject] | None = None,
    in_reply_to: str | None = None,
) -> models.OutboxObject:
    note_id = uuid4().hex
    note_from_outbox = RemoteObject(
        factories.build_note_object(
            from_remote_actor=LOCAL_ACTOR,
            outbox_public_id=note_id,
            content=content,
            to=to,
            cc=cc,
            tags=tags,
            in_reply_to=in_reply_to,
        ),
        LOCAL_ACTOR,
    )
    return factories.OutboxObjectFactory.from_remote_object(note_id, note_from_outbox)


def setup_inbox_note(
    actor: models.Actor,
    content: str = "Hello",
    to: list[str] | None = None,
    cc: list[str] | None = None,
    tags: list[ap.RawObject] | None = None,
    in_reply_to: str | None = None,
) -> models.OutboxObject:
    note_id = uuid4().hex
    note_from_outbox = RemoteObject(
        factories.build_note_object(
            from_remote_actor=actor,
            outbox_public_id=note_id,
            content=content,
            to=to,
            cc=cc,
            tags=tags,
            in_reply_to=in_reply_to,
        ),
        actor,
    )
    return factories.InboxObjectFactory.from_remote_object(note_from_outbox, actor)


def setup_inbox_delete(
    actor: models.Actor, deleted_object_ap_id: str
) -> models.InboxObject:
    follow_from_inbox = RemoteObject(
        factories.build_delete_activity(
            from_remote_actor=actor,
            deleted_object_ap_id=deleted_object_ap_id,
        ),
        actor,
    )
    inbox_object = factories.InboxObjectFactory.from_remote_object(
        follow_from_inbox, actor
    )
    return inbox_object


def run_async(func, *args, **kwargs):
    async def _func():
        async with async_session() as db:
            return await func(db, *args, **kwargs)

    asyncio.run(_func())


async def _process_next_incoming_activity(db_session: AsyncSession) -> None:
    next_activity = await fetch_next_incoming_activity(db_session)
    assert next_activity
    await process_next_incoming_activity(db_session, next_activity)


def run_process_next_incoming_activity() -> None:
    run_async(_process_next_incoming_activity)


async def setup_auth_application_client(db: Session):
    # adds auth app client to db
    client = models.OAuthClient(
        client_name="testclient",
        redirect_uris="testuri",
        client_id="testclientid",
        client_secret="testclientsecret",
    )

    db.add(client)
    await db.commit()


async def setup_auth_auth_token(db: Session):
    # adds authorized access token to DB
    await setup_auth_application_client(db)
    auth_request = models.IndieAuthAuthorizationRequest(
        code="accesscode",
        scope="create",
        redirect_uri="testuri",
        client_id="testclientid",
        code_challenge="",
        code_challenge_method="",
    )

    db.add(auth_request)

    await db.commit()


async def setup_auth_access_token(db: Session):
    # adds authorized access token to DB
    await setup_auth_auth_token(db)
    access_token = models.IndieAuthAccessToken(
        indieauth_authorization_request_id=1,
        access_token="accesstoken",
        refresh_token="refreshtoken",
        expires_in=3600,
        scope="create update",
    )
    db.add(access_token)
    await db.commit()
