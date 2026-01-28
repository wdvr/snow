#!/usr/bin/env python3
"""
Generate App Store description using Claude API.
Analyzes the codebase to understand all features and generates compelling copy.
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Installing anthropic package...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic


def get_repo_root() -> Path:
    """Get the repository root directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def get_swift_files(repo_root: Path) -> list[str]:
    """Get all Swift source files in the iOS app."""
    ios_path = repo_root / "ios"
    swift_files = []

    for pattern in ["**/*.swift"]:
        for f in ios_path.glob(pattern):
            # Skip test files and build artifacts
            if "Tests" in str(f) or "build" in str(f) or ".build" in str(f):
                continue
            swift_files.append(str(f))

    return swift_files[:30]  # Limit to avoid token limits


def read_file_contents(files: list[str], max_chars: int = 50000) -> str:
    """Read and concatenate file contents."""
    contents = []
    total_chars = 0

    for f in files:
        try:
            with open(f, "r") as file:
                content = file.read()
                if total_chars + len(content) > max_chars:
                    break
                contents.append(f"// File: {f}\n{content}\n")
                total_chars += len(content)
        except Exception:
            continue

    return "\n".join(contents)


def get_existing_metadata(repo_root: Path) -> dict:
    """Read existing metadata files."""
    metadata_path = repo_root / "ios" / "fastlane" / "metadata" / "en-US"
    metadata = {}

    for file in ["name.txt", "subtitle.txt", "keywords.txt"]:
        file_path = metadata_path / file
        if file_path.exists():
            metadata[file.replace(".txt", "")] = file_path.read_text().strip()

    return metadata


def generate_description(app_type: str = "snow") -> str:
    """Generate App Store description using Claude."""
    repo_root = get_repo_root()

    # Gather context
    swift_files = get_swift_files(repo_root)
    code_context = read_file_contents(swift_files)
    existing_metadata = get_existing_metadata(repo_root)

    # Determine app-specific context
    if app_type == "snow" or "snow" in str(repo_root).lower():
        app_context = """
        App: Powder Chaser (Snow Tracker)
        Purpose: Track snow conditions at ski resorts worldwide
        Key features to highlight:
        - Real-time snow conditions at multiple elevations
        - Fresh powder vs icy conditions estimation
        - Weather forecasts for ski resorts
        - Interactive map with resort locations
        - Favorites list for quick access
        - Multiple regions (Alps, North America, Japan, etc.)
        """
    else:
        app_context = """
        App: Footprint Travel Tracker
        Purpose: Track countries and places visited around the world
        Key features to highlight:
        - World map visualization of visited countries
        - State/province tracking for larger countries
        - Travel statistics and achievements
        - Beautiful visualizations
        """

    client = anthropic.Anthropic()

    prompt = f"""You are writing an App Store description for an iOS app.
Based on the code and context below, write a compelling App Store description.

{app_context}

Existing metadata:
- Name: {existing_metadata.get("name", "Unknown")}
- Subtitle: {existing_metadata.get("subtitle", "Unknown")}
- Keywords: {existing_metadata.get("keywords", "Unknown")}

Code context (key source files):
{code_context[:30000]}

Write an App Store description that:
1. Opens with a compelling hook (1-2 sentences)
2. Lists key features with bullet points or short paragraphs
3. Highlights what makes this app unique
4. Is between 200-400 words
5. DO NOT USE ANY EMOJIS - App Store Connect rejects them
6. Ends with a call to action

Output ONLY the description text, no additional commentary."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    description = response.content[0].text

    # Strip emojis - App Store Connect rejects them
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f700-\U0001f77f"  # alchemical symbols
        "\U0001f780-\U0001f7ff"  # Geometric Shapes
        "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U0001fa00-\U0001fa6f"  # Chess Symbols
        "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027b0"  # Dingbats
        "\U0001f1e0-\U0001f1ff"  # Flags
        "]+",
        flags=re.UNICODE,
    )
    description = emoji_pattern.sub("", description)

    return description.strip()


def main():
    """Main entry point."""
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Determine app type from repo name or argument
    app_type = "snow"
    if len(sys.argv) > 1:
        app_type = sys.argv[1]

    print("Generating App Store description...")
    description = generate_description(app_type)

    # Output to stdout
    print("\n" + "=" * 50)
    print("GENERATED DESCRIPTION:")
    print("=" * 50)
    print(description)
    print("=" * 50)

    # Also save to metadata file
    repo_root = get_repo_root()
    output_path = (
        repo_root / "ios" / "fastlane" / "metadata" / "en-US" / "description.txt"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(description)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
