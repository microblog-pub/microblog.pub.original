from uuid import uuid4

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select

import activitypub.models
from activitypub.actor import LOCAL_ACTOR
from activitypub.ap_object import RemoteObject
from app.database import AsyncSession
from activitypub.outgoing_activities import _MAX_RETRIES
from activitypub.outgoing_activities import fetch_next_outgoing_activity
from activitypub.outgoing_activities import new_outgoing_activity
from activitypub.outgoing_activities import process_next_outgoing_activity
from activitypub.tests import factories


def _setup_outbox_object() -> activitypub.models.OutboxObject:
    ra = factories.RemoteActorFactory(
        base_url="https://example.com",
        username="toto",
        public_key="pk",
    )

    # And a Follow activity in the outbox
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
    return outbox_object


@pytest.mark.asyncio
async def test_new_outgoing_activity(
    async_db_session: AsyncSession,
    client: TestClient,
    respx_mock: respx.MockRouter,
) -> None:
    outbox_object = _setup_outbox_object()
    inbox_url = "https://example.com/inbox"

    if not outbox_object.id:
        raise ValueError("Should never happen")

    # When queuing the activity
    outgoing_activity = await new_outgoing_activity(
        async_db_session, inbox_url, outbox_object.id
    )
    await async_db_session.commit()

    assert (
        await async_db_session.execute(select(activitypub.models.OutgoingActivity))
    ).scalar_one() == outgoing_activity
    assert outgoing_activity.outbox_object_id == outbox_object.id
    assert outgoing_activity.recipient == inbox_url


@pytest.mark.asyncio
async def test_process_next_outgoing_activity__no_next_activity(
    respx_mock: respx.MockRouter,
    async_db_session: AsyncSession,
) -> None:
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity is None


@pytest.mark.asyncio
async def test_process_next_outgoing_activity__server_200(
    async_db_session: AsyncSession,
    respx_mock: respx.MockRouter,
) -> None:
    # And an outgoing activity
    outbox_object = _setup_outbox_object()

    recipient_inbox_url = "https://example.com/users/toto/inbox"
    respx_mock.post(recipient_inbox_url).mock(return_value=httpx.Response(204))

    outgoing_activity = factories.OutgoingActivityFactory(
        recipient=recipient_inbox_url,
        outbox_object_id=outbox_object.id,
        inbox_object_id=None,
        webmention_target=None,
    )

    # When processing the next outgoing activity
    # Then it is processed
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity
    await process_next_outgoing_activity(async_db_session, next_activity)

    assert respx_mock.calls.call_count == 1

    outgoing_activity = (
        await async_db_session.execute(select(activitypub.models.OutgoingActivity))
    ).scalar_one()
    assert outgoing_activity.is_sent is True
    assert outgoing_activity.last_status_code == 204
    assert outgoing_activity.error is None
    assert outgoing_activity.is_errored is False


@pytest.mark.asyncio
async def test_process_next_outgoing_activity__webmention(
    async_db_session: AsyncSession,
    respx_mock: respx.MockRouter,
) -> None:
    # And an outgoing activity
    outbox_object = _setup_outbox_object()

    recipient_url = "https://example.com/webmention"
    respx_mock.post(recipient_url).mock(return_value=httpx.Response(204))

    outgoing_activity = factories.OutgoingActivityFactory(
        recipient=recipient_url,
        outbox_object_id=outbox_object.id,
        inbox_object_id=None,
        webmention_target="http://example.com",
    )

    # When processing the next outgoing activity
    # Then it is processed
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity
    await process_next_outgoing_activity(async_db_session, next_activity)

    assert respx_mock.calls.call_count == 1

    outgoing_activity = (
        await async_db_session.execute(select(activitypub.models.OutgoingActivity))
    ).scalar_one()
    assert outgoing_activity.is_sent is True
    assert outgoing_activity.last_status_code == 204
    assert outgoing_activity.error is None
    assert outgoing_activity.is_errored is False


@pytest.mark.asyncio
async def test_process_next_outgoing_activity__error_500(
    async_db_session: AsyncSession,
    respx_mock: respx.MockRouter,
) -> None:
    outbox_object = _setup_outbox_object()
    recipient_inbox_url = "https://example.com/inbox"
    respx_mock.post(recipient_inbox_url).mock(
        return_value=httpx.Response(500, text="oops")
    )

    # And an outgoing activity
    outgoing_activity = factories.OutgoingActivityFactory(
        recipient=recipient_inbox_url,
        outbox_object_id=outbox_object.id,
        inbox_object_id=None,
        webmention_target=None,
    )

    # When processing the next outgoing activity
    # Then it is processed
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity
    await process_next_outgoing_activity(async_db_session, next_activity)

    assert respx_mock.calls.call_count == 1

    outgoing_activity = (
        await async_db_session.execute(select(activitypub.models.OutgoingActivity))
    ).scalar_one()
    assert outgoing_activity.is_sent is False
    assert outgoing_activity.last_status_code == 500
    assert outgoing_activity.last_response == "oops"
    assert outgoing_activity.is_errored is False
    assert outgoing_activity.tries == 1


@pytest.mark.asyncio
async def test_process_next_outgoing_activity__errored(
    async_db_session: AsyncSession,
    respx_mock: respx.MockRouter,
) -> None:
    outbox_object = _setup_outbox_object()
    recipient_inbox_url = "https://example.com/inbox"
    respx_mock.post(recipient_inbox_url).mock(
        return_value=httpx.Response(500, text="oops")
    )

    # And an outgoing activity
    outgoing_activity = factories.OutgoingActivityFactory.create(
        recipient=recipient_inbox_url,
        outbox_object_id=outbox_object.id,
        inbox_object_id=None,
        webmention_target=None,
        tries=_MAX_RETRIES - 1,
    )

    # When processing the next outgoing activity
    # Then it is processed
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity
    await process_next_outgoing_activity(async_db_session, next_activity)

    assert respx_mock.calls.call_count == 1

    outgoing_activity = (
        await async_db_session.execute(select(activitypub.models.OutgoingActivity))
    ).scalar_one()
    assert outgoing_activity.is_sent is False
    assert outgoing_activity.last_status_code == 500
    assert outgoing_activity.last_response == "oops"
    assert outgoing_activity.is_errored is True

    # And it is skipped from processing
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity is None


@pytest.mark.asyncio
async def test_process_next_outgoing_activity__connect_error(
    async_db_session: AsyncSession,
    respx_mock: respx.MockRouter,
) -> None:
    outbox_object = _setup_outbox_object()
    recipient_inbox_url = "https://example.com/inbox"
    respx_mock.post(recipient_inbox_url).mock(side_effect=httpx.ConnectError)

    # And an outgoing activity
    outgoing_activity = factories.OutgoingActivityFactory(
        recipient=recipient_inbox_url,
        outbox_object_id=outbox_object.id,
        inbox_object_id=None,
        webmention_target=None,
    )

    # When processing the next outgoing activity
    # Then it is processed
    next_activity = await fetch_next_outgoing_activity(async_db_session)
    assert next_activity
    await process_next_outgoing_activity(async_db_session, next_activity)

    assert respx_mock.calls.call_count == 1

    outgoing_activity = (
        await async_db_session.execute(select(activitypub.models.OutgoingActivity))
    ).scalar_one()
    assert outgoing_activity.is_sent is False
    assert outgoing_activity.error is not None
    assert outgoing_activity.tries == 1


# TODO(ts):
# - parse retry after
