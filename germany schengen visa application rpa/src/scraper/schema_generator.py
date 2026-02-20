"""
Schema Generator - Generates JSON templates and Pydantic models from scraped form data.
"""

import json
from pathlib import Path
from typing import Any, Optional
from rich.console import Console

console = Console()


def generate_applicant_template(schema_path: Path, output_path: Path) -> dict:
    """
    Generate an applicant data template JSON from the scraped schema.
    
    Args:
        schema_path: Path to the fields_schema.json file
        output_path: Path to save the applicant_template.json
    
    Returns:
        The generated template dictionary
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    template = {
        "_meta": {
            "description": "VIDEX Visa Application Data Template",
            "instructions": "Fill in all required fields (marked with required: true in comments)",
            "generated_from": str(schema_path)
        },
        "sections": {}
    }
    
    # Support both old format (form_pages) and new format (sections)
    sections = schema.get("sections", schema.get("form_pages", []))
    
    for section in sections:
        section_name = section.get("name_en", section.get("page_title", f"Section {section.get('index', 0)}"))
        section_key = f"section_{section.get('index', 0)}_{_sanitize_key(section_name)}"
        
        template["sections"][section_key] = {
            "_section_name": section_name,
            "fields": {}
        }
        
        for field in section.get("fields", []):
            field_id = field.get("id", "unknown")
            field_type = field.get("field_type", "text")
            required = field.get("required", False)
            options = field.get("options", [])
            
            # Generate appropriate default/placeholder value
            default_value = _get_default_value(field_type, options)
            
            template["sections"][section_key]["fields"][field_id] = {
                "value": default_value,
                "label": field.get("label", ""),
                "type": field_type,
                "required": required,
                "options": options if options else None,
                "max_length": field.get("max_length"),
            }
    
    # Save template
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    console.print(f"[green]Applicant template saved to {output_path}[/green]")
    return template


def generate_flat_template(schema_path: Path, output_path: Path) -> dict:
    """
    Generate a flat applicant data template (easier to fill).
    
    Args:
        schema_path: Path to the fields_schema.json file
        output_path: Path to save the flat template
    
    Returns:
        The generated flat template dictionary
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    template = {
        "_instructions": "Fill in all fields. Required fields are marked with (REQUIRED)",
    }
    
    # Support both old format (form_pages) and new format (sections)
    sections = schema.get("sections", schema.get("form_pages", []))
    
    for section in sections:
        section_name = section.get("name_en", section.get("page_title", ""))
        if section_name:
            template[f"_section_{section.get('index', 0)}"] = f"=== {section_name} ==="
        
        for field in section.get("fields", []):
            field_id = field.get("id", "unknown")
            field_type = field.get("field_type", "text")
            required = field.get("required", False)
            label = field.get("label", field_id)
            options = field.get("options", [])
            
            # Create descriptive key
            key = field_id
            
            # Add comment with field info
            comment_key = f"_comment_{field_id}"
            required_marker = "(REQUIRED)" if required else "(optional)"
            
            if options:
                # Handle both old format (list of strings) and new format (list of dicts)
                option_labels = []
                for opt in options[:5]:
                    if isinstance(opt, dict):
                        option_labels.append(opt.get("label", opt.get("value", "")))
                    else:
                        option_labels.append(str(opt))
                template[comment_key] = f"{label} {required_marker} - Options: {', '.join(option_labels)}{'...' if len(options) > 5 else ''}"
            else:
                template[comment_key] = f"{label} {required_marker}"
            
            template[key] = _get_default_value(field_type, options)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    console.print(f"[green]Flat template saved to {output_path}[/green]")
    return template


def generate_pydantic_models(schema_path: Path, output_path: Path) -> str:
    """
    Generate Pydantic model classes from the scraped schema.
    
    Args:
        schema_path: Path to the fields_schema.json file
        output_path: Path to save the generated Python file
    
    Returns:
        The generated Python code as a string
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    code_lines = [
        '"""',
        'Auto-generated Pydantic models for VIDEX form validation.',
        'Generated from scraped form schema.',
        '"""',
        '',
        'from typing import Optional, Literal',
        'from pydantic import BaseModel, Field',
        '',
        '',
    ]
    
    # Generate a model for each section/page
    section_models = []
    
    # Support both old format (form_pages) and new format (sections)
    sections = schema.get("sections", schema.get("form_pages", []))
    
    for section in sections:
        section_idx = section.get("index", section.get("page_number", 0))
        section_name = section.get("name_en", section.get("page_title", f"Section{section_idx}"))
        class_name = f"Section{section_idx}{_to_class_name(section_name)}"
        section_models.append(class_name)
        
        code_lines.append(f'class {class_name}(BaseModel):')
        code_lines.append(f'    """Fields from: {section_name}"""')
        code_lines.append('')
        
        if not section.get("fields"):
            code_lines.append('    pass')
            code_lines.append('')
            code_lines.append('')
            continue
        
        for field in section.get("fields", []):
            field_id = field.get("id", "unknown")
            field_name = _sanitize_field_name(field_id)
            field_type = field.get("field_type", "text")
            required = field.get("required", False)
            label = field.get("label", "")
            options = field.get("options", [])
            max_length = field.get("max_length")
            
            # Determine Python type
            py_type = _get_python_type(field_type, options)
            
            # Build Field() arguments
            field_args = []
            if label:
                field_args.append(f'description="{_escape_string(label)}"')
            if max_length:
                field_args.append(f'max_length={max_length}')
            
            # Generate field definition
            if required:
                if field_args:
                    code_lines.append(f'    {field_name}: {py_type} = Field(..., {", ".join(field_args)})')
                else:
                    code_lines.append(f'    {field_name}: {py_type}')
            else:
                if field_args:
                    code_lines.append(f'    {field_name}: Optional[{py_type}] = Field(None, {", ".join(field_args)})')
                else:
                    code_lines.append(f'    {field_name}: Optional[{py_type}] = None')
        
        code_lines.append('')
        code_lines.append('')
    
    # Generate main application model
    code_lines.append('class VidexApplication(BaseModel):')
    code_lines.append('    """Complete VIDEX visa application data."""')
    code_lines.append('')
    
    for model_name in section_models:
        attr_name = _to_snake_case(model_name)
        code_lines.append(f'    {attr_name}: {model_name}')
    
    code_lines.append('')
    
    # Write to file
    code = '\n'.join(code_lines)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(code)
    
    console.print(f"[green]Pydantic models saved to {output_path}[/green]")
    return code


def generate_field_mappings(schema_path: Path, output_path: Path) -> str:
    """
    Generate field mappings Python file from the scraped schema.
    
    Args:
        schema_path: Path to the fields_schema.json file
        output_path: Path to save the generated Python file
    
    Returns:
        The generated Python code as a string
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    code_lines = [
        '"""',
        'Auto-generated field mappings for VIDEX form automation.',
        'Maps JSON field keys to CSS selectors.',
        '"""',
        '',
        'from dataclasses import dataclass',
        'from typing import Optional',
        '',
        '',
        '@dataclass',
        'class FieldMapping:',
        '    """Represents a field mapping for form automation."""',
        '    field_id: str',
        '    selector: str',
        '    field_type: str',
        '    required: bool',
        '    section: str = ""',
        '    label: str = ""',
        '',
        '',
        '# Field mappings organized by section',
        'FIELD_MAPPINGS: dict[int, list[FieldMapping]] = {',
    ]
    
    # Support both old format (form_pages) and new format (sections)
    sections = schema.get("sections", schema.get("form_pages", []))
    
    for section in sections:
        section_idx = section.get("index", section.get("page_number", 0))
        section_name = section.get("name_en", section.get("page_title", ""))
        
        code_lines.append(f'    # Section {section_idx}: {section_name}')
        code_lines.append(f'    {section_idx}: [')
        
        for field in section.get("fields", []):
            field_id = field.get("id", "unknown")
            selector = field.get("selector", "")
            field_type = field.get("field_type", "text")
            required = field.get("required", False)
            label = _escape_string(field.get("label", ""))
            
            code_lines.append(f'        FieldMapping(')
            code_lines.append(f'            field_id="{field_id}",')
            code_lines.append(f'            selector="{selector}",')
            code_lines.append(f'            field_type="{field_type}",')
            code_lines.append(f'            required={required},')
            code_lines.append(f'            label="{label}",')
            code_lines.append(f'        ),')
        
        code_lines.append('    ],')
    
    code_lines.append('}')
    code_lines.append('')
    code_lines.append('')
    code_lines.append('# Flat mapping: field_id -> FieldMapping')
    code_lines.append('FLAT_MAPPINGS: dict[str, FieldMapping] = {')
    code_lines.append('    mapping.field_id: mapping')
    code_lines.append('    for mappings in FIELD_MAPPINGS.values()')
    code_lines.append('    for mapping in mappings')
    code_lines.append('}')
    code_lines.append('')
    code_lines.append('')
    code_lines.append('def get_selector(field_id: str) -> Optional[str]:')
    code_lines.append('    """Get the CSS selector for a field ID."""')
    code_lines.append('    mapping = FLAT_MAPPINGS.get(field_id)')
    code_lines.append('    return mapping.selector if mapping else None')
    code_lines.append('')
    code_lines.append('')
    code_lines.append('def get_required_fields() -> list[str]:')
    code_lines.append('    """Get list of all required field IDs."""')
    code_lines.append('    return [m.field_id for m in FLAT_MAPPINGS.values() if m.required]')
    code_lines.append('')
    
    code = '\n'.join(code_lines)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(code)
    
    console.print(f"[green]Field mappings saved to {output_path}[/green]")
    return code


# Helper functions

def _sanitize_key(text: str) -> str:
    """Convert text to a valid JSON key."""
    return ''.join(c if c.isalnum() else '_' for c in text.lower()).strip('_')


def _sanitize_field_name(text: str) -> str:
    """Convert text to a valid Python identifier."""
    # Handle empty or numeric-starting names
    name = ''.join(c if c.isalnum() or c == '_' else '_' for c in text)
    if name and name[0].isdigit():
        name = 'field_' + name
    return name or 'unknown_field'


def _to_class_name(text: str) -> str:
    """Convert text to a valid Python class name."""
    words = ''.join(c if c.isalnum() else ' ' for c in text).split()
    return ''.join(word.capitalize() for word in words)


def _to_snake_case(text: str) -> str:
    """Convert CamelCase to snake_case."""
    result = []
    for i, char in enumerate(text):
        if char.isupper() and i > 0:
            result.append('_')
        result.append(char.lower())
    return ''.join(result)


def _escape_string(text: str) -> str:
    """Escape string for use in Python code."""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _get_default_value(field_type: str, options: list) -> Any:
    """Get an appropriate default value for a field type."""
    if field_type == "checkbox":
        return False
    elif field_type == "select" and options:
        return ""  # Empty, user should select from options
    elif field_type == "date":
        return ""  # Format: YYYY-MM-DD
    elif field_type == "number":
        return None
    else:
        return ""


def _get_python_type(field_type: str, options: list) -> str:
    """Get the Python type annotation for a field type."""
    if field_type == "checkbox":
        return "bool"
    elif field_type == "number":
        return "int"
    elif field_type == "select" and options and len(options) <= 10:
        # Use Literal for small option sets
        # Handle both old format (strings) and new format (dicts)
        escaped_options = []
        for opt in options:
            if isinstance(opt, dict):
                label = opt.get("label", opt.get("value", ""))
            else:
                label = str(opt)
            escaped_options.append(f'"{_escape_string(label)}"')
        return f"Literal[{', '.join(escaped_options)}]"
    else:
        return "str"


if __name__ == "__main__":
    # Test generation
    base_path = Path(__file__).parent.parent.parent
    schema_path = base_path / "output" / "fields_schema.json"
    
    if schema_path.exists():
        generate_applicant_template(schema_path, base_path / "output" / "applicant_template.json")
        generate_flat_template(schema_path, base_path / "output" / "applicant_flat.json")
        generate_pydantic_models(schema_path, base_path / "src" / "automation" / "models.py")
        generate_field_mappings(schema_path, base_path / "src" / "automation" / "field_mappings.py")
    else:
        console.print("[red]Schema file not found. Run the scraper first.[/red]")

