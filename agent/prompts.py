import json
from typing import Dict, Any

SYSTEM_PROMPT = """You are a senior software engineer acting as an autonomous Code Agent.
Your task is to generate a full, production-ready software project based on the provided architecture documentation.

Follow these strict guidelines:
1. **Analyze First**: Carefully read all provided architecture documentation, UML diagrams, API contracts, and data schemas.
2. **Plan**: Before generating any code, outline the complete project directory structure, listing every file you will create.
3. **Generate Code**: Write production-quality, working code file by file using the provided tools.
4. **Dependencies**: Create proper dependency manifests (e.g., requirements.txt or package.json) with pinned versions.
5. **Docker**: Write a Dockerfile and docker-compose.yml to make the project easily deployable.
6. **Documentation**: Write a comprehensive README.md with setup instructions, usage guide, and architecture overview.
7. **Tests**: Generate meaningful unit and integration test cases for key components.
8. **Tool Usage**: Use `create_file` to write each file and `create_directory` to set up the folder structure. Use `read_file` or `list_directory` to verify your progress.
9. **Architecture Compliance**: Strictly follow the architecture patterns, class structures, API contracts, data models, and deployment topology described in the documentation.
10. **Code Quality**: Include proper imports, type hints, error handling, logging, and inline comments. Follow language-specific best practices.
11. **Completeness**: Ensure ALL classes, APIs, data models, and interactions shown in the UML diagrams are implemented.
12. **Playable Frontend (REQUIRED, do not skip)**: The documentation describes a *web-based, interactive* product (for SpaceFractions: an introductory movie/scene, a main menu, a series of fraction questions, and an ending scene with feedback and score). Besides the backend, you MUST generate a self-contained, browser-playable frontend under a `frontend/` directory:
    - `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (plain HTML/CSS/JS - no build step, no npm install, no framework CDN required).
    - It MUST implement the complete user experience end-to-end: intro/animated scene -> main menu -> a sequence of multiple-choice fraction questions with immediate right/wrong feedback -> running score -> ending/feedback screen with a final score and a "Play again" option.
    - It MUST be fully playable by simply opening `frontend/index.html` in a browser, with NO backend, NO server, and NO network access: embed a set of sample fraction questions and a working offline "demo mode".
    - If a backend is reachable it may optionally use it, but the offline demo mode is mandatory and must be the default so the game always works.
    - The README MUST contain a clearly-marked "Play the game" section stating: open `frontend/index.html` in a web browser (no installation required).

When you have generated ALL necessary files for the complete project (backend AND the playable frontend), state clearly 'DONE' and provide a final summary listing every file created with a one-line description.
"""

def build_generation_prompt(architecture_data: Dict[str, Any]) -> str:
    """Build the initial user message with architecture context.
    
    Handles the nested output from ArchitecturePreprocessor.preprocess():
    {
        'documentation': {'sections': {section_name: {level, content, code_blocks, tables}, ...}},
        'views': {'views': {view_name: {diagrams: [{name, type, participants, relationships, raw_content}, ...]}, ...}}
    }
    """
    project_name = architecture_data.get('project_name', 'SpaceFractions')
    
    prompt = f"Please generate the complete software project for '{project_name}'.\n\n"
    prompt += "=" * 60 + "\n"
    prompt += "ARCHITECTURE DOCUMENTATION\n"
    prompt += "=" * 60 + "\n\n"
    
    # Extract documentation sections
    doc_data = architecture_data.get('documentation', {})
    sections = doc_data.get('sections', doc_data) if isinstance(doc_data, dict) else {}
    
    if sections:
        for section_title, section_info in sections.items():
            prompt += f"## {section_title}\n"
            
            if isinstance(section_info, dict):
                # Include text content
                content = section_info.get('content', '')
                if content:
                    prompt += f"{content}\n"
                
                # Include tables
                tables = section_info.get('tables', [])
                for table in tables:
                    if table:
                        prompt += "\n**Table:**\n"
                        prompt += json.dumps(table, indent=2) + "\n"
                
                # Include code blocks
                code_blocks = section_info.get('code_blocks', [])
                for block in code_blocks:
                    lang = block.get('language', '')
                    code = block.get('content', '')
                    prompt += f"\n```{lang}\n{code}\n```\n"
            else:
                prompt += f"{section_info}\n"
            
            prompt += "\n"
    else:
        prompt += "(No textual documentation provided)\n\n"
        
    prompt += "=" * 60 + "\n"
    prompt += "ARCHITECTURE VIEWS (UML DIAGRAMS)\n"
    prompt += "=" * 60 + "\n\n"
    
    # Extract views/diagrams
    views_data = architecture_data.get('views', {})
    views = views_data.get('views', views_data) if isinstance(views_data, dict) else {}
    
    if views:
        for view_title, view_info in views.items():
            prompt += f"### {view_title}\n"
            
            if isinstance(view_info, dict):
                diagrams = view_info.get('diagrams', [])
                for diagram in diagrams:
                    name = diagram.get('name', 'Diagram')
                    diag_type = diagram.get('type', 'Unknown')
                    raw = diagram.get('raw_content', '')
                    participants = diagram.get('participants', [])
                    relationships = diagram.get('relationships', [])
                    
                    prompt += f"\n**{name}** (Type: {diag_type})\n"
                    if participants:
                        prompt += f"Participants: {', '.join(participants)}\n"
                    if relationships:
                        rels = [f"{r['from']} -> {r['to']}" for r in relationships]
                        prompt += f"Relationships: {', '.join(rels)}\n"
                    prompt += f"```plantuml\n{raw}\n```\n"
            else:
                prompt += f"```plantuml\n{view_info}\n```\n"
            
            prompt += "\n"
    else:
        prompt += "(No architecture views provided)\n\n"
        
    prompt += "=" * 60 + "\n"
    prompt += "INSTRUCTIONS\n"
    prompt += "=" * 60 + "\n\n"
    prompt += "1. First, outline your plan: list the directory structure and every file you will create.\n"
    prompt += "2. Then, execute the plan by creating each directory and file using the provided tools.\n"
    prompt += "3. Ensure the generated project is complete, runnable, and follows the architecture exactly.\n"
    prompt += "4. MANDATORY: also create a self-contained, browser-playable frontend under `frontend/`\n"
    prompt += "   (`index.html`, `styles.css`, `app.js`) implementing the full game flow - intro scene,\n"
    prompt += "   main menu, multiple-choice fraction questions with feedback, running score, and an\n"
    prompt += "   ending/feedback screen. It must work offline by opening `frontend/index.html` directly\n"
    prompt += "   in a browser (embed sample questions; no server, build, or network needed). This is\n"
    prompt += "   required and must not be skipped, even if the architecture only lists backend artifacts.\n"
    prompt += "5. In the README, add a 'Play the game' section: open `frontend/index.html` in a browser.\n"
    prompt += "6. When finished, say 'DONE' and list all created files.\n"
    
    return prompt
