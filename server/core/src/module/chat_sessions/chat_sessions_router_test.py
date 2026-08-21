import unittest

from pydantic import ValidationError

from src.module.agent_execution.agent_execution_constants import AgentApproach, OpenAIModel
from src.module.chat_sessions.chat_sessions_router_schema import (
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from src.platform.database.models import (
    ChatSessionTable,
)


class ChatSessionApproachSchemaTests(unittest.TestCase):
    def test_update_distinguishes_omitted_and_explicit_patch_values(self) -> None:
        omitted = ChatSessionUpdateRequest()
        self.assertNotIn("title", omitted.model_fields_set)
        self.assertNotIn("tags", omitted.model_fields_set)
        self.assertIn("title", ChatSessionUpdateRequest(title=None).model_fields_set)
        self.assertIn("tags", ChatSessionUpdateRequest(tags=[]).model_fields_set)

    def test_update_reuses_tag_validation_for_replacement(self) -> None:
        request = ChatSessionUpdateRequest(tags=[{"value": "  important "}])
        self.assertEqual(request.tags[0].value, "important")
        with self.assertRaises(ValidationError):
            ChatSessionUpdateRequest(tags=[{"value": "same"}, {"value": "same"}])

    def test_create_request_defaults_to_direct_mini(self) -> None:
        self.assertEqual(ChatSessionCreateRequest().agent_approach, AgentApproach.BASELINE)
        self.assertEqual(ChatSessionCreateRequest().model, OpenAIModel.GPT_5_6_LUNA)

    def test_create_request_accepts_all_exact_models(self) -> None:
        for model in (
            "gpt-5.6-luna",
            "gpt-5.6-terra",
            "gpt-5.6-sol",
            "gpt-5-mini",
        ):
            with self.subTest(model=model):
                self.assertEqual(ChatSessionCreateRequest(model=model).model.value, model)

    def test_create_request_rejects_unknown_model(self) -> None:
        with self.assertRaises(ValidationError):
            ChatSessionCreateRequest(model="gpt-5.6-unknown")

    def test_create_request_accepts_explicit_direct_mini(self) -> None:
        self.assertEqual(
            ChatSessionCreateRequest(agent_approach="baseline").agent_approach,
            AgentApproach.BASELINE,
        )

    def test_create_request_rejects_unknown_approach(self) -> None:
        with self.assertRaises(ValidationError):
            ChatSessionCreateRequest(agent_approach="unknown")

    def test_openapi_describes_models_and_rejects_unknown_http_values(self) -> None:
        from fastapi.testclient import TestClient

        from src.main import create_app

        app = create_app()
        schema = app.openapi()
        request_schema = schema["components"]["schemas"]["ChatSessionCreateRequest"]
        self.assertFalse(request_schema.get("required"))
        self.assertEqual(
            request_schema["properties"]["agent_approach"]["$ref"],
            "#/components/schemas/AgentApproach",
        )
        self.assertEqual(
            schema["components"]["schemas"]["AgentApproach"]["enum"],
            ["baseline", "baseline-tool", "program-of-thought"],
        )
        self.assertEqual(
            request_schema["properties"]["model"]["$ref"],
            "#/components/schemas/OpenAIModel",
        )
        self.assertEqual(request_schema["properties"]["model"]["default"], "gpt-5.6-luna")
        self.assertNotIn("tags", request_schema.get("required", []))
        self.assertNotIn("required", request_schema)
        self.assertEqual(
            request_schema["properties"]["tags"]["items"]["$ref"],
            "#/components/schemas/ChatSessionTagInput",
        )
        response_schema = schema["components"]["schemas"]["ChatSessionResponse"]
        self.assertEqual(
            response_schema["properties"]["tags"]["items"]["$ref"],
            "#/components/schemas/ChatSessionTagResponse",
        )
        self.assertEqual(
            schema["components"]["schemas"]["OpenAIModel"]["enum"],
            ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5-mini"],
        )
        response = TestClient(app).post(
            "/dataset-conversations/1/chat-sessions", json={"agent_approach": "unknown"}
        )
        self.assertEqual(response.status_code, 422)
        response = TestClient(app).post(
            "/dataset-conversations/1/chat-sessions", json={"model": "not-a-model"}
        )
        self.assertEqual(response.status_code, 422)

    def test_create_request_accepts_calculator_mini(self) -> None:
        self.assertEqual(
            ChatSessionCreateRequest(agent_approach="baseline-tool").agent_approach,
            AgentApproach.BASELINE_TOOL,
        )

    def test_response_exposes_persisted_approach(self) -> None:
        from datetime import UTC, datetime

        response = ChatSessionResponse.model_validate(
            ChatSessionTable(
                id=8,
                dataset_conversation_id=3,
                agent_approach="baseline",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        self.assertEqual(response.agent_approach, AgentApproach.BASELINE)

    def test_response_exposes_persisted_non_default_model(self) -> None:
        from datetime import UTC, datetime

        response = ChatSessionResponse.model_validate(
            ChatSessionTable(
                id=8,
                dataset_conversation_id=3,
                agent_approach="baseline",
                model="gpt-5.6-sol",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        self.assertEqual(response.model, OpenAIModel.GPT_5_6_SOL)
