"""Tests for build_generation_prompt."""

import pytest

from agent.prompts import SYSTEM_PROMPT, build_generation_prompt


FULL_DATA = {
    "project_name": "SpaceFractions",
    "documentation": {
        "sections": {
            "A. Executive Summary": {
                "level": 1,
                "content": "Microservices architecture for a fractions game.",
                "code_blocks": [{"language": "yml", "content": "openapi: 3.0.0"}],
                "tables": [[{"Risk": "Scalability", "Mitigation": "Load balancing"}]],
            },
            "D. Detailed Technical Design": {
                "level": 2,
                "content": "GameComponent owns game state.",
                "code_blocks": [],
                "tables": [],
            },
        }
    },
    "views": {
        "views": {
            "ScenarioView": {
                "diagrams": [{
                    "name": "UseCaseDiagram",
                    "type": "UseCase",
                    "participants": ["EndUser", "Admin"],
                    "relationships": [{"from": "EndUser", "to": "PlayGame"}],
                    "raw_content": "actor EndUser\nusecase \"Play Game\"",
                }]
            }
        }
    },
}


class TestBuildGenerationPrompt:
    def test_project_name_included(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "SpaceFractions" in prompt

    def test_default_project_name(self):
        prompt = build_generation_prompt({})
        assert "SpaceFractions" in prompt

    def test_section_titles_and_content(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "A. Executive Summary" in prompt
        assert "Microservices architecture" in prompt
        assert "GameComponent owns game state." in prompt

    def test_code_blocks_included(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "```yml\nopenapi: 3.0.0\n```" in prompt

    def test_tables_included(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "Scalability" in prompt and "Load balancing" in prompt

    def test_diagram_raw_content_and_metadata(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "UseCaseDiagram" in prompt
        assert "UseCase" in prompt
        assert "EndUser" in prompt
        assert "actor EndUser" in prompt

    def test_empty_data_does_not_crash(self):
        prompt = build_generation_prompt({})
        assert "No textual documentation provided" in prompt
        assert "No architecture views provided" in prompt

    def test_instructions_present(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "DONE" in prompt
        assert "create_file" in prompt or "outline" in prompt.lower()

    def test_generation_prompt_requires_playable_frontend(self):
        prompt = build_generation_prompt(FULL_DATA)
        assert "frontend/index.html" in prompt
        assert "Play the game" in prompt
        assert "offline" in prompt.lower()

    def test_system_prompt_requires_playable_frontend(self):
        assert "frontend/" in SYSTEM_PROMPT
        assert "index.html" in SYSTEM_PROMPT
        assert "Play the game" in SYSTEM_PROMPT
        # The full game flow must be spelled out.
        assert "main menu" in SYSTEM_PROMPT.lower()
        assert "ending" in SYSTEM_PROMPT.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
