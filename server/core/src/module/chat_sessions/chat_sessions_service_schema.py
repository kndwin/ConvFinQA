from src.module.chat_sessions.chat_sessions_repository_schema import (
    ChatSessionRepositoryCreateParams,
    ChatSessionRepositoryDeleteParams,
    ChatSessionRepositoryGetParams,
    ChatSessionRepositoryListParams,
    ChatSessionRepositoryUpdateParams,
)


class ChatSessionServiceListParams(ChatSessionRepositoryListParams):
    """Parameters for listing chat sessions through the service."""


class ChatSessionServiceGetParams(ChatSessionRepositoryGetParams):
    """Parameters for retrieving a chat session through the service."""


class ChatSessionServiceCreateParams(ChatSessionRepositoryCreateParams):
    """Parameters for creating a chat session through the service."""


class ChatSessionServiceUpdateParams(ChatSessionRepositoryUpdateParams):
    """Parameters for updating a chat session through the service."""


class ChatSessionServiceDeleteParams(ChatSessionRepositoryDeleteParams):
    """Parameters for deleting a chat session through the service."""
