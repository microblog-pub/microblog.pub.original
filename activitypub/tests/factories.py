from urllib.parse import urlparse
from uuid import uuid4

import factory  # type: ignore
from Crypto.PublicKey import RSA
from dateutil.parser import isoparse
from sqlalchemy import orm

import activitypub.models
from activitypub import activitypub as ap, actor
from activitypub.actor import RemoteActor
from activitypub.ap_object import RemoteObject
from app.database import SessionLocal
from app.utils.datetime import now

_Session = orm.scoped_session(SessionLocal)


def generate_key() -> tuple[str, str]:
    k = RSA.generate(1024)
    return k.exportKey("PEM").decode(), k.publickey().exportKey("PEM").decode()


def build_follow_activity(
    from_remote_actor: actor.RemoteActor,
    for_remote_actor: actor.RemoteActor,
    outbox_public_id: str | None = None,
) -> ap.RawObject:
    return {
        "@context": ap.AS_CTX,
        "type": "Follow",
        "id": from_remote_actor.ap_id + "/follow/" + (outbox_public_id or uuid4().hex),
        "actor": from_remote_actor.ap_id,
        "object": for_remote_actor.ap_id,
    }


def build_delete_activity(
    from_remote_actor: actor.RemoteActor | activitypub.models.Actor,
    deleted_object_ap_id: str,
    outbox_public_id: str | None = None,
) -> ap.RawObject:
    return {
        "@context": ap.AS_CTX,
        "type": "Delete",
        "id": (
            from_remote_actor.ap_id  # type: ignore
            + "/follow/"
            + (outbox_public_id or uuid4().hex)
        ),
        "actor": from_remote_actor.ap_id,
        "object": deleted_object_ap_id,
    }


def build_accept_activity(
    from_remote_actor: actor.RemoteActor,
    for_remote_object: RemoteObject,
    outbox_public_id: str | None = None,
) -> ap.RawObject:
    return {
        "@context": ap.AS_CTX,
        "type": "Accept",
        "id": from_remote_actor.ap_id + "/accept/" + (outbox_public_id or uuid4().hex),
        "actor": from_remote_actor.ap_id,
        "object": for_remote_object.ap_id,
    }


def build_block_activity(
    from_remote_actor: actor.RemoteActor,
    for_remote_actor: actor.RemoteActor,
    outbox_public_id: str | None = None,
) -> ap.RawObject:
    return {
        "@context": ap.AS_CTX,
        "type": "Block",
        "id": from_remote_actor.ap_id + "/block/" + (outbox_public_id or uuid4().hex),
        "actor": from_remote_actor.ap_id,
        "object": for_remote_actor.ap_id,
    }


def build_move_activity(
    from_remote_actor: actor.RemoteActor,
    for_remote_object: actor.RemoteActor,
    outbox_public_id: str | None = None,
) -> ap.RawObject:
    return {
        "@context": ap.AS_CTX,
        "type": "Move",
        "id": from_remote_actor.ap_id + "/move/" + (outbox_public_id or uuid4().hex),
        "actor": from_remote_actor.ap_id,
        "object": from_remote_actor.ap_id,
        "target": for_remote_object.ap_id,
    }


def build_note_object(
    from_remote_actor: actor.RemoteActor | activitypub.models.Actor,
    outbox_public_id: str | None = None,
    content: str = "Hello",
    to: list[str] | None = None,
    cc: list[str] | None = None,
    tags: list[ap.RawObject] | None = None,
    in_reply_to: str | None = None,
) -> ap.RawObject:
    published = now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    context = from_remote_actor.ap_id + "/ctx/" + uuid4().hex
    note_id = outbox_public_id or uuid4().hex
    return {
        "@context": ap.AS_CTX,
        "type": "Note",
        "id": from_remote_actor.ap_id + "/note/" + note_id,
        "attributedTo": from_remote_actor.ap_id,
        "content": content,
        "to": to or [ap.AS_PUBLIC],
        "cc": cc or [],
        "published": published,
        "context": context,
        "conversation": context,
        "url": from_remote_actor.ap_id + "/note/" + note_id,
        "tag": tags or [],
        "summary": None,
        "sensitive": False,
        "inReplyTo": in_reply_to,
    }


def build_create_activity(obj: ap.RawObject) -> ap.RawObject:
    return {
        "@context": ap.AS_EXTENDED_CTX,
        "actor": obj["attributedTo"],
        "to": obj.get("to", []),
        "cc": obj.get("cc", []),
        "id": obj["id"] + "/activity",
        "object": ap.remove_context(obj),
        "published": obj["published"],
        "type": "Create",
    }


class BaseModelMeta:
    sqlalchemy_session = _Session
    sqlalchemy_session_persistence = "commit"


class RemoteActorFactory(factory.Factory):
    class Meta:
        model = RemoteActor
        exclude = (
            "base_url",
            "username",
            "public_key",
            "also_known_as",
        )

    class Params:
        icon_url = None
        summary = "I like unit tests"
        also_known_as: list[str] = []

    ap_actor = factory.LazyAttribute(
        lambda o: {
            "@context": ap.AS_CTX,
            "type": "Person",
            "id": o.base_url,
            "following": o.base_url + "/following",
            "followers": o.base_url + "/followers",
            # "featured": ID + "/featured",
            "inbox": o.base_url + "/inbox",
            "outbox": o.base_url + "/outbox",
            "preferredUsername": o.username,
            "name": o.username,
            "summary": o.summary,
            "endpoints": {},
            "url": o.base_url,
            "manuallyApprovesFollowers": False,
            "attachment": [],
            "icon": {},
            "publicKey": {
                "id": f"{o.base_url}#main-key",
                "owner": o.base_url,
                "publicKeyPem": o.public_key,
            },
            "alsoKnownAs": o.also_known_as,
        }
    )


class ActorFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta(BaseModelMeta):
        model = activitypub.models.Actor

    # ap_actor
    # ap_id
    ap_type = "Person"

    @classmethod
    def from_remote_actor(cls, ra):
        return cls(
            ap_type=ra.ap_type,
            ap_actor=ra.ap_actor,
            ap_id=ra.ap_id,
        )


class OutboxObjectFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta(BaseModelMeta):
        model = activitypub.models.OutboxObject

    # public_id
    # relates_to_inbox_object_id
    # relates_to_outbox_object_id

    @classmethod
    def from_remote_object(cls, public_id, ro):
        return cls(
            public_id=public_id,
            ap_type=ro.ap_type,
            ap_id=ro.ap_id,
            ap_context=ro.ap_context,
            ap_object=ro.ap_object,
            visibility=ro.visibility,
            og_meta=ro.og_meta,
            activity_object_ap_id=ro.activity_object_ap_id,
            is_hidden_from_homepage=True if ro.in_reply_to else False,
        )


class OutgoingActivityFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta(BaseModelMeta):
        model = activitypub.models.OutgoingActivity

    # recipient
    # outbox_object_id


class InboxObjectFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta(BaseModelMeta):
        model = activitypub.models.InboxObject

    @classmethod
    def from_remote_object(
        cls,
        ro: RemoteObject,
        actor: activitypub.models.Actor,
        relates_to_inbox_object_id: int | None = None,
        relates_to_outbox_object_id: int | None = None,
    ):
        ap_published_at = now()
        if "published" in ro.ap_object:
            ap_published_at = isoparse(ro.ap_object["published"])
        return cls(
            server=urlparse(ro.ap_id).hostname,
            actor_id=actor.id,
            ap_actor_id=actor.ap_id,
            ap_type=ro.ap_type,
            ap_id=ro.ap_id,
            ap_context=ro.ap_context,
            ap_published_at=ap_published_at,
            ap_object=ro.ap_object,
            visibility=ro.visibility,
            relates_to_inbox_object_id=relates_to_inbox_object_id,
            relates_to_outbox_object_id=relates_to_outbox_object_id,
            activity_object_ap_id=ro.activity_object_ap_id,
            # Hide replies from the stream
            is_hidden_from_stream=True if ro.in_reply_to else False,
        )


class FollowerFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta(BaseModelMeta):
        model = activitypub.models.Follower


class FollowingFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta(BaseModelMeta):
        model = activitypub.models.Following
