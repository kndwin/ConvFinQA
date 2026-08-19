import asyncio
from typing import Any, cast
from unittest import IsolatedAsyncioTestCase, TestCase

from src.module.agent_execution.agent_approach.ensemble.definition import (
    CandidateResult,
    EnsembleCandidate,
    EnsembleConfig,
    InMemoryEnsembleExecutor,
)
from src.module.agent_execution.agent_execution_constants import AgentApproach
from src.module.agent_execution.execution.durable.ensemble_workflow import EnsembleWorkflow
from src.module.agent_execution.execution.durable.ensemble_workflow_schema import (
    EnsembleCandidateOutput,
    EnsembleWorkflowOutput,
)
from src.module.chat_sessions.chat_session_run_adapter import ChatSessionRunAdapter


class EnsembleDomainTests(TestCase):
    def test_config_requires_unique_direct_candidates(self) -> None:
        candidate = EnsembleCandidate(
            approach=AgentApproach.BASELINE,
            prompt_version="baseline:v1",
            context_version="document-conversation:v1",
        )
        with self.assertRaises(ValueError):
            EnsembleConfig.validate_candidates([candidate, candidate])

    def test_in_memory_executor_keeps_order_and_invokes_reviewer(self) -> None:
        config = EnsembleConfig.validate_candidates(
            EnsembleCandidate(
                approach=approach,
                prompt_version=f"{approach}:v1",
                context_version="document-conversation:v1",
            )
            for approach in (AgentApproach.BASELINE, AgentApproach.BASELINE_TOOL)
        )
        reviewer_inputs: list[str] = []

        async def candidate(item: EnsembleCandidate):
            await asyncio.sleep(0)
            return CandidateResult(
                approach=item.approach,
                final_output=f"answer from {item.approach}",
                duration_ms=1,
            )

        async def reviewer(value: str) -> str:
            reviewer_inputs.append(value)
            return "reviewed answer"

        result = asyncio.run(
            InMemoryEnsembleExecutor(candidate, reviewer).run(
                config, context="document", question="question"
            )
        )
        self.assertEqual(result.reviewer_output, "reviewed answer")
        self.assertEqual(
            [item.approach for item in result.candidates],
            [AgentApproach.BASELINE, AgentApproach.BASELINE_TOOL],
        )
        self.assertIn("answer from baseline-tool", reviewer_inputs[0])

    def test_cursor_round_trip_rejects_unknown_sources(self) -> None:
        offsets = {"candidate:baseline": 4, "reviewer": 9}
        encoded = ChatSessionRunAdapter.encode_cursor(offsets)
        self.assertEqual(ChatSessionRunAdapter.decode_cursor(encoded, set(offsets)), offsets)
        self.assertEqual(ChatSessionRunAdapter.decode_cursor(encoded, {"reviewer"}), {})


class ChatSessionRunAdapterTests(IsolatedAsyncioTestCase):
    async def test_stream_events_uses_typed_parent_handle_and_finishes(self) -> None:
        class EmptyStream:
            async def subscribe(self, **kwargs):
                if False:
                    yield kwargs

        class Handle:
            def __init__(self, result):
                self.result_value = result

            async def result(self):
                return self.result_value

        output = EnsembleWorkflowOutput(
            reviewer_output="reviewed answer",
            candidates=(
                EnsembleCandidateOutput(
                    approach="baseline", status="completed", final_output="candidate answer"
                ),
            ),
        )

        class Client:
            def __init__(self):
                self.typed_calls = []

            def get_workflow_handle(self, workflow_id):
                return Handle({"reviewer_output": "wrong shape"})

            def get_workflow_handle_for(self, workflow, workflow_id):
                self.typed_calls.append((workflow, workflow_id))
                return Handle(output)

        client = Client()

        class Backend:
            async def preflight(self):
                return None

            async def typed_handle(self, workflow, workflow_id):
                return client.get_workflow_handle_for(workflow, workflow_id)

            async def subscribe(self, workflow_id, topic, from_offset):
                async for item in EmptyStream().subscribe(topic=topic, from_offset=from_offset):
                    yield item

        service = ChatSessionRunAdapter(
            cast(Any, None), cast(Any, None), cast(Any, None), cast(Any, Backend())
        )
        events = [
            event
            async for event in service.stream_events(
                "ensemble:1:run", "thread", "run", ("baseline",)
            )
        ]

        self.assertEqual(client.typed_calls, [(EnsembleWorkflow.run, "ensemble:1:run")])
        self.assertTrue(any(event.__class__.__name__ == "RunFinishedEvent" for event in events))
        self.assertTrue(
            any(getattr(event, "name", None) == "ensemble.candidate.completed" for event in events)
        )
