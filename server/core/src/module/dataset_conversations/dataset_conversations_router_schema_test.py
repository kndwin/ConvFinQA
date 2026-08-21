import asyncio
import json
import unittest
from typing import Any, cast

from fastapi import HTTPException
from pydantic import ValidationError

from src.main import create_app
from src.module.dataset_conversations.dataset_conversations_repository_schema import (
    DatasetConversationRepositoryListParams,
)
from src.module.dataset_conversations.dataset_conversations_router import router
from src.module.dataset_conversations.dataset_conversations_router_schema import (
    DatasetConversationResponse,
    candidate_qa_from_dialogue_json,
)
from src.platform.database.models import DatasetConversationTable


class CandidateQuestionAnswerTests(unittest.TestCase):
    def test_maps_pairs_by_question_index_and_trims_text(self):
        result = candidate_qa_from_dialogue_json(
            '{"conv_questions": [" Q1 ","Q2", " ", 4], "conv_answers": [" A1 ", " A2 ", "extra"]}'
        )
        self.assertEqual(
            [(item.question, item.answer) for item in result], [("Q1", "A1"), ("Q2", "A2")]
        )

    def test_missing_and_non_string_answers_are_unavailable(self):
        result = candidate_qa_from_dialogue_json(
            '{"conv_questions": ["Q1", "Q2", "Q3"], "conv_answers": [4, "  "]}'
        )
        self.assertEqual(
            [(item.question, item.answer) for item in result],
            [("Q1", None), ("Q2", None), ("Q3", None)],
        )

    def test_missing_answers_array_keeps_questions(self):
        result = candidate_qa_from_dialogue_json('{"conv_questions": ["Q1"]}')
        self.assertEqual([(item.question, item.answer) for item in result], [("Q1", None)])

    def test_invalid_or_wrong_shape_is_empty(self):
        for payload in ("not json", "[]", "null", "{}", '{"conv_questions": "Q"}'):
            with self.subTest(payload=payload):
                self.assertEqual(candidate_qa_from_dialogue_json(payload), [])

    def test_response_validates_table_and_serializes_candidate_qa(self):
        table = DatasetConversationTable(
            id=7,
            source_id="source-7",
            split="test",
            dialogue_json='{"conv_questions": [" Q1 "], "conv_answers": [" A1 "]}',
        )
        response = DatasetConversationResponse.model_validate(table)
        self.assertEqual(response.candidate_qa[0].model_dump(), {"question": "Q1", "answer": "A1"})
        self.assertEqual(
            response.model_dump()["candidate_qa"], [{"question": "Q1", "answer": "A1"}]
        )

    def test_response_schema_requires_candidate_qa(self):
        schema = DatasetConversationResponse.model_json_schema(mode="serialization")
        self.assertIn("candidate_qa", schema["required"])
        self.assertIn("candidate_qa", schema["properties"])


class DatasetConversationTagFilterTests(unittest.TestCase):
    def test_route_propagates_tags_and_returns_json_safe_422(self):
        endpoint = next(
            cast(Any, route).endpoint.__dishka_orig_func__
            for route in router.routes
            if (
                cast(Any, route).path == "/dataset-conversations"
                and "GET" in cast(Any, route).methods
            )
        )

        class Service:
            def __init__(self) -> None:
                self.params: Any = None

            async def list(self, params: Any) -> list[Any]:
                self.params = params
                return []

        service = Service()
        self.assertEqual(asyncio.run(endpoint(service, 0, 20, [" alpha ", "beta"])), [])
        self.assertEqual(service.params.tags, ["alpha", "beta"])
        for tags in (["alpha", "alpha"], [" "]):
            with self.subTest(tags=tags), self.assertRaises(HTTPException) as context:
                asyncio.run(endpoint(service, 0, 20, tags))
            self.assertEqual(context.exception.status_code, 422)
            json.dumps(context.exception.detail)

    def test_openapi_exposes_tag_query_parameter(self):
        parameters = create_app().openapi()["paths"]["/dataset-conversations"]["get"]["parameters"]
        tag_parameter = next(parameter for parameter in parameters if parameter["name"] == "tags")
        schema = tag_parameter["schema"]["anyOf"][0]
        self.assertEqual(schema["maxItems"], 50)
        self.assertEqual(schema["items"]["maxLength"], 100)

    def test_tags_are_trimmed_and_duplicates_rejected(self):
        self.assertEqual(
            DatasetConversationRepositoryListParams(tags=[" alpha ", "beta"]).tags,
            ["alpha", "beta"],
        )
        for tags in (["alpha", "alpha"], ["  "], ["x" * 101], [str(i) for i in range(51)]):
            with self.subTest(tags=tags), self.assertRaises(ValidationError):
                DatasetConversationRepositoryListParams(tags=tags)
