"""
VIDEX Form Automation - Main CLI Entry Point

Usage:
    python -m src.main scrape [--headless]
    python -m src.main fill --data <path> [--headless] [--submit]
    python -m src.main generate --schema <path>
"""

import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

# Base paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
SRC_DIR = BASE_DIR / "src"


def cmd_scrape(args: argparse.Namespace) -> int:
    """Run the form scraper to analyze the VIDEX form."""
    from .scraper.form_scraper import scrape_videx_form
    from .scraper.schema_generator import (
        generate_applicant_template,
        generate_flat_template,
        generate_pydantic_models,
        generate_field_mappings
    )
    
    console.print(Panel.fit(
        "[bold blue]VIDEX Form Scraper[/bold blue]\n"
        "Analyzing form structure and extracting field definitions..."
    ))
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    schema_path = OUTPUT_DIR / "fields_schema.json"
    
    try:
        # Run scraper
        schema = scrape_videx_form(
            headless=args.headless,
            output_path=schema_path,
            language=args.language
        )
        
        if not schema.sections:
            console.print("[yellow]Warning: No form pages were scraped. The form structure may have changed.[/yellow]")
            return 1
        
        console.print("\n[bold cyan]Generating templates and mappings...[/bold cyan]")
        
        # Generate templates
        generate_applicant_template(
            schema_path,
            OUTPUT_DIR / "applicant_template.json"
        )
        
        generate_flat_template(
            schema_path,
            OUTPUT_DIR / "applicant_flat.json"
        )
        
        # Generate code files
        generate_pydantic_models(
            schema_path,
            SRC_DIR / "automation" / "models.py"
        )
        
        generate_field_mappings(
            schema_path,
            SRC_DIR / "automation" / "field_mappings.py"
        )
        
        console.print(Panel.fit(
            "[bold green]Scraping Complete![/bold green]\n\n"
            f"Schema saved to: {schema_path}\n"
            f"Template saved to: {OUTPUT_DIR / 'applicant_template.json'}\n"
            f"Flat template: {OUTPUT_DIR / 'applicant_flat.json'}\n\n"
            "[cyan]Next steps:[/cyan]\n"
            "1. Edit the applicant template with your data\n"
            "2. Run: python -m src.main fill --data output/applicant_template.json"
        ))
        
        return 0
        
    except Exception as e:
        console.print(f"[bold red]Scraping failed: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return 1
 

def cmd_template(args: argparse.Namespace) -> int:
    """Generate an English-friendly template JSON file."""
    from .automation.field_translator import create_english_template
    import json
    
    output_path = Path(args.output) if args.output else OUTPUT_DIR / "english_template.json"
    
    template = create_english_template()
    
    with open(output_path, 'w') as f:
        json.dump(template, f, indent=2)
    
    console.print(f"[green]English template saved to: {output_path}[/green]")
    console.print("\n[cyan]Edit this file with your applicant data and run:[/cyan]")
    console.print(f"  python -m src.main fill --data {output_path}")
    
    return 0


def cmd_fill(args: argparse.Namespace) -> int:
    """Fill the VIDEX form with applicant data."""
    from .automation.form_filler import fill_videx_form
    from .automation.data_loader import ApplicantDataLoader
    
    data_path = Path(args.data)
    if not data_path.exists():
        console.print(f"[red]Data file not found: {data_path}[/red]")
        return 1
    
    schema_path = OUTPUT_DIR / "fields_schema.json"
    if not schema_path.exists():
        console.print("[yellow]Warning: No schema file found. Run 'scrape' first for better results.[/yellow]")
        schema_path = None
    
    # Load defaults if specified or use default path
    defaults_path = Path(args.defaults) if args.defaults else OUTPUT_DIR / "defaults.json"
    if not defaults_path.exists():
        defaults_path = None
    
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    save_pdf = not args.no_pdf
    
    console.print(Panel.fit(
        "[bold blue]VIDEX Form Filler[/bold blue]\n"
        f"Data file: {data_path}\n"
        f"Defaults: {defaults_path or 'None'}\n"
        f"Output dir: {output_dir}\n"
        f"Headless: {args.headless}\n"
        f"Save PDF: {save_pdf}\n"
        f"Submit: {args.submit}"
    ))
    
    if args.submit:
        console.print("[bold yellow]WARNING: Form will be submitted![/bold yellow]")
        response = input("Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            console.print("[cyan]Submission cancelled.[/cyan]")
            return 0
    
    try:
        results = fill_videx_form(
            data_path=data_path,
            schema_path=schema_path,
            defaults_path=defaults_path,
            headless=args.headless,
            submit=args.submit,
            save_pdf=save_pdf,
            output_dir=output_dir
        )
        
        # Summary
        success = results.get("success_count", 0)
        failed = results.get("fail_count", 0)
        pdf_path = results.get("pdf_path")
        
        summary_text = f"[bold green]Form Filling Complete![/bold green]\n\n"
        summary_text += f"Fields filled: {success}\n"
        summary_text += f"Fields failed: {failed}"
        
        if pdf_path:
            summary_text += f"\n\n[bold cyan]PDF saved to:[/bold cyan]\n{pdf_path}"
        
        console.print(Panel.fit(summary_text))
        
        return 0 if failed == 0 else 1
        
    except Exception as e:
        console.print(f"[bold red]Form filling failed: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return 1


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate templates and code from an existing schema."""
    from .scraper.schema_generator import (
        generate_applicant_template,
        generate_flat_template,
        generate_pydantic_models,
        generate_field_mappings
    )
    
    schema_path = Path(args.schema)
    if not schema_path.exists():
        console.print(f"[red]Schema file not found: {schema_path}[/red]")
        return 1
    
    console.print(Panel.fit(
        "[bold blue]Template Generator[/bold blue]\n"
        f"Schema: {schema_path}"
    ))
    
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        generate_applicant_template(
            schema_path,
            OUTPUT_DIR / "applicant_template.json"
        )
        
        generate_flat_template(
            schema_path,
            OUTPUT_DIR / "applicant_flat.json"
        )
        
        generate_pydantic_models(
            schema_path,
            SRC_DIR / "automation" / "models.py"
        )
        
        generate_field_mappings(
            schema_path,
            SRC_DIR / "automation" / "field_mappings.py"
        )
        
        console.print("[bold green]Generation complete![/bold green]")
        return 0
        
    except Exception as e:
        console.print(f"[bold red]Generation failed: {e}[/bold red]")
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate applicant data against the schema."""
    from .automation.data_loader import ApplicantDataLoader
    
    data_path = Path(args.data)
    if not data_path.exists():
        console.print(f"[red]Data file not found: {data_path}[/red]")
        return 1
    
    schema_path = OUTPUT_DIR / "fields_schema.json"
    if not schema_path.exists():
        console.print("[yellow]No schema file found. Run 'scrape' first.[/yellow]")
        schema_path = None
    
    try:
        loader = ApplicantDataLoader(data_path, schema_path)
        loader.load()
        loader.display_summary()
        
        is_valid, missing = loader.validate()
        
        if is_valid:
            console.print("\n[bold green]Validation passed! All required fields are filled.[/bold green]")
            return 0
        else:
            console.print(f"\n[bold red]Validation failed! Missing required fields:[/bold red]")
            for field in missing:
                console.print(f"  - {field}")
            return 1
            
    except Exception as e:
        console.print(f"[bold red]Validation failed: {e}[/bold red]")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="videx",
        description="VIDEX Visa Application Form Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape the form to discover all fields
  python -m src.main scrape
  
  # Scrape in headless mode (no visible browser)
  python -m src.main scrape --headless
  
  # Fill the form with applicant data
  python -m src.main fill --data output/applicant_template.json
  
  # Fill and submit the form
  python -m src.main fill --data output/applicant_template.json --submit
  
  # Validate applicant data
  python -m src.main validate --data output/applicant_template.json
  
  # Regenerate templates from existing schema
  python -m src.main generate --schema output/fields_schema.json
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scrape command
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape the VIDEX form to extract field definitions"
    )
    scrape_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    scrape_parser.add_argument(
        "--language",
        choices=["en", "de"],
        default="en",
        help="Language to use (en=English, de=German). Default: en"
    )
    
    # Fill command
    fill_parser = subparsers.add_parser(
        "fill",
        help="Fill the VIDEX form with applicant data"
    )
    fill_parser.add_argument(
        "--data",
        required=True,
        help="Path to applicant data JSON file"
    )
    fill_parser.add_argument(
        "--output",
        help="Directory to save the PDF output (default: output/)"
    )
    fill_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    fill_parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Don't save the form as PDF"
    )
    fill_parser.add_argument(
        "--defaults",
        help="Path to defaults JSON file (default: output/defaults.json)"
    )
    fill_parser.add_argument(
        "--submit",
        action="store_true",
        help="Actually submit the form (default: just fill without submitting)"
    )
    
    # Generate command
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate templates from an existing schema file"
    )
    generate_parser.add_argument(
        "--schema",
        required=True,
        help="Path to the schema JSON file"
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate applicant data against the schema"
    )
    validate_parser.add_argument(
        "--data",
        required=True,
        help="Path to applicant data JSON file"
    )
    
    # Template command
    template_parser = subparsers.add_parser(
        "template",
        help="Generate an English-friendly template JSON file"
    )
    template_parser.add_argument(
        "--output",
        help="Path for the output template file (default: output/english_template.json)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Print banner
    console.print(Panel.fit(
        "[bold cyan]VIDEX Form Automation Tool[/bold cyan]\n"
        "Automate German Schengen visa applications",
        border_style="cyan"
    ))
    
    # Dispatch to command handler
    if args.command == "scrape":
        return cmd_scrape(args)
    elif args.command == "fill":
        return cmd_fill(args)
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "template":
        return cmd_template(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

