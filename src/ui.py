from rich.console import Console
from rich.text import Text

console = Console()

def render_banner() -> None:
    """for the cli, minimal for now"""
    console.print("[bold cyan]=== CEPHALON ORDIS WEAVE INITIALIZED (Type 'exit' to quit) ===[/bold cyan]")

def get_user_input() -> str:
    return console.input("\n[bold green][OPERATOR]: [/bold green]").strip()

def render_ordis_output(segments: list[tuple[str, str]]) -> None:
    output = Text("\n[ORDIS]: ", style="bold cyan")
    for mode, chunk in segments:
        if mode == "glitch":
            output.append(f" ⚡ {chunk} ⚡ ", style="bold bright_red on black")
        else:
            output.append(f" {chunk} ", style="cyan")
    console.print(output)


