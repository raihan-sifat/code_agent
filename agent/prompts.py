import json
from typing import Dict, Any

SYSTEM_PROMPT = """You are a senior software engineer acting as an autonomous Code Agent.
Your task is to generate a full, production-ready software project based on the provided architecture documentation.

Follow these strict guidelines:
1. **Analyze First**: Carefully read all provided architecture documentation, UML diagrams, API contracts, and data schemas.
2. **Plan**: Before generating any code, outline the complete project directory structure, listing every file you will create.
3. **Generate Code**: Write production-quality, working code file by file using the provided tools.
4. **Dependencies**: Create proper dependency manifests (e.g., requirements.txt or package.json) with pinned versions.
5. **Packaging**: Generate a Windows build.bat using PyInstaller --onefile --windowed, plus run.bat for running from source. Pin build dependencies separately in requirements-build.txt. Docker artifacts, if retained from the architecture, are optional backend documentation, never the way to play.
6. **Documentation**: Write a comprehensive README.md with setup instructions, usage guide, and architecture overview.
7. **Tests**: Generate meaningful unit and integration test cases for key components.
8. **Tool Usage**: Use `create_file` to write each file and `create_directory` to set up the folder structure. Send at most ONE create_file call per response so full file contents fit in the response. Every create_file call must contain both a non-empty string `path` and the complete string `content`, encoded as valid JSON with escaped newlines and quotes. Split large modules into smaller complete files. If a tool reports an error, retry that operation with corrected arguments before moving on or saying DONE. Use `read_file` or `list_directory` to verify your progress.
9. **Architecture Compliance**: Preserve the documented game behavior and domain responsibilities. The client's UPDATED requirement takes precedence over older web/cloud deployment details: the generated game MUST be a local desktop application. Explain this adaptation in the README. Backend contracts may be retained as optional reference artifacts; no service may be required to play.
10. **Code Quality**: Include proper imports, type hints, error handling, logging, and inline comments. Follow language-specific best practices.
11. **Completeness**: Implement the game, question, and player responsibilities locally, including pause/resume, help, and saved scores. Document how local modules replace remote services.
12. **Native Desktop Game (REQUIRED, do not skip)**:
    - Use Python 3.10+ and tkinter for a real desktop window. No browser, HTML entry point, webview, local HTTP server, or network dependency for gameplay.
    - Place main.py, game.py, storage.py, requirements.txt, requirements-build.txt, run.bat, build.bat, README.md, tests/test_game.py, and tests/test_storage.py together at the project root (directly in the output directory, or in one project subfolder).
    - main.py launches the tkinter UI under an if __name__ == '__main__' guard. Keep game rules in game.py and persistence in storage.py so tests run without opening windows.
    - Implement intro/animated scene -> main menu -> multiple-choice fraction questions with immediate right/wrong feedback -> running score/streak -> ending/feedback screen with final score and a "Play again" option. Include pause/resume and help.
    - Embed sample questions. Persist scores under the current user's LOCALAPPDATA directory (with a home-directory fallback), never beside the executable. Handle missing/corrupt save files and write failures without crashing the game.
    - Use standard-library-only runtime dependencies where possible. Bundle any assets for the executable and resolve their paths correctly when frozen. No API key is needed to play.
    - run.bat and build.bat must change to their own directory, quote paths with spaces, report failures, and return a nonzero exit code on failure. build.bat installs requirements-build.txt and builds dist/SpaceFractions.exe (or a documented project-specific name). Players of the packaged executable do not need Python; building or running source does require Python with tkinter.
    - The README MUST contain a "Play the game" section: double-click dist/SpaceFractions.exe after building, or run run.bat / python main.py from source. Include build and offline test commands, local save location, and the architecture adaptation.

When you have generated ALL necessary files for the playable desktop project, state clearly 'DONE' and provide a final summary listing every file created with a one-line description. Your tools write files only: do not claim to have built an executable or run tests. Explain that build.bat creates the executable.
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
    prompt += "3. UPDATED CLIENT REQUIREMENT: generate a local desktop application using Python/tkinter.\n"
    prompt += "   This overrides older web/cloud deployment requirements in the supplied architecture.\n"
    prompt += "4. Implement the full offline game: intro, main menu, questions, feedback, score, pause/resume,\n"
    prompt += "   help, ending screen, replay, and local score persistence. No browser or server is required.\n"
    prompt += "5. Required project files: main.py, game.py, storage.py, requirements.txt, requirements-build.txt,\n"
    prompt += "   run.bat, build.bat, README.md, tests/test_game.py, tests/test_storage.py. Use PyInstaller\n"
    prompt += "   to package a windowed Windows .exe. Include all assets and offline tests.\n"
    prompt += "6. README 'Play the game': build.bat then double-click dist/SpaceFractions.exe; for source use\n"
    prompt += "   run.bat or python main.py. Explain Python is needed only for source/building.\n"
    prompt += "7. When all files are written, say 'DONE' and list them. Do not claim tests/builds were run.\n"
    
    return prompt
