"""Tests for the ArchitecturePreprocessor."""

import os
import pytest
import tempfile
from parser.preprocessor import ArchitecturePreprocessor


SAMPLE_DOC = """# A. Executive Summary
The Space Fractions system is a web-based educational game.

Chosen architectural style: Microservices

| Risk | Mitigation |
| --- | --- |
| Scalability | Load balancing |
| Security | Encryption |

## GameComponent
### Technology options
```yml
openapi: 3.0.0
info:
  title: Space Fractions API
  version: 1.0.0
```

```sql
CREATE TABLE games (
  id SERIAL PRIMARY KEY,
  game_state JSONB NOT NULL
);
```
"""

SAMPLE_VIEWS = """## ScenarioView
1. UseCase Diagram
```plantuml
@startuml UseCaseDiagram
left to right direction
actor EndUser as "End User"
rectangle System {
  usecase "Play Game" as (PlayGame)
}
EndUser -- (PlayGame)
@enduml
```

## LogicView
2. Class Diagram
```plantuml
@startuml ClassDiagram
class Game {
  - id: string
  - score: int
  + play(): void
}
class Question {
  - id: string
  - prompt: string
}
Game --* Question
@enduml
```
"""


class TestArchitecturePreprocessor:
    """Tests for ArchitecturePreprocessor."""
    
    def setup_method(self):
        self.preprocessor = ArchitecturePreprocessor()
        self.tmpdir = tempfile.mkdtemp()
        
        # Write sample files
        self.doc_path = os.path.join(self.tmpdir, "Architecture_Documentation.md")
        with open(self.doc_path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_DOC)
            
        self.views_path = os.path.join(self.tmpdir, "Architecture_View.md")
        with open(self.views_path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_VIEWS)
    
    def test_parse_documentation_sections(self):
        """Test that documentation sections are extracted."""
        result = self.preprocessor.parse_documentation(self.doc_path)
        assert "sections" in result
        sections = result["sections"]
        assert len(sections) > 0
        
    def test_parse_documentation_code_blocks(self):
        """Test that code blocks are extracted from documentation."""
        result = self.preprocessor.parse_documentation(self.doc_path)
        sections = result["sections"]
        # Find section with code blocks
        has_code_blocks = any(
            len(s.get("code_blocks", [])) > 0 
            for s in sections.values()
        )
        assert has_code_blocks, "Should find at least one code block"
        
    def test_parse_documentation_tables(self):
        """Test that tables are extracted from documentation."""
        result = self.preprocessor.parse_documentation(self.doc_path)
        sections = result["sections"]
        has_tables = any(
            len(s.get("tables", [])) > 0 
            for s in sections.values()
        )
        assert has_tables, "Should find at least one table"

    def test_parse_views_extracts_diagrams(self):
        """Test that PlantUML diagrams are extracted from views."""
        result = self.preprocessor.parse_views(self.views_path)
        assert "views" in result
        views = result["views"]
        assert len(views) > 0
        
        # Check at least one view has diagrams
        has_diagrams = any(
            len(v.get("diagrams", [])) > 0 
            for v in views.values()
        )
        assert has_diagrams, "Should find at least one diagram"
        
    def test_parse_views_diagram_type_detection(self):
        """Test that diagram types are correctly detected."""
        result = self.preprocessor.parse_views(self.views_path)
        views = result["views"]
        
        all_diagrams = []
        for v in views.values():
            all_diagrams.extend(v.get("diagrams", []))
        
        types = [d["type"] for d in all_diagrams]
        assert "UseCase" in types or "Class" in types, f"Should detect diagram types, got: {types}"
        
    def test_parse_views_participants(self):
        """Test that participants are extracted from diagrams."""
        result = self.preprocessor.parse_views(self.views_path)
        views = result["views"]
        
        all_diagrams = []
        for v in views.values():
            all_diagrams.extend(v.get("diagrams", []))
        
        has_participants = any(len(d.get("participants", [])) > 0 for d in all_diagrams)
        assert has_participants, "Should extract participants from diagrams"

    def test_preprocess_combines_both(self):
        """Test that preprocess combines documentation and views."""
        result = self.preprocessor.preprocess(self.doc_path, self.views_path)
        assert "documentation" in result
        assert "views" in result
        
    def test_parse_nonexistent_file(self):
        """Test graceful handling of nonexistent files."""
        result = self.preprocessor.parse_documentation("/nonexistent/file.md")
        assert result == {}

    def test_parse_views_nonexistent_file(self):
        """Test graceful handling of nonexistent view files."""
        result = self.preprocessor.parse_views("/nonexistent/file.md")
        assert result == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
