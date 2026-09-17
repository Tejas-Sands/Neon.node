# Expressive voice and smoother cuts — 2026-09-17

User-approved direction: the Leda audition moves toward the desired expressive
reel voice. Preserve credible explanation, add audible surprise at reactions,
and refine the already-improved transitions without adding more decoration.

## Evidence and design

- Exact reference: [CUDA reel](https://www.instagram.com/reel/DdYevTqEVSA/),
  around 17s: “The docs require CUDA twelve, which caught me by surprise.”
- GitHub run `35201843090`, SHA `41493b3d`, resolved Aria +5%. The original
  motion branch was deployed; its local +12% default did not override CI.
- Edge does not expose emotion instructions. Use opt-in Gemini 2.5 Flash
  Preview TTS, voice Leda, with concise performance direction and the existing
  Gemini key. Do not change billing, publishing paths, or workflow files.
- Keep Remotion. Extend outgoing visuals through the incoming reveal by at
  most ten frames. Preserve original scene starts, audio windows, subtitles,
  final duration, cover and still-ending contracts. Exclude quiz/ranking packs.

## Implementation sequence

1. Synthesize the whole narration in one request for context and consistent
   delivery. Split at measured gaps between scenes, never inside spoken words.
   Add transcript-checked audio alignment with installed faster-whisper small. Keep
   acoustic word intervals and original script spelling. Reject missing/extra
   words, changed numbers/negations and invalid timings; never guess captions.
2. Route `TTS_PROVIDER=gemini` or an explicit `gemini:Leda` voice to the new
   provider. Reuse shared silence trimming, scene fitting and audio mixing.
   On any failure clean temporary audio, restore planned scene
   lengths and restart the whole video on Edge Aria. Record the fallback reason.
3. Add visual-only tails in `Main.tsx` with capped overlap in `transitions.ts`.
   Test cumulative sequence arithmetic, protected packs and short scenes.
4. Generate an exact-CUDA-line audition plus matched moving-footage previews
   against `41493b3d`. Review boundary frames, unchanged covers and endings;
   run voice/provider, TypeScript, story, contrast, text and cover checks.
5. Update all AGENTS files and review evidence. Keep deployment status explicit.

## Activation and rollback

The user authorized promotion to main and activation for the next scheduled
reels on 2026-09-17. Preserve remote automated ledger commits with rebase.
Set the existing Variables only after the code reaches main, then read them
back. Do not manually dispatch a video. Inspect the next scheduled run's
resolved provider and audio before claiming a production listening result.

After this code reaches the deployment, the existing exported repository
Variable `TTS_PROVIDER=gemini` selects Leda without changing the workflow.
`VOICEOVER_RATE=+12%` is a prompt pace target for Gemini; it is not an exact
rate guarantee. `VOICEOVER_PITCH=+0Hz` retains natural fallback pitch.
Chatterbox is not part of this rollout. Existing account quotas apply.
The initial model download and
CPU ASR add startup time. No provider setting is changed by local previews.

Rollback: `TTS_PROVIDER=edge`, clear explicit `gemini:` voice overrides, and
restore the prior rate. Revert the visual-tail diff for motion rollback.
Audience impact remains unmeasured; compare mature metrics with coverage.
