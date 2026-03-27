"""
cli.py — CLI entry point for Auto Video Agent.

Orchestrates the full pipeline: plan → script → voiceover → assembly → export.
Commands: generate, interactive, batch, preview, validate, new-plan
"""

import os
import sys
from pathlib import Path

import click
import yaml

from .planner import load_plan, print_plan_summary, PlanError, VideoPlan, Clip
from .scriptwriter import generate_script, print_script, Script, ScriptLine
from .voiceover import generate_voiceover, load_voice_config, print_voiceover_summary
from .captions import generate_captions, print_captions_summary
from .assets import prepare_clips
from .compositor import compose_video, load_compositor_config
from .exporter import generate_output_path, validate_output, print_export_summary


# ---------------------------------------------------------------------------
# Shared pipeline logic
# ---------------------------------------------------------------------------

def _resolve_project_root(plan_path: str, project_root: str = None) -> str:
    if project_root:
        return project_root
    return str(Path(plan_path).parent.parent)


def _run_pipeline(plan: VideoPlan, project_root: str, skip_script_api: bool = False):
    """Run the full generation pipeline for a single plan."""

    # Step 1: Script
    click.echo("--- Generating Script ---")
    if skip_script_api:
        script = _script_from_plan(plan)
        click.echo("  (preview mode — script built from plan text, no API call)")
    else:
        try:
            script = generate_script(plan)
        except Exception as e:
            click.echo(f"\n  Error generating script: {e}", err=True)
            return None
    print_script(script)

    # Step 2: Voiceover
    click.echo("--- Generating Voiceover ---")
    try:
        os.makedirs("output", exist_ok=True)
        slug = plan.title.lower().replace(" ", "_")[:30]
        audio_path = f"output/{slug}_voiceover.mp3"

        voice, rate = load_voice_config(
            os.path.join(project_root, "config.yaml")
        )
        voiceover = generate_voiceover(script, audio_path, voice=voice, rate=rate)
    except Exception as e:
        click.echo(f"\n  Error generating voiceover: {e}", err=True)
        return None
    print_voiceover_summary(voiceover)

    # Step 3: Captions
    caption_track = None
    if plan.include_captions:
        click.echo("--- Generating Captions ---")
        caption_track = generate_captions(voiceover.word_timings, words_per_frame=3)
        print_captions_summary(caption_track)

    # Step 4: Assets
    click.echo("--- Preparing Assets ---")
    clips = prepare_clips(
        [{"path": c.path, "label": c.label} for c in plan.user_clips],
        project_root=project_root,
    )
    if clips:
        click.echo(f"  {len(clips)} clip(s) validated and ready")
    else:
        click.echo("  No user clips found — using gradient background")

    # Step 5: Compose
    click.echo("\n--- Assembling Video ---")
    config_path = os.path.join(project_root, "config.yaml")
    comp_config = load_compositor_config(config_path)
    output_path = generate_output_path(plan.title, output_dir="output")

    try:
        compose_video(
            voiceover=voiceover,
            caption_track=caption_track,
            clips=clips,
            output_path=output_path,
            config=comp_config,
            music_mood=plan.music,
            video_title=plan.title,
            cta_text=plan.call_to_action,
        )
    except Exception as e:
        click.echo(f"\n  Error assembling video: {e}", err=True)
        return None

    # Step 6: Validate
    click.echo("--- Exporting ---")
    result = validate_output(output_path)
    print_export_summary(result)
    return output_path


def _script_from_plan(plan: VideoPlan) -> Script:
    """Build a simple script directly from plan fields (no API call).

    Used for preview mode and when the API key is not configured.
    """
    lines = []

    # Hook
    lines.append(ScriptLine(
        text=plan.hook,
        duration=plan.timing.hook_seconds if plan.timing else 5.0,
        section="hook",
        caption=plan.hook[:30],
    ))

    # Body — one line per key point
    body_time = plan.timing.body_seconds if plan.timing else 25.0
    per_point = body_time / max(len(plan.key_points), 1)
    for point in plan.key_points:
        lines.append(ScriptLine(
            text=point,
            duration=round(per_point, 1),
            section="body",
            caption=point[:30],
        ))

    # CTA
    lines.append(ScriptLine(
        text=plan.call_to_action,
        duration=plan.timing.cta_seconds if plan.timing else 5.0,
        section="cta",
        caption=plan.call_to_action[:30],
    ))

    total = sum(l.duration for l in lines)
    return Script(lines=lines, total_duration=round(total, 1))


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(version="0.2.0")
def cli():
    """Auto Video Agent — AI-powered short video creator for auto repair marketing."""
    pass


@cli.command()
@click.argument("plan_path", type=click.Path(exists=True))
@click.option("--project-root", default=None, help="Project root for resolving clip paths")
def generate(plan_path, project_root):
    """Generate a video from a YAML plan file.

    Uses Claude API for script generation, Edge TTS for voiceover,
    and FFmpeg for video assembly with styled captions, music, and branding.
    """
    project_root = _resolve_project_root(plan_path, project_root)

    click.echo("\n--- Loading Plan ---")
    try:
        plan = load_plan(plan_path, project_root=project_root)
    except PlanError as e:
        click.echo(f"\n  Error: {e}", err=True)
        sys.exit(1)

    print_plan_summary(plan)
    result = _run_pipeline(plan, project_root, skip_script_api=False)
    if not result:
        sys.exit(1)


@cli.command()
@click.argument("plan_path", type=click.Path(exists=True))
@click.option("--project-root", default=None, help="Project root for resolving clip paths")
def preview(plan_path, project_root):
    """Quick preview render — skips Claude API, builds script from plan text.

    Great for testing your plan before using API credits.
    Uses plan hook + key points + CTA directly as the script.
    """
    project_root = _resolve_project_root(plan_path, project_root)

    click.echo("\n--- Loading Plan (Preview Mode) ---")
    try:
        plan = load_plan(plan_path, project_root=project_root)
    except PlanError as e:
        click.echo(f"\n  Error: {e}", err=True)
        sys.exit(1)

    print_plan_summary(plan)
    result = _run_pipeline(plan, project_root, skip_script_api=True)
    if not result:
        sys.exit(1)


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--project-root", default=None, help="Project root for resolving clip paths")
@click.option("--no-api", is_flag=True, help="Skip Claude API — use plan text as script")
def batch(paths, project_root, no_api):
    """Process multiple video plans at once.

    Pass individual YAML files or a directory containing YAML plans.

    Examples:
        python -m src batch templates/plan1.yaml templates/plan2.yaml
        python -m src batch templates/
        python -m src batch templates/ --no-api
    """
    # Expand directories into YAML files
    plan_files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            plan_files.extend(sorted(path.glob("*.yaml")))
            plan_files.extend(sorted(path.glob("*.yml")))
        else:
            plan_files.append(path)

    if not plan_files:
        click.echo("No plan files found.")
        sys.exit(1)

    click.echo(f"\n=== Batch Mode: {len(plan_files)} plan(s) ===\n")
    results = []

    for i, plan_file in enumerate(plan_files, 1):
        plan_path = str(plan_file)
        root = _resolve_project_root(plan_path, project_root)

        click.echo(f"\n{'='*50}")
        click.echo(f"  [{i}/{len(plan_files)}] {plan_file.name}")
        click.echo(f"{'='*50}")

        try:
            plan = load_plan(plan_path, project_root=root)
        except PlanError as e:
            click.echo(f"  SKIPPED — {e}")
            results.append((plan_file.name, "FAILED", str(e)))
            continue

        print_plan_summary(plan)
        output = _run_pipeline(plan, root, skip_script_api=no_api)

        if output:
            results.append((plan_file.name, "OK", output))
        else:
            results.append((plan_file.name, "FAILED", "Pipeline error"))

    # Summary
    click.echo(f"\n{'='*50}")
    click.echo(f"  Batch Summary")
    click.echo(f"{'='*50}")
    ok = sum(1 for _, s, _ in results if s == "OK")
    fail = len(results) - ok
    for name, status, detail in results:
        icon = "OK" if status == "OK" else "FAIL"
        click.echo(f"  [{icon}] {name} — {detail}")
    click.echo(f"\n  {ok} succeeded, {fail} failed out of {len(results)} total\n")


@cli.command()
def interactive():
    """Build a video plan interactively via guided prompts, then generate."""
    click.echo("\n--- Interactive Video Builder ---\n")

    title = click.prompt("  Video title")

    click.echo("\n  Video types: educational_tip, before_after, common_mistake, promo")
    video_type = click.prompt("  Type", default="educational_tip")

    click.echo("\n  Tones: friendly, authoritative, urgent, humorous")
    tone = click.prompt("  Tone", default="friendly")

    hook = click.prompt("\n  Hook (attention-grabbing opening line)")

    click.echo("\n  Key points (enter each point, empty line to finish):")
    key_points = []
    while True:
        point = click.prompt(f"    Point {len(key_points) + 1}", default="", show_default=False)
        if not point:
            if not key_points:
                click.echo("    (need at least one point)")
                continue
            break
        key_points.append(point)

    cta = click.prompt("\n  Call to action")

    click.echo("\n  Music moods: upbeat, chill, dramatic, none")
    music = click.prompt("  Music", default="upbeat")

    duration = click.prompt("\n  Target duration (seconds)", default=45, type=int)
    include_captions = click.confirm("  Include captions?", default=True)
    include_logo = click.confirm("  Include logo?", default=True)

    # Ask about clips
    clips = []
    if click.confirm("\n  Do you have video clips to include?", default=False):
        click.echo("  Enter clip paths (empty line to finish):")
        while True:
            clip_path = click.prompt(f"    Clip {len(clips) + 1} path", default="", show_default=False)
            if not clip_path:
                break
            label = click.prompt(f"    Label for this clip", default="")
            clips.append({"path": clip_path, "label": label})

    # Build the plan
    plan = VideoPlan(
        title=title,
        type=video_type,
        tone=tone,
        hook=hook,
        key_points=key_points,
        call_to_action=cta,
        music=music,
        duration_target=duration,
        include_captions=include_captions,
        include_logo=include_logo,
        user_clips=[Clip(path=c["path"], label=c["label"]) for c in clips],
    )

    # Calculate timing
    from .planner import _calculate_timing
    plan.timing = _calculate_timing(plan)

    click.echo("\n--- Plan Summary ---")
    print_plan_summary(plan)

    # Option to save the plan
    if click.confirm("  Save this plan as a YAML file?", default=True):
        save_path = click.prompt("  Save to", default=f"templates/{title.lower().replace(' ', '_')[:30]}.yaml")
        _save_plan_yaml(plan, save_path)
        click.echo(f"  Saved to {save_path}")

    # Option to use API or preview
    use_api = click.confirm("\n  Use Claude API for script? (No = use plan text directly)", default=True)

    click.echo()
    project_root = str(Path.cwd())
    _run_pipeline(plan, project_root, skip_script_api=not use_api)


@cli.command("new-plan")
@click.argument("name")
@click.option("--type", "video_type", default="educational_tip",
              type=click.Choice(["educational_tip", "before_after", "common_mistake", "promo"]),
              help="Video type template")
@click.option("--output-dir", default="templates", help="Directory to save the template")
def new_plan(name, video_type, output_dir):
    """Create a new video plan template YAML file.

    Examples:
        python -m src new-plan "Tire Rotation Tips"
        python -m src new-plan "Oil Change Special" --type promo
    """
    templates = {
        "educational_tip": {
            "hook": "Did you know this about your car? Most people don't.",
            "key_points": [
                "Key fact or insight #1",
                "Why this matters for your car",
                "What you should do about it",
            ],
            "call_to_action": "Follow for more car tips — and book your service today!",
            "tone": "friendly",
            "music": "upbeat",
            "duration_target": 45,
        },
        "before_after": {
            "hook": "Look at the difference — this is what we do every day.",
            "key_points": [
                "Here's what it looked like before",
                "The problem we found during inspection",
                "And here's the result after our work",
            ],
            "call_to_action": "Want results like this? Book with us today!",
            "tone": "friendly",
            "music": "upbeat",
            "duration_target": 40,
        },
        "common_mistake": {
            "hook": "Stop doing this to your car — it's costing you money.",
            "key_points": [
                "The mistake most people make",
                "Why it's damaging your vehicle",
                "The right way to handle it",
            ],
            "call_to_action": "Don't risk it — bring it to the pros. Link in bio.",
            "tone": "urgent",
            "music": "dramatic",
            "duration_target": 40,
        },
        "promo": {
            "hook": "Limited time offer you don't want to miss.",
            "key_points": [
                "What's included in the deal",
                "Why this service matters",
                "The special price — this month only",
            ],
            "call_to_action": "Book now before the deal ends — link in bio!",
            "tone": "friendly",
            "music": "chill",
            "duration_target": 35,
        },
    }

    template = templates[video_type]
    plan_data = {
        "title": name,
        "type": video_type,
        "tone": template["tone"],
        "hook": template["hook"],
        "key_points": template["key_points"],
        "call_to_action": template["call_to_action"],
        "user_clips": [],
        "music": template["music"],
        "duration_target": template["duration_target"],
        "include_captions": True,
        "include_logo": True,
    }

    os.makedirs(output_dir, exist_ok=True)
    slug = name.lower().replace(" ", "_")[:30]
    file_path = os.path.join(output_dir, f"{slug}.yaml")

    with open(file_path, "w") as f:
        yaml.dump(plan_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    click.echo(f"\n  Created template: {file_path}")
    click.echo(f"  Type: {video_type}")
    click.echo(f"  Edit the file, fill in your content, then run:")
    click.echo(f"    python -m src generate {file_path}")
    click.echo(f"    python -m src preview {file_path}  (no API needed)\n")


@cli.command()
@click.argument("plan_path", type=click.Path(exists=True))
def validate(plan_path):
    """Validate a video plan YAML file without generating anything."""
    try:
        plan = load_plan(plan_path)
        print_plan_summary(plan)
        click.echo("  Plan is valid!\n")
    except PlanError as e:
        click.echo(f"\n  Validation failed: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_plan_yaml(plan: VideoPlan, path: str) -> None:
    """Save a VideoPlan to a YAML file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    data = {
        "title": plan.title,
        "type": plan.type,
        "tone": plan.tone,
        "hook": plan.hook,
        "key_points": plan.key_points,
        "call_to_action": plan.call_to_action,
        "user_clips": [
            {"path": c.path, "label": c.label} for c in plan.user_clips
        ] if plan.user_clips else [],
        "music": plan.music,
        "duration_target": plan.duration_target,
        "include_captions": plan.include_captions,
        "include_logo": plan.include_logo,
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def main():
    cli()


if __name__ == "__main__":
    main()
