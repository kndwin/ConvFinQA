from pydantic import BaseModel, ConfigDict

from src.platform.database.models import ChatSessionTable, DatasetConversationTable


class OpenAIChatAgentPreparedRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    chat_session: ChatSessionTable
    dataset: DatasetConversationTable
    question: str
