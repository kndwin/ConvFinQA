"""Normalized ConvFinQA tables (SQLModel table models)."""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class DatasetConversationTable(SQLModel, table=True):
    __tablename__: ClassVar[str] = "dataset_conversation"
    id: int | None = Field(default=None, primary_key=True)
    source_id: str = Field(index=True, unique=True)
    split: str = Field(index=True)
    pre_text: str = ""
    post_text: str = ""
    num_dialogue_turns: int | None = None
    has_type2_question: bool | None = None
    has_duplicate_columns: bool | None = None
    has_non_numeric_values: bool | None = None
    features_json: str = "{}"
    doc_json: str | None = None
    dialogue_json: str = "{}"


class ChatSessionTable(SQLModel, table=True):
    __tablename__: ClassVar[str] = "chat_session"
    id: int | None = Field(default=None, primary_key=True)
    dataset_conversation_id: int = Field(foreign_key="dataset_conversation.id", index=True)
    agent_variant: str = Field(default="direct-mini", index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    title: str | None = None
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ChatMessageTable(SQLModel, table=True):
    __tablename__: ClassVar[str] = "chat_message"
    id: int | None = Field(default=None, primary_key=True)
    chat_session_id: int = Field(foreign_key="chat_session.id", index=True)
    role: str = Field(index=True)
    content: str
    client_message_id: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    __table_args__ = (UniqueConstraint("chat_session_id", "client_message_id"),)


class AgentRunTable(SQLModel, table=True):
    __tablename__: ClassVar[str] = "agent_run"
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True)
    chat_session_id: int = Field(foreign_key="chat_session.id", index=True)
    status: str = Field(default="running", index=True)
    model: str
    assistant_message_id: int | None = Field(
        default=None, foreign_key="chat_message.id", ondelete="SET NULL"
    )
    error: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class TableCellTable(SQLModel, table=True):
    __tablename__: ClassVar[str] = "table_cell"
    id: int | None = Field(default=None, primary_key=True)
    dataset_conversation_id: int = Field(foreign_key="dataset_conversation.id", index=True)
    column_heading: str
    row_label: str
    value_type: str = Field(index=True)
    text_value: str | None = None
    numeric_value: float | None = None
    raw_value: str


class DialogueTurnTable(SQLModel, table=True):
    __tablename__: ClassVar[str] = "dialogue_turn"
    id: int | None = Field(default=None, primary_key=True)
    dataset_conversation_id: int = Field(foreign_key="dataset_conversation.id", index=True)
    turn_index: int
    question: str | None = None
    answer_text: str | None = None
    program: str | None = None
    executed_answer_json: str | None = None
    qa_split: bool | None = None
