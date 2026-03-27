# Use Case: Weekly Social Media Video Content for an Auto Repair Shop

## Background

A local auto repair shop wants to grow its social media presence on Facebook Reels, Instagram Reels, and TikTok. The owner knows that short-form video is the #1 way to reach new customers — but creating videos is time-consuming. Between running the shop, managing staff, and servicing vehicles, there's no time to script, record voiceovers, edit, add captions, and export videos every week.

## The Problem

- **Time:** Editing a single 30–60 second video manually takes 1–2 hours
- **Cost:** Hiring a videographer or social media agency costs $500–$2,000/month
- **Consistency:** Posting falls off after a few weeks because the process is too manual
- **Quality:** DIY videos often lack captions, branding, and professional pacing

## The Solution: Auto Video Agent

Auto Video Agent lets the shop owner go from a video idea to a ready-to-post Reel in under 2 minutes — with zero editing skills required.

## Workflow

### Step 1: Create a Video Plan (30 seconds)

The owner fills out a simple YAML template or uses the interactive CLI:

```bash
python -m src interactive
```

They answer a few questions:
- **Title:** "5 Signs Your Brakes Need Replacing"
- **Type:** educational_tip
- **Hook:** "Hear a squealing noise when you brake? Don't ignore it."
- **Key points:** worn pads, grinding sounds, longer stopping distance
- **Call to action:** "Book a free brake check — link in bio"
- **Music:** upbeat

### Step 2: Generate the Video (90 seconds)

```bash
python -m src generate templates/brake_signs.yaml
```

The agent automatically:
1. **Writes a script** using Claude AI — optimized for short-form video with a scroll-stopping hook, concise body, and clear CTA
2. **Generates a voiceover** using Edge TTS — natural-sounding, free, no API key needed
3. **Creates styled captions** — uppercase text on dark pills, synced word-by-word to the audio
4. **Adds background music** — mood-matched, auto-ducked under the voiceover
5. **Generates a brand intro** — logo + title card with fade-in
6. **Generates a CTA outro** — call to action card with "Follow for more"
7. **Assembles everything** into a 1080x1920 MP4 with FFmpeg
8. **Validates** the output meets platform specs (file size, duration, resolution)

### Step 3: Upload (30 seconds)

The owner opens the `output/` folder, picks up the MP4, and posts it directly to Facebook, Instagram, or TikTok. Done.

## Weekly Content Calendar Example

Using batch mode, the owner can generate an entire week of content at once:

```bash
python -m src batch templates/ --no-api
```

| Day       | Video                                    | Type            |
|-----------|------------------------------------------|-----------------|
| Monday    | "Why Your Car Shakes When Braking"       | Educational Tip |
| Wednesday | "The #1 Oil Change Mistake"              | Common Mistake  |
| Friday    | "Summer AC Check — $49.99 Special"       | Promo           |
| Sunday    | "Headlight Restoration Before & After"   | Before/After    |

4 videos generated in under 5 minutes. Each one is branded, captioned, and ready to post.

## Results

- **Time saved:** From 4–8 hours/week to under 10 minutes
- **Cost:** $0 (Edge TTS is free, Claude API costs ~$0.01–0.03 per script)
- **Consistency:** Batch mode makes it easy to prepare a full week in one sitting
- **Quality:** Every video has professional captions, music, branding, and pacing

## Who This Is For

- Auto repair shop owners who want to grow on social media
- Service managers who need marketing content but don't have a marketing team
- Any small business in a hands-on trade (HVAC, plumbing, electrical) that can swap in their own templates

## Technical Requirements

- Python 3.11+
- FFmpeg (installed via `apt install ffmpeg` on Ubuntu/WSL)
- Anthropic API key (optional — preview mode works without one)
- No GPU required — runs on any machine
