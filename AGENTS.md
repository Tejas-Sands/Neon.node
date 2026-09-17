# AGENTS.md — Root Directive: VIRAL GROWTH & ZERO-SKIP ENGINEERING
> **This file outranks all other instructions for content quality, hook design, and voice calibration.**
> Rules in `CLAUDE.md` govern the technical posting plumbing; rules here govern *why anyone watches*.
> Every AI assistant touching this repo must read this document **before** generating any script, prompt, or scene.

---

## CURRENT WORK — Voice pace + Brag-inspired motion (2026-09-17)

The user reports that timely news still earns weak results, the narrator sounds
too professional/slow, and Brag's animation style is a reference worth adapting.
The plan is now implemented locally on `feat/voice-brag-motion`; it is not deployed.
The user selected **Aria at +12%** after the matched voice auditions.

- Read [design](docs/superpowers/specs/2026-09-17-voice-and-brag-motion-design.md)
  and [implementation plan](docs/superpowers/plans/2026-09-17-voice-and-brag-motion.md)
  and [review record](docs/VOICE_MOTION_REVIEW.md) before extending this work.
  The review records measured artifacts and outstanding listening/rollout checks.
- Keep the developer/AI-builder audience in [GROWTH_PLAN](docs/GROWTH_PLAN.md).
  Being early is useful; each story must also explain a supported consequence
  for the viewer and provide useful evidence immediately after the hook.
- Prioritize matched voice auditions and measured pacing over adding effects.
  Local defaults are Aria, natural pitch, `+12%`, `VOICE_PACING=tight`. Tight
  fitting trims exterior silence, preserves word alignment and uses actual audio
  coverage plus reading floors. `VOICE_PACING=legacy` retains the old 90-frame /
  0.35s fitting. CI still exports `+5%` unless its existing Variable overrides it.
  Inspect resolved settings and audio; local defaults do not establish deployment.
- Brag is a Hyperframes-based storytelling skill, not a Remotion component
  library. Adapt its focused typography, concrete demonstrations and purposeful
  sound cues inside existing `StoryScene.tsx` / `storyMotion.ts`. Keep Remotion.
- Reuse free providers (Edge, optional existing Kokoro) and existing local audio.
  Do not copy Brag's music: its own README leaves exact licensing unverified.
- Existing source grounding, anti-repetition, frame-zero cover, HookPunch,
  still ending, format-pack budgets and feedback guards remain load-bearing.
  Preserve any configured runtime experiment; do not assume it is active.
- Follow `CLAUDE.md` and `AI_CONTEXT.md` §0 for frozen publishing paths.
  Local previews must never call posting entry points. This plan does not
  authorize changing dispatch, captions, schedules, tokens or publishing workflows.
- Judge results using mature saved metrics with coverage counts. No guaranteed
  virality, claimed shadowban, or causal diagnosis from low views alone.

Where older guidance below conflicts with this section or the current grounded
retention contract, use this section. Current limits: spoken hook **at most 12
words**, title at most four, on-screen hook text at most eight. Target a hook
under four seconds; revise overlong copy rather than clipping spoken audio.
Animation names such as `rise-mask` and `clip-wipe` below describe render-side
choices; do not emit them into backend schema fields that do not accept them.

---

## 🎯 THE ONE MISSION

> **Stop the scroll. Hold the frame. Earn the follow.**

The renderer already has substantial motion tooling. Weak hooks, formal delivery,
slow pacing and insufficiently concrete proof are improvement hypotheses, not a
proven explanation for low distribution. Test them against actual artifacts and
the saved metrics; technical polish alone does not establish content quality.

A viewer's thumb is on the screen. They are one frame away from leaving. You must make leaving feel like a *mistake*. That is the only goal of scene 0 (the hook). Everything else — the facts, the charts, the nice transitions — exists to *service* a viewer who was already stopped in the first 1.5 seconds.

---

## 🚨 THE FIVE LAWS (non-negotiable for every single video)

### LAW 1 — The Hook Must Create a Knowledge Gap Instantly

The human brain cannot resist an open loop. The hook's job is to *open* the loop, not answer it. The viewer should feel: *"Wait — I need to know how that ends."*

**The three hook patterns that work on Reels (pick one per video):**

| Pattern | Formula | Example |
|---|---|---|
| **Shock Stat** | `[Number] [surprising claim] — here's why that matters.` | `"OpenAI just lost $5B in a single quarter. Here's the number that explains why."` |
| **Broken Assumption** | `Everyone thinks [X]. [Y] actually happened.` | `"Everyone thinks GPT-4 is still the best. Three benchmarks disagree."` |
| **Stakes Reveal** | `[Named subject] just [did thing] — and your [thing] is already affected.` | `"Chrome just killed the API every ad blocker runs on. Starting January."` |

**What the hook MUST do in the first 3 words of voiceover:**
- Drop an unexpected number, OR
- Name a consequence the viewer didn't know existed, OR
- Contradict something the viewer believes is true

**What the hook MUST NEVER do:**
- BAD: `"Today we're looking at..."` — this is a death sentence for reach
- BAD: `"So,"` / `"Okay,"` / `"Hey guys,"` / `"Welcome back"` — wastes the only frame that matters
- BAD: Start with the *name* of the thing — the name means nothing until you've created desire to know it
- BAD: Answer the question the hook asked — that's what the next 4 scenes are for

### LAW 2 — The Voice Must Sound Like a Human Who Can't Believe What They're Saying

The target register is: **a brilliant friend who just found out something wild and called you immediately.** Not a podcast host. Not a news anchor. Not a textbook. A friend.

This means:
- **Lean-in sentences**: The voice physically leans in before the payoff. In text, this looks like: `"And the part nobody's talking about — it uses your laptop's RAM."` The dash is a lean-in. Use it.
- **Honest reactions**: `"Wild, right?"` / `"That's not a typo."` / `"Read that again."` — one per video, placed at the moment of maximum surprise.
- **Contractions always**: `"it's"`, `"that's"`, `"here's"`, `"they've"`. Full forms (`"it is"`, `"that is"`) sound robotic in TTS.
- **Second person always**: Every video must contain the word `"you"` or `"your"` — the viewer must feel addressed.
- **Specificity as energy**: `"20 milliseconds"` delivered with relish sounds more enthusiastic than `"very fast"`. The number IS the excitement.

**The ENERGY ARC of the voiceover across scenes:**
```
Scene 0 (Hook):   HIGH — surprising, urgent, immediate
Scene 1-2 (Why):  MID — grounded, factual, but still conversational
Scene 3 (Peak):   HIGHEST — the most surprising/impressive single detail
Scene 4-N (How):  MID — mechanism, context, implications
Final scene:      PAYOFF — rewarding, complete, leaves them smarter
```

### LAW 3 — Every Scene Must Raise the Stakes or Reveal a New Layer

The viewer's decision to stay is re-made at every cut. If a scene only repeats what was just said, they leave. If a scene answers a question but opens a *new* one, they stay.

**The "open loop cascade" technique:**
- Scene 1 hooks with the shock → opens loop A
- Scene 2 partially answers A → opens loop B (`"But that's not even the weird part..."`)
- Scene 3 answers B → opens loop C (`"Here's the number that should scare you..."`)
- Final scene closes all loops → gives the satisfying conclusion they stayed for

**Hard delete rule**: If a scene's entire voiceover would still be true if you replaced the subject with ANY other topic, delete the scene. Platitudes cost retention.

### LAW 4 — The On-Screen Text Must Work as a Silent Movie

A significant portion of viewers watch Reels on mute, or glance at the screen before tapping unmute. The on-screen `text`, `title`, and `subtitle` fields must tell a coherent story on their own.

This means:
- Scene 0 text should be **the most alarming/interesting 4-6 words** you can extract from the hook
- Numbers belong on-screen (they read instantly; voiceover can elaborate)
- Questions work great on screen (`"WHY IS NOBODY TALKING ABOUT THIS?"`)
- The final scene text should feel like a satisfying conclusion, not a generic CTA

**The "thumb-stop test"**: Pause the video on any frame. A stranger's thumb is hovering. Does the text on screen make them curious? If not, rewrite it.

### LAW 5 — The Outro Must Reward, Not Just Ask

A follow/subscribe ask without a reward feels transactional. A viewer who feels *smarter* at the end follows naturally. The CTA scene must:

1. **Close every loop** opened in the hook
2. **Deliver the one concrete takeaway** the viewer can use or share
3. **THEN** optionally ask for the follow — framed as: `"I cover stuff like this every week"` not `"Please follow for more content"`

The CTA text on the button should be an action tied to the content: `"TRY IT NOW"` / `"SEE THE REPO"` / `"READ THE DOCS"` — not a generic `"FOLLOW"`.

---

## SCENE-BY-SCENE CONSTRUCTION GUIDE

### Scene 0 — The Hook Scene (type: `hero`)

| Field | Requirement |
|---|---|
| `durationInFrames` | **100-120 frames MAX** (3.3-4s). Shorter is better. Instagram measures 3-second hold rate. |
| `title` | 2-4 words, ALL CAPS, the *subject* of the shock — NOT a description. `"$5B GONE"` not `"OpenAI Revenue"` |
| `text` | 4-8 words. The shocking claim, stated baldly. `"They lost it in a single quarter."` |
| `voiceover` | **First 3 words carry the punch.** Aim for 8-12 words, never over 12. Opens a factual loop, does NOT close it. |
| `textAnimation` | `"rise-mask"` or `"clip-wipe"` — powerful reveals, not gimmicky |
| `searchQuery` | The most visually dramatic image relevant to the subject |

### Scene 1-2 — The Stakes / Why-It-Matters

| Field | Requirement |
|---|---|
| `type` | `split`, `metric`, or `countdown` — show the number |
| `voiceover` | Answers *why the viewer should care*. Contains at least one specific number. |
| `text` | The concrete number or consequence — makes the stat scannable at a glance |

### Scene N-2 — The Mechanism / The Surprising Detail

This is the **"wait, REALLY?"** scene. It must contain the most technically surprising or counterintuitive detail about the subject. If this scene doesn't make the viewer want to pause and re-read, the writing is too safe.

### Final Scene — The Payoff

| Field | Requirement |
|---|---|
| `type` | `cta` or `split` |
| `voiceover` | Closes all loops. Delivers the "so here's what this means for you" statement. |
| `ctaText` | Action tied to the content, not a generic ask |

---

## VOICE CALIBRATION REFERENCE

### The TTS Prosody Cheat Sheet

The current free Edge-TTS integration has no emotion control. Punctuation can
influence phrasing, but does not guarantee an emotional performance. The table
below describes writing intentions; verify the result with real audio auditions.

| Effect | How to write it | Example |
|---|---|---|
| **Lean-in pause** | Em dash `—` | `"They did it — in a weekend."` |
| **Genuine rise** | Question mark `?` | `"So what actually changed?"` |
| **Peak brightness** | Exclamation mark `!` | `"That's not a patch — it's a full rewrite!"` |
| **Natural pause** | Period after a short sentence | `"Wild, right? Here's why."` |
| **Dramatic beat** | Short sentence, its own line | `"Yep. Every single one."` |
| **Specificity energy** | Exact number, said once | `"Twenty milliseconds. Not two hundred."` |

**Hard limits** (from the system prompt, enforced here):
- Max 2 exclamation marks per video total
- Max 2 short interjection sentences (`"Yep."`, `"No, really."`) per video
- Zero greetings, zero wind-up words at scene 0

### The Enthusiasm Spectrum

```
Too cold (kills shares):
  "The model performs well on reasoning tasks."

Too hot (kills credibility):
  "This AI is INSANE and will CHANGE EVERYTHING!!!"

Perfect (shares AND credibility):
  "It outscores GPT-4 on three benchmarks. That's the part nobody expected."
```

The sweet spot is **specificity + genuine surprise**. The surprise comes from the *fact*, not from adjectives.

---

## THE ALGORITHM — What Instagram Actually Rewards

Understanding what you're optimizing for:

| Signal | What it measures | How to engineer it |
|---|---|---|
| **3-second view rate** | Did they watch past 3 seconds? | Hook quality. The `hero` scene must pay off immediately. |
| **Completion rate** | What % watched to the end? | Open loop cascade. Each scene must raise stakes. |
| **Shares** | Did they send it to someone? | The "oh you HAVE to see this" moment. One per video. |
| **Saves** | Did they bookmark it? | A concrete, actionable insight they want to revisit. |
| **Comments** | Did it provoke a reaction? | A claim that's either surprising or slightly controversial (but factually true). |

**Measurement rule:** There is no verified Instagram reach equation here.
Prioritize a clear opening, useful proof and a rewarding ending as editorial
hypotheses. Watch/runtime ratio is not completion rate. Report only available
metrics, preserve missing values as unknown, and use the exposure/sample floors
in `docs/GROWTH_PLAN.md`; do not invent weights or universal retention targets.

---

## TECHNICAL HOOKS IN THE RENDER SYSTEM

The following render-system behaviors exist specifically to stop the scroll — make sure they're being used:

### HookPunch Component (Main.tsx)
The `HookPunch` component fires in the first 42 frames of scene 0: a radial gradient burst + expanding shock ring + particle burst. This is the visual equivalent of the first 3 spoken words. **It only fires on scene 0 and it is already implemented.** Do not disable or weaken it.

### Energy Schedule (energy.ts)
- Scene 0 energy: `0.52-0.65` (calmer hook so text lands clean — this is correct)
- Body scenes: `0.62-1.0` with a guaranteed spike per triple
- Final scene: `energy.still = true` (dead-still close — the strongest close on a kinetic feed)

Preserve this schedule while testing content, delivery and purposeful motion.
The schedule alone does not prove where the retention bottleneck lies.

### Visual Hook Patterns to Match Content
| Content type | Best visual treatment |
|---|---|
| Tech/AI breaking news | `grid-hud` + `JetBrains Mono` + `glitch-cut` transitions |
| Financial shock stat | `clean` + `Archivo` + `zoom-through` + `countdown` scene for the number |
| Product launch | `aurora` + `Space Grotesk` + `iris-open` transitions |
| Security/breach | `vhs-glitch` + `JetBrains Mono` + `glitch-shift` camera |
| Developer tools | `grid-hud` + `JetBrains Mono` or `Space Grotesk` + `dynamic-zoom-rotate` |

---

## SELF-EVALUATION CHECKLIST

Before finalizing any script, run through every item:

- [ ] **Hook test**: Read the first voiceover sentence aloud. Does it create a question the viewer needs answered?
- [ ] **3-word test**: Are the first 3 words of voiceover interesting ON THEIR OWN? Could they be a text notification that makes someone open the app?
- [ ] **Mute test**: Read only the on-screen `text` and `title` fields in order. Does the story make sense? Does it feel complete?
- [ ] **Platitude test**: Replace the subject with "AI" (generic). If the voiceover still sounds fine, it's a platitude. Delete and rewrite.
- [ ] **Loop test**: Is there an unanswered question between scenes 1-3 that the final scene closes?
- [ ] **Number test**: Is there at least one specific number in the first two scenes?
- [ ] **Voice test**: Does every sentence sound like something a human would actually say to a friend? Or does it sound like a Wikipedia summary?
- [ ] **Contraction test**: Grep for "it is", "that is", "there is" — replace all with contractions.
- [ ] **Energy arc test**: Does the voiceover feel MOST energetic at the most surprising single fact?

---

## HARD NOs — Things That Guarantee Low Reach

These patterns are content death. Zero tolerance:

| Pattern | Why it kills reach |
|---|---|
| Opening with the tool name | `"Zed editor has just released..."` — nobody cares about the name before they care about the story |
| Generic enthusiasm | `"This is amazing!"` — conveys nothing, signals low quality |
| Scene repeating the last scene | The algorithm detects completion rate drops at repeat moments |
| Abstract search queries | Returns random stock photos that make the video look amateur |
| Placeholder numbers (`X%`, `$N`) | Destroys credibility instantly |
| Asking for a follow before delivering value | Transactional; viewers smell it |
| More than one CTA in a video | Confuses the viewer, dilutes both |
| Scene over 250 frames with no scene-change | Attention span runs out at ~7 seconds on Reels |

---

## WHERE THESE RULES ARE ENFORCED IN CODE

| File | What it controls |
|---|---|
| `main.py` > `SYSTEM_PROMPT` | Script generation prompt (hooks, content rules, voice style) |
| `main.py` > `_SPOKEN_WARMTH_RULES` | The warmth/cheerful voice register addition |
| `src/remotion/MyComp/Main.tsx` > `HookPunch` | The visual scroll-stop burst on scene 0 |
| `src/remotion/MyComp/energy.ts` | Per-scene kinetics schedule |
| `src/remotion/MyComp/microDetails.ts` | Two seeded micro-details per video |
| `src/remotion/MyComp/AnimatedText.tsx` | All text animation modes |
| `ANIMATION_BRIEF.md` | The visual taste/motion brief |

---

## THE ONE-SENTENCE SUMMARY

> Write every script as if you're texting a friend who's about to swipe away — make the first sentence so specific and surprising that swiping feels like missing out, then earn every second after that with a new piece of information they couldn't predict.
