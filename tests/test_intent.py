import unittest

from nexus.intent import IntentEngine, make_objective
from nexus.kernel.events import EventBus


def parse(text, context_refs=None, bus=None):
    engine = IntentEngine(bus=bus)
    return engine.parse(make_objective(text, context_refs))


class TestGoalExtraction(unittest.TestCase):
    def test_simple_imperative_is_a_goal(self):
        intent = parse("Build a REST API from this specification")
        self.assertEqual(intent.goals, ["Build a REST API from this specification"])
        self.assertEqual(intent.constraints, [])
        self.assertEqual(intent.open_questions, [])

    def test_numbered_list_decomposes_into_goals(self):
        intent = parse("1. Research existing solutions\n2. Design the schema\n3. Implement the API")
        self.assertEqual(
            intent.goals,
            ["Research existing solutions", "Design the schema", "Implement the API"],
        )

    def test_bulleted_list_decomposes_into_goals(self):
        intent = parse("- Set up the repo\n- Write the docs")
        self.assertEqual(intent.goals, ["Set up the repo", "Write the docs"])

    def test_and_then_splits_goals(self):
        intent = parse("Set up the repo and then configure CI")
        self.assertEqual(intent.goals, ["Set up the repo", "configure CI"])

    def test_sentences_split_without_breaking_versions(self):
        intent = parse("Migrate the service to Python 3.11. Add integration tests")
        self.assertEqual(
            intent.goals,
            ["Migrate the service to Python 3.11", "Add integration tests"],
        )

    def test_duplicate_goals_deduplicated(self):
        intent = parse("Write the docs. Write the docs")
        self.assertEqual(intent.goals, ["Write the docs"])


class TestConstraintExtraction(unittest.TestCase):
    def test_must_clause_is_a_constraint(self):
        intent = parse("Build an API. Must support pagination")
        self.assertEqual(intent.goals, ["Build an API"])
        self.assertEqual(intent.constraints, ["Must support pagination"])

    def test_leading_use_is_a_constraint(self):
        intent = parse("Build a CLI. Use Python 3.11")
        self.assertEqual(intent.goals, ["Build a CLI"])
        self.assertEqual(intent.constraints, ["Use Python 3.11"])

    def test_budget_clause_is_a_constraint(self):
        intent = parse("Run the benchmark. No more than $50 in API costs")
        self.assertEqual(intent.constraints, ["No more than $50 in API costs"])

    def test_embedded_using_phrase_becomes_constraint(self):
        intent = parse("Build a REST API using FastAPI")
        self.assertEqual(intent.goals, ["Build a REST API using FastAPI"])
        self.assertEqual(intent.constraints, ["using FastAPI"])

    def test_embedded_without_phrase_becomes_constraint(self):
        intent = parse("Build a CLI without external dependencies")
        self.assertEqual(intent.constraints, ["without external dependencies"])

    def test_avoid_and_never_clauses(self):
        intent = parse("Refactor the module. Avoid breaking the public API. Never delete user data")
        self.assertEqual(
            intent.constraints,
            ["Avoid breaking the public API", "Never delete user data"],
        )


class TestOutcomeExtraction(unittest.TestCase):
    def test_deliver_clause_is_an_outcome(self):
        intent = parse("Build the pipeline. Deliver a benchmark report")
        self.assertEqual(intent.desired_outcomes, ["Deliver a benchmark report"])

    def test_so_that_splits_goal_and_outcome(self):
        intent = parse("Build an API so that clients can generate SDKs")
        self.assertEqual(intent.goals, ["Build an API"])
        self.assertEqual(intent.desired_outcomes, ["clients can generate SDKs"])


class TestOpenQuestions(unittest.TestCase):
    def test_question_is_captured_not_resolved(self):
        intent = parse("Should we use SQLite or Postgres?")
        self.assertEqual(intent.open_questions, ["Should we use SQLite or Postgres?"])
        self.assertEqual(intent.goals, [])

    def test_empty_objective_yields_open_question(self):
        intent = parse("   ")
        self.assertEqual(intent.goals, [])
        self.assertEqual(len(intent.open_questions), 1)

    def test_mixed_goal_and_question(self):
        intent = parse("Design the memory layer. Should promotion be automatic?")
        self.assertEqual(intent.goals, ["Design the memory layer"])
        self.assertEqual(intent.open_questions, ["Should promotion be automatic?"])


class TestContextRefs(unittest.TestCase):
    def test_url_and_file_path_detected_in_order(self):
        intent = parse("Summarize docs/report.md and https://example.com/spec")
        self.assertEqual(intent.context_refs, ["docs/report.md", "https://example.com/spec"])

    def test_url_trailing_punctuation_stripped(self):
        intent = parse("Read https://example.com/spec.")
        self.assertEqual(intent.context_refs, ["https://example.com/spec"])

    def test_objective_refs_come_first_and_are_deduplicated(self):
        intent = parse("Summarize docs/report.md", context_refs=["repo.git", "docs/report.md"])
        self.assertEqual(intent.context_refs, ["repo.git", "docs/report.md"])

    def test_bare_word_with_dotted_name_is_not_a_ref(self):
        intent = parse("Deploy the Node.js service")
        self.assertEqual(intent.context_refs, [])


class TestDeterminism(unittest.TestCase):
    def test_same_input_produces_identical_intent(self):
        text = "Build a REST API using FastAPI. Must support pagination. Deliver an OpenAPI spec"
        a = parse(text, context_refs=["spec.md"])
        b = parse(text, context_refs=["spec.md"])
        self.assertEqual(a, b)  # includes ids: hash-derived, not random

    def test_different_objectives_get_different_ids(self):
        a = parse("Build an API")
        b = parse("Build a CLI")
        self.assertNotEqual(a.id, b.id)
        self.assertNotEqual(a.objective_id, b.objective_id)

    def test_make_objective_id_is_content_derived(self):
        self.assertEqual(make_objective("Build an API").id, make_objective("Build an API").id)


class TestEngineBehavior(unittest.TestCase):
    def test_emits_intent_parsed_event(self):
        bus = EventBus()
        intent = parse("Build an API", bus=bus)
        events = bus.log("intent.parsed")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["intent_id"], intent.id)
        self.assertEqual(events[0].payload["objective_id"], intent.objective_id)

    def test_engine_works_without_a_bus(self):
        intent = parse("Build an API")  # no bus wired; must not raise
        self.assertEqual(intent.goals, ["Build an API"])

    def test_end_to_end_success_criteria_objective(self):
        intent = parse(
            "Build a REST API from spec.md using FastAPI. Must support pagination. "
            "Deliver an OpenAPI spec so that clients can generate SDKs"
        )
        self.assertEqual(intent.goals, ["Build a REST API from spec.md using FastAPI"])
        self.assertEqual(intent.constraints, ["using FastAPI", "Must support pagination"])
        self.assertEqual(
            intent.desired_outcomes,
            ["Deliver an OpenAPI spec", "clients can generate SDKs"],
        )
        self.assertEqual(intent.context_refs, ["spec.md"])
        self.assertEqual(intent.open_questions, [])


if __name__ == "__main__":
    unittest.main()
