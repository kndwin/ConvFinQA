from src.module.chat_session_tags.chat_session_tags_repository_schema import (
    ChatSessionTagRepositoryCreateParams,
    ChatSessionTagRepositoryGetParams,
    ChatSessionTagRepositoryListParams,
    ChatSessionTagRepositoryUpdateParams,
)


class ChatSessionTagServiceGetParams(ChatSessionTagRepositoryGetParams):
    pass


class ChatSessionTagServiceListParams(ChatSessionTagRepositoryListParams):
    pass


class ChatSessionTagServiceCreateParams(ChatSessionTagRepositoryCreateParams):
    pass


class ChatSessionTagServiceUpdateParams(ChatSessionTagRepositoryUpdateParams):
    pass
