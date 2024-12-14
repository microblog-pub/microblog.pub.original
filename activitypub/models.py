from typing import Optional, Any, Union

from sqlalchemy import Column, Integer, DateTime, String, JSON, Boolean, ForeignKey, Enum, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, relationship

from activitypub import activitypub as ap
from activitypub.actor import Actor as BaseActor, LOCAL_ACTOR
from activitypub.ap_object import Object as BaseObject, Attachment
from app.config import BASE_URL
from app.database import Base
from app.utils.datetime import now


class Actor(Base, BaseActor):
    __tablename__ = "actor"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)

    ap_id: Mapped[str] = Column(String, unique=True, nullable=False, index=True)
    ap_actor: Mapped[ap.RawObject] = Column(JSON, nullable=False)
    ap_type = Column(String, nullable=False)

    handle = Column(String, nullable=True, index=True)

    is_blocked = Column(Boolean, nullable=False, default=False, server_default="0")
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="0")

    are_announces_hidden_from_stream = Column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    @property
    def is_from_db(self) -> bool:
        return True


class InboxObject(Base, BaseObject):
    __tablename__ = "inbox"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)

    actor_id = Column(Integer, ForeignKey("actor.id"), nullable=False)
    actor: Mapped[Actor] = relationship(Actor, uselist=False)

    server = Column(String, nullable=False)

    is_hidden_from_stream = Column(Boolean, nullable=False, default=False)

    ap_actor_id = Column(String, nullable=False)
    ap_type = Column(String, nullable=False, index=True)
    ap_id: Mapped[str] = Column(String, nullable=False, unique=True, index=True)
    ap_context = Column(String, nullable=True)
    ap_published_at = Column(DateTime(timezone=True), nullable=False)
    ap_object: Mapped[ap.RawObject] = Column(JSON, nullable=False)

    # Only set for activities
    activity_object_ap_id = Column(String, nullable=True, index=True)

    visibility = Column(Enum(ap.VisibilityEnum), nullable=False)
    conversation = Column(String, nullable=True)

    has_local_mention = Column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    # Used for Like, Announce and Undo activities
    relates_to_inbox_object_id = Column(
        Integer,
        ForeignKey("inbox.id"),
        nullable=True,
    )
    relates_to_inbox_object: Mapped[Optional["InboxObject"]] = relationship(
        "InboxObject",
        foreign_keys=relates_to_inbox_object_id,
        remote_side=id,
        uselist=False,
    )
    relates_to_outbox_object_id = Column(
        Integer,
        ForeignKey("outbox.id"),
        nullable=True,
    )
    relates_to_outbox_object: Mapped[Optional["OutboxObject"]] = relationship(
        "OutboxObject",
        foreign_keys=[relates_to_outbox_object_id],
        uselist=False,
    )

    undone_by_inbox_object_id = Column(Integer, ForeignKey("inbox.id"), nullable=True)

    # Link the oubox AP ID to allow undo without any extra query
    liked_via_outbox_object_ap_id = Column(String, nullable=True)
    announced_via_outbox_object_ap_id = Column(String, nullable=True)
    voted_for_answers: Mapped[list[str] | None] = Column(JSON, nullable=True)

    is_bookmarked = Column(Boolean, nullable=False, default=False)

    # Used to mark deleted objects, but also activities that were undone
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_transient = Column(Boolean, nullable=False, default=False, server_default="0")

    replies_count: Mapped[int] = Column(Integer, nullable=False, default=0)

    og_meta: Mapped[list[dict[str, Any]] | None] = Column(JSON, nullable=True)

    @property
    def relates_to_anybox_object(self) -> Union["InboxObject", "OutboxObject"] | None:
        if self.relates_to_inbox_object_id:
            return self.relates_to_inbox_object
        elif self.relates_to_outbox_object_id:
            return self.relates_to_outbox_object
        else:
            return None

    @property
    def is_from_db(self) -> bool:
        return True

    @property
    def is_from_inbox(self) -> bool:
        return True


class OutboxObject(Base, BaseObject):
    __tablename__ = "outbox"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)

    is_hidden_from_homepage = Column(Boolean, nullable=False, default=False)

    public_id = Column(String, nullable=False, index=True)
    slug = Column(String, nullable=True, index=True)

    ap_type = Column(String, nullable=False, index=True)
    ap_id: Mapped[str] = Column(String, nullable=False, unique=True, index=True)
    ap_context = Column(String, nullable=True)
    ap_object: Mapped[ap.RawObject] = Column(JSON, nullable=False)

    activity_object_ap_id = Column(String, nullable=True, index=True)

    # Source content for activities (like Notes)
    source = Column(String, nullable=True)
    revisions: Mapped[list[dict[str, Any]] | None] = Column(JSON, nullable=True)

    ap_published_at = Column(DateTime(timezone=True), nullable=False, default=now)
    visibility = Column(Enum(ap.VisibilityEnum), nullable=False)
    conversation = Column(String, nullable=True)

    likes_count = Column(Integer, nullable=False, default=0)
    announces_count = Column(Integer, nullable=False, default=0)
    replies_count: Mapped[int] = Column(Integer, nullable=False, default=0)
    webmentions_count: Mapped[int] = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # reactions: Mapped[list[dict[str, Any]] | None] = Column(JSON, nullable=True)

    og_meta: Mapped[list[dict[str, Any]] | None] = Column(JSON, nullable=True)

    # For the featured collection
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_transient = Column(Boolean, nullable=False, default=False, server_default="0")

    # Never actually delete from the outbox
    is_deleted = Column(Boolean, nullable=False, default=False)

    # Used for Create, Like, Announce and Undo activities
    relates_to_inbox_object_id = Column(
        Integer,
        ForeignKey("inbox.id"),
        nullable=True,
    )
    relates_to_inbox_object: Mapped[Optional["InboxObject"]] = relationship(
        "InboxObject",
        foreign_keys=[relates_to_inbox_object_id],
        uselist=False,
    )
    relates_to_outbox_object_id = Column(
        Integer,
        ForeignKey("outbox.id"),
        nullable=True,
    )
    relates_to_outbox_object: Mapped[Optional["OutboxObject"]] = relationship(
        "OutboxObject",
        foreign_keys=[relates_to_outbox_object_id],
        remote_side=id,
        uselist=False,
    )
    # For Follow activies
    relates_to_actor_id = Column(
        Integer,
        ForeignKey("actor.id"),
        nullable=True,
    )
    relates_to_actor: Mapped[Optional["Actor"]] = relationship(
        "Actor",
        foreign_keys=[relates_to_actor_id],
        uselist=False,
    )

    undone_by_outbox_object_id = Column(Integer, ForeignKey("outbox.id"), nullable=True)

    @property
    def actor(self) -> BaseActor:
        return LOCAL_ACTOR

    outbox_object_attachments: Mapped[list["OutboxObjectAttachment"]] = relationship(
        "OutboxObjectAttachment", uselist=True, backref="outbox_object"
    )

    @property
    def attachments(self) -> list[Attachment]:
        out = []
        for attachment in self.outbox_object_attachments:
            url = (
                BASE_URL
                + f"/attachments/{attachment.upload.content_hash}/{attachment.filename}"
            )
            out.append(
                Attachment.parse_obj(
                    {
                        "type": "Document",
                        "mediaType": attachment.upload.content_type,
                        "name": attachment.alt or attachment.filename,
                        "url": url,
                        "width": attachment.upload.width,
                        "height": attachment.upload.height,
                        "proxiedUrl": url,
                        "resizedUrl": (
                            BASE_URL
                            + (
                                "/attachments/thumbnails/"
                                f"{attachment.upload.content_hash}"
                                f"/{attachment.filename}"
                            )
                            if attachment.upload.has_thumbnail
                            else None
                        ),
                    }
                )
            )
        return out

    @property
    def relates_to_anybox_object(self) -> Union["InboxObject", "OutboxObject"] | None:
        if self.relates_to_inbox_object_id:
            return self.relates_to_inbox_object
        elif self.relates_to_outbox_object_id:
            return self.relates_to_outbox_object
        else:
            return None

    @property
    def is_from_db(self) -> bool:
        return True

    @property
    def is_from_outbox(self) -> bool:
        return True

    @property
    def url(self) -> str | None:
        # XXX: rewrite old URL here for compat
        if self.ap_type == "Article" and self.slug and self.public_id:
            return f"{BASE_URL}/articles/{self.public_id[:7]}/{self.slug}"
        return super().url


class Follower(Base):
    __tablename__ = "follower"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)

    actor_id = Column(Integer, ForeignKey("actor.id"), nullable=False, unique=True)
    actor: Mapped[Actor] = relationship(Actor, uselist=False)

    inbox_object_id = Column(Integer, ForeignKey("inbox.id"), nullable=False)
    inbox_object = relationship(InboxObject, uselist=False)

    ap_actor_id = Column(String, nullable=False, unique=True)


class Following(Base):
    __tablename__ = "following"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)

    actor_id = Column(Integer, ForeignKey("actor.id"), nullable=False, unique=True)
    actor = relationship(Actor, uselist=False)

    outbox_object_id = Column(Integer, ForeignKey("outbox.id"), nullable=False)
    outbox_object = relationship(OutboxObject, uselist=False)

    ap_actor_id = Column(String, nullable=False, unique=True)


class IncomingActivity(Base):
    __tablename__ = "incoming_activity"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

    # An incoming activity can be a webmention
    webmention_source = Column(String, nullable=True)
    # or an AP object
    sent_by_ap_actor_id = Column(String, nullable=True)
    ap_id = Column(String, nullable=True, index=True)
    ap_object: Mapped[ap.RawObject] = Column(JSON, nullable=True)

    tries: Mapped[int] = Column(Integer, nullable=False, default=0)
    next_try = Column(DateTime(timezone=True), nullable=True, default=now)

    last_try = Column(DateTime(timezone=True), nullable=True)

    is_processed = Column(Boolean, nullable=False, default=False)
    is_errored = Column(Boolean, nullable=False, default=False)
    error = Column(String, nullable=True)


class OutgoingActivity(Base):
    __tablename__ = "outgoing_activity"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

    recipient = Column(String, nullable=False)

    outbox_object_id = Column(Integer, ForeignKey("outbox.id"), nullable=True)
    outbox_object = relationship(OutboxObject, uselist=False)

    # Can also reference an inbox object if it needds to be forwarded
    inbox_object_id = Column(Integer, ForeignKey("inbox.id"), nullable=True)
    inbox_object = relationship(InboxObject, uselist=False)

    # The source will be the outbox object URL
    webmention_target = Column(String, nullable=True)

    tries = Column(Integer, nullable=False, default=0)
    next_try = Column(DateTime(timezone=True), nullable=True, default=now)

    last_try = Column(DateTime(timezone=True), nullable=True)
    last_status_code = Column(Integer, nullable=True)
    last_response = Column(String, nullable=True)

    is_sent = Column(Boolean, nullable=False, default=False)
    is_errored = Column(Boolean, nullable=False, default=False)
    error = Column(String, nullable=True)

    @property
    def anybox_object(self) -> OutboxObject | InboxObject:
        if self.outbox_object_id:
            return self.outbox_object  # type: ignore
        elif self.inbox_object_id:
            return self.inbox_object  # type: ignore
        else:
            raise ValueError("Should never happen")


class TaggedOutboxObject(Base):
    __tablename__ = "tagged_outbox_object"
    __table_args__ = (
        UniqueConstraint("outbox_object_id", "tag", name="uix_tagged_object"),
    )

    id = Column(Integer, primary_key=True, index=True)

    outbox_object_id = Column(Integer, ForeignKey("outbox.id"), nullable=False)
    outbox_object = relationship(OutboxObject, uselist=False)

    tag = Column(String, nullable=False, index=True)


class Upload(Base):
    __tablename__ = "upload"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

    content_type: Mapped[str] = Column(String, nullable=False)
    content_hash = Column(String, nullable=False, unique=True)

    has_thumbnail = Column(Boolean, nullable=False)

    # Only set for images
    blurhash = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith("image")


class OutboxObjectAttachment(Base):
    __tablename__ = "outbox_object_attachment"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    filename = Column(String, nullable=False)
    alt = Column(String, nullable=True)

    outbox_object_id = Column(Integer, ForeignKey("outbox.id"), nullable=False)

    upload_id = Column(Integer, ForeignKey("upload.id"), nullable=False)
    upload: Mapped["Upload"] = relationship(Upload, uselist=False)


class PollAnswer(Base):
    __tablename__ = "poll_answer"
    __table_args__ = (
        # Enforce a single answer for poll/actor/answer
        UniqueConstraint(
            "outbox_object_id",
            "name",
            "actor_id",
            name="uix_outbox_object_id_name_actor_id",
        ),
        # Enforce an actor can only vote once on a "oneOf" Question
        Index(
            "uix_one_of_outbox_object_id_actor_id",
            "outbox_object_id",
            "actor_id",
            unique=True,
            sqlite_where=text('poll_type = "oneOf"'),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

    outbox_object_id = Column(Integer, ForeignKey("outbox.id"), nullable=False)
    outbox_object = relationship(OutboxObject, uselist=False)

    # oneOf|anyOf
    poll_type = Column(String, nullable=False)

    inbox_object_id = Column(Integer, ForeignKey("inbox.id"), nullable=False)
    inbox_object = relationship(InboxObject, uselist=False)

    actor_id = Column(Integer, ForeignKey("actor.id"), nullable=False)
    actor = relationship(Actor, uselist=False)

    name = Column(String, nullable=False)
