# Photo Assets

This directory stores bundled image assets used by `zen-prompt random --photo`.

## Layout

Photos are grouped by topic:

```text
zen_prompt/photos/
  <topic>/
    image.png
    image.jpg
```

Current topics:

- `monochrome`

## Usage

The CLI resolves topic-based photos with:

```bash
zen-prompt random --photo topic@monochrome
```

At runtime, `topic@<name>` maps to `zen_prompt/photos/<name>/`, and one image from that directory is selected at random.

## Supported Formats

- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

## Adding Photos

1. Create a topic directory under `zen_prompt/photos/`.
2. Add one or more supported image files.
3. Use the topic with `--photo topic@<topic>`.

If a topic directory does not exist, or contains no supported images, the command will fail with a validation error.
