from rich.console import Console
from src.config import VOICEPRINT_PATH
from src.ears import OrdisEars

console = Console()

PROMPTS = [
    "Ordis, run a full diagnostic on the system and check my CPU temperatures.",
    "Operator online. Prepare the orbiter for our next mission and check the foundry.",
    "Hey Ordis, what is my battery percentage looking like right now?",
    "Ordis, talk to me and tell me a terrible cosmic joke.",
    "Ordis, check how much memory my laptop is using right now.",
]


def main() -> None:
    console.print("[bold cyan]=== CEPHALON ORDIS: OPERATOR BIOMETRIC RE-ENROLLMENT ===[/bold cyan]")
    console.print("[dim]Speak naturally at your normal sitting distance from the laptop.[/dim]\n")

    ears = OrdisEars()
    samples = []

    for i, sentence in enumerate(PROMPTS, 1):
        console.input(
            f"[yellow]Sample {i}/{len(PROMPTS)} — Press [ENTER], say this naturally, then pause:[/yellow]\n"
            f'  [bold white]"{sentence}"[/bold white]'
        )
        console.print("[bold red]● Listening... (Speak now, it will stop automatically when you finish)[/bold red]")
        audio = ears.record_utterance()
        if len(audio) == 0:
            console.print("[red]⚠ Didn't hear anything—try that one again.[/red]")
            continue

        samples.append(audio)
        console.print(f"[green]✓ Captured ({len(audio) / 16000:.1f}s of speech)[/green]\n")

    ears.verifier.enroll_from_samples(samples)
    console.print(f"[bold green]✓ New Voiceprint locked and saved to:[/bold green] {VOICEPRINT_PATH}")

    # Immediate self-test on the last sample!
    is_op, score = ears.verifier.verify(samples[-1])
    console.print(f"[bold cyan]Self-Test Score: {score:.3f} (Authorized: {is_op})[/bold cyan]")


if __name__ == "__main__":
    main()