from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryGetParams,
    DatasetConversationRepositoryListParams,
)


class DatasetConversationServiceGetParams(DatasetConversationRepositoryGetParams):
    """Parameters for retrieving a dataset conversation through the service."""


class DatasetConversationServiceListParams(DatasetConversationRepositoryListParams):
    """Parameters for listing dataset conversations through the service."""
