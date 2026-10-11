import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ArchitecturePreprocessor:
    """Parses architecture markdown documentation into structured JSON."""
    
    def parse_documentation(self, filepath: str) -> Dict[str, Any]:
        """Parse Architecture_Documentation.md into structured JSON."""
        logger.info(f"Parsing documentation: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return {}
            
        # Basic markdown parser for sections
        sections = {}
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#'):
                if current_section:
                    sections[current_section]["content"] = '\n'.join(current_content)
                
                header_level = len(line) - len(line.lstrip('#'))
                header_text = line.lstrip('#').strip()
                current_section = header_text
                current_content = []
                sections[current_section] = {
                    "level": header_level,
                    "code_blocks": [],
                    "tables": []
                }
                i += 1
                continue
                
            if line.startswith('```'):
                # Extract code block
                lang = line[3:].strip()
                block_content = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    block_content.append(lines[i])
                    i += 1
                
                if current_section:
                    sections[current_section]["code_blocks"].append({
                        "language": lang,
                        "content": '\n'.join(block_content)
                    })
            elif '|' in line and line.strip().startswith('|') and line.strip().endswith('|'):
                # Basic table detection
                if i + 1 < len(lines) and '|' in lines[i+1] and '-' in lines[i+1]:
                    headers = [h.strip() for h in line.split('|') if h.strip()]
                    i += 2
                    table_data = []
                    while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
                        row = [cell.strip() for cell in lines[i].split('|')[1:-1]]
                        if len(row) == len(headers):
                            row_dict = dict(zip(headers, row))
                            table_data.append(row_dict)
                        i += 1
                    if current_section:
                        sections[current_section]["tables"].append(table_data)
                    continue
                else:
                    if current_section:
                        current_content.append(line)
            else:
                if current_section:
                    current_content.append(line)
            
            i += 1
            
        if current_section:
            sections[current_section]["content"] = '\n'.join(current_content)
            
        return {"sections": sections}

    def parse_views(self, filepath: str) -> Dict[str, Any]:
        """Parse Architecture_View.md (with PlantUML diagrams) into structured JSON."""
        logger.info(f"Parsing views: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return {}
            
        views = {}
        current_view = None
        
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#'):
                current_view = line.lstrip('#').strip()
                views[current_view] = {"diagrams": []}
                i += 1
                continue
                
            if line.startswith('```plantuml'):
                diagram_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    diagram_lines.append(lines[i])
                    i += 1
                    
                diagram_content = '\n'.join(diagram_lines)
                
                # Extract some basic plantuml info
                name_match = re.search(r'title\s+(.+)', diagram_content, re.IGNORECASE)
                name = name_match.group(1).strip() if name_match else "Unknown Diagram"
                
                # Try to guess type based on keywords
                diag_type = "Unknown"
                if "actor" in diagram_content or "usecase" in diagram_content:
                    diag_type = "UseCase"
                elif "class" in diagram_content:
                    diag_type = "Class"
                elif "state" in diagram_content:
                    diag_type = "State"
                elif "participant" in diagram_content:
                    diag_type = "Sequence"
                elif "component" in diagram_content or "package" in diagram_content:
                    diag_type = "Component/Package"
                    
                participants = re.findall(r'(?:participant|actor|class|component|node)\s+([A-Za-z0-9_]+)', diagram_content)
                relationships = re.findall(r'([A-Za-z0-9_]+)\s*(?:->|-->|=>|..>|--|>)\s*([A-Za-z0-9_]+)', diagram_content)
                
                diagram_data = {
                    "name": name,
                    "type": diag_type,
                    "participants": list(set(participants)),
                    "relationships": [{"from": r[0], "to": r[1]} for r in relationships],
                    "raw_content": diagram_content
                }
                
                if current_view:
                    views[current_view]["diagrams"].append(diagram_data)
                
            i += 1
            
        return {"views": views}

    def preprocess(self, doc_path: str, view_path: str) -> Dict[str, Any]:
        """Combined preprocessing. Returns full architecture context as JSON."""
        return {
            "documentation": self.parse_documentation(doc_path),
            "views": self.parse_views(view_path)
        }
