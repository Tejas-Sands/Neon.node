# Animation & Randomness Brief — questionnaire

Goal: pin down exactly what "more graphical, more little effects, minimalist but impactful"
means for you, so the render side (`src/remotion/`) can be extended without guessing.

## The organizing principle (stated 2026-07-26) — outranks every answer below

> "People should be able to properly understand the news I'm showing — for that it needs to be
> a bit calmer. But to keep people hooked there needs to be a bit of kinetics so they don't
> leave. There needs to be a balance of that. That's my main aim."

**Comprehension is the objective; kinetics is instrumental.** Motion exists to buy attention, not
to decorate. Where an answer below would trade legibility for movement, the principle wins and the
answer gets reinterpreted, not obeyed literally.

Two consequences that resolve the tensions in the answers:

- **Energy is a schedule, not a level.** Q8 asks for "always something moving"; the principle says
  reading must not compete with motion. Both hold if energy varies *across* the video — kinetic
  between reading moments, calm while a headline or subtitle is landing, dead still on the final
  scene (Q9b). A constant medium-high level would satisfy Q8 and fail the principle.
- **Legibility is a floor, not a preference.** Q32 wants brighter photos, but backgrounds are
  currently crushed to 0.6–0.76 brightness *specifically* to keep text readable. The photo can only
  brighten to the extent that plates/scrims take over that duty, enforced as a checkable contrast
  minimum — not eyeballed per look.

**How to answer:** fill the answer sheet in §0 — one line per question, e.g. `Q7: b, d`.
Anything you skip, I'll keep at the current behavior (marked `← now`).
Free-text answers are welcome anywhere; the options exist to make it fast, not to box you in.

---

## §0 — Answer sheet (fill this, ignore the rest if you're in a hurry)

```
Q1: a,b,c,d     Q2: d     Q3:a      Q4:f      Q5: a,c,d
Q6: a     Q7: b    Q8:c     Q9:b     Q10:d
Q11:b     Q12:b     Q13:f     Q14:a,b,c,d,e,f     Q15:a
Q16:c     Q17:c     Q18:a,b,c,f     Q19:b     Q20:c,d
Q21:b     Q22:f     Q23:a,b,c,d,e,f     Q24: All of them look great    Q25:b
Q26:c     Q27:a     Q28:c     Q29:a,d,e,f     Q30:b
Q31:d     Q32:a     Q33:b    Q34:b     Q35:b

Hard NOs (anything that must never appear):

Reference accounts / videos whose motion I want (links or handles):@holke79, @matvoyce
```

---

## §1 — Taste anchor

**Q1. Which of these is closest to the target?**
- a) Apple product page — near-static, one perfect move per scene, huge negative space
- b) Vox / Johnny Harris explainer — editorial type, map/diagram energy, hard cuts
- c) Sports/hype broadcast — punchy, kinetic, chrome-heavy
- d) Swiss poster in motion — giant type, grid discipline, almost no effects
- e) Cinematic doc trailer — slow push-ins, grain, letterbox, long dissolves

**Q2. If a viewer stopped one of your videos on a random frame, what should make it look designed?**
- a) The typography alone
- b) Type + one graphic accent (line, rule, chip)
- c) The photo treatment / grade
- d) Layered composition (multiple planes, depth)

---

## §2 — Randomness policy

Right now **every video rolls a fresh look from its seed**: 5 backgrounds × 5 chrome styles ×
6 grades × 4 motion feels × 4 text layouts × 4 title treatments × 4 finishes. That's why no two
videos match — but it also means there's no recognizable "house style."

**Q3. Where should the dial sit?**
- a) More variety than now — I want each video to feel like a different designer made it
- b) About right ← now
- c) Tighter — one recognizable house style, randomness only in the details
- d) Two or three fixed "series looks" that rotate (e.g. Mono / Editorial / Neon), random within each

**Q4. Which dimensions should be LOCKED across all videos (pick any)?**
- a) Font family (currently 5 rotate)
- b) Color grade (currently 6 rotate)
- c) Text layout / alignment (currently 4 rotate)
- d) Chrome level — HUD vs minimal (currently 5 rotate)
- e) Motion personality (currently 4 rotate)
- f) Nothing — keep all of it rolling ← now

**Q5. Which dimensions should get MORE variety than they have now?**
- a) Backgrounds / photo treatment
- b) Transitions
- c) Text animation
- d) Graphic accents (shapes, lines, rules)
- e) Layout / composition
- f) Color

**Q6. Should the look be driven by the TOPIC, not just the seed?**
(e.g. a finance story always gets the cold editorial look; a space story always gets the aurora look)
- a) Yes, strongly — topic should pick the look family
- b) Slightly — topic nudges the palette only
- c) No, keep it purely seed-random ← now

**Q7. Should the look repeat occasionally on purpose, so the feed reads as a series?**
- a) Yes — reuse a look every ~4-5 videos
- b) Yes, but only within the same topic channel
- c) No, always fresh ← now

---

## §3 — Motion energy

**Q8. Overall energy budget per video:**
- a) Very low — one motion at a time, everything else still
- b) Low-medium — one dominant motion + one subtle secondary ← roughly now
- c) Medium-high — layered motion, always something moving
- d) High — constant kinetic energy

**Q9. Should motion ever fully STOP?** (a held, dead-still beat is a strong minimalist move)
- a) Yes — every video should have 1-2 completely still beats
- b) Yes — hold still on the final scene only
- c) No, keep something always moving ← now

**Q10. Preferred easing character:**
- a) Springy / overshoot (bouncy)
- b) Sharp in, soft out (snappy, editorial) 
- c) Slow, even, cinematic
- d) Mixed per video ← now

**Q11. Scene length feel — current videos are ~5 scenes over ~28s:**
- a) Fewer, longer scenes (more room to breathe)
- b) About right ← now
- c) More, shorter scenes (faster rhythm)
- d) Varied within one video — long, long, quick-quick, long

---

## §4 — Typography

Current: 5 fonts, 13 text-animation modes (typewriter, glitch-decode, fade-up, slide-in,
word-by-word, scale-pop, blur-in, wave, rise-mask, flip-in, clip-wipe, tracking-in, none),
4 title treatments (solid / outline / gradient-fill / boxed).

**Q12. Type scale ambition:**
- a) Go much bigger — headline type that fills the frame edge-to-edge
- b) Bigger than now, moderately
- c) Current scale is right ← now
- d) Smaller, more restrained

**Q13. Which text animations should be RETIRED (feel cheap / dated)?**
- a) typewriter
- b) glitch-decode
- c) wave
- d) scale-pop
- e) word-by-word
- f) none of them — keep all ← now

**Q14. Text animations you want MORE of / added:**
- a) Mask reveals (text wiped in behind a moving edge)
- b) Line-by-line stagger for multi-line headlines
- c) Letter-spacing settle (tracking-in)
- d) Number roll-ups / counters for stats
- e) Word emphasis — one key word highlighted mid-sentence
- f) Text that reacts to the cut (settles as the scene lands)

**Q15. Subtitle band treatment:**
- a) Keep as-is ← now
- b) Bigger, bolder, more of a design element
- c) Smaller / quieter, get out of the way
- d) Karaoke-style word highlight synced to the voiceover

**Q16. Should headlines ever break the grid?** (type running off-frame, rotated, oversized behind subject)
- a) Yes, regularly — it's the strongest minimalist move
- b) Occasionally, as an accent
- c) No, keep everything inside the safe area ← mostly now

---

## §5 — Cuts & transitions

Current: 1 "signature" transition + 1 accent per video; most boundaries are hard cuts or a
~7% punch-in; a dressed transition lands at most every 3rd boundary.

**Q17. Cut density:**
- a) More hard cuts, fewer dressed transitions (more editorial)
- b) Current balance is right ← now
- c) More dressed transitions

**Q18. Which transition families do you actually like?**
- a) Dissolves / blur-dissolve
- b) Whip pans
- c) Wipes / blinds / iris
- d) Zoom-through / punch
- e) Glitch / chromatic
- f) Film burn / light-driven
- g) Just hard cuts, honestly

**Q19. Should the first 1.5 seconds get special treatment?** (the scroll-stopper)
- a) Yes — a distinct, louder opening move, then calm down
- b) Yes — but calmer than the body, let the type land clean
- c) No, treat scene 1 like the others ← roughly now

**Q20. Ending:**
- a) Hard stop on the last frame
- b) Settle and hold ← now
- c) Deliberate outro card with the follow CTA
- d) Loop-friendly — last frame matches the first

---

## §6 — Background & camera

Current: 10 camera moves (ken-burns, zoom-slow, pan, dynamic-zoom-rotate, vertigo, orbit-drift,
pulse-zoom, glitch-shift, pan-tilt, static), 6 overlays (grid-hud, particles, clean, vhs-glitch,
fantasy-sparks, aurora), 5 background styles.

**Q21. Photo/background camera motion:**
- a) Slower and subtler than now
- b) About right ← now
- c) More dynamic
- d) Static frames, let the graphics carry the motion

**Q22. Which overlays should go?**
- a) particles
- b) fantasy-sparks
- c) vhs-glitch
- d) grid-hud
- e) aurora
- f) keep all ← now

**Q23. Background ambition — want any of these added?**
- a) Duotone / halftone photo treatments (partly exists)
- b) Solid-color scenes with no photo at all
- c) Split-screen / two-image compositions
- d) Photo masked inside a shape or letterform
- e) Subtle parallax — foreground graphics moving against the photo
- f) Blurred photo as a color field, subject as a cutout

---

## §7 — Micro-details (the "little effects here and there")

This is the section that matters most for your ask. All of these are small, cheap, and read as craft.

**Q24. Which of these do you want added? (pick freely — this is the wishlist)**
- a) Hairline rules that draw themselves in under headlines
- b) Small ticking counters / timecode that feel "live"
- c) Corner marks or crop registration ticks that reposition per scene
- d) A single accent dot/shape that travels between scenes as a through-line
- e) Micro-shadow / depth pop on text as it lands
- f) Subtle chromatic fringe on cuts only (not constant)
- g) Grain / texture that breathes rather than sitting static
- h) Scene-number or progress indicator that animates rather than jumping
- i) Light sweep across type on emphasis words
- j) Edge-of-frame masking that reveals the next scene's color early

**Q25. How many micro-details should be live at once?**
- a) Exactly one, always
- b) One or two ← roughly now
- c) Two or three
- d) As many as look good

**Q26. Should micro-details be seeded-random or fixed as house style?**
- a) Fixed — same details every video, that's the brand
- b) Fixed set, random placement/timing
- c) Randomly chosen per video ← now

**Q27. Emphasis moments — should a specific word/number in the voiceover trigger a visual hit?**
- a) Yes — the key stat/number gets a dedicated graphic moment
- b) Yes, but subtle (color shift or scale bump only)
- c) No

---

## §8 — Chrome / on-screen furniture

Current chrome styles: hud-heavy, minimal, editorial, broadcast, kinetic — each toggles a fixed
set of progress bar / scene counter / corner brackets / rings / floating shapes.

**Q28. On-screen furniture in general:**
- a) Strip it back hard — type and photo only
- b) Less than now
- c) About right ← now
- d) More

**Q29. Which pieces earn their place?**
- a) Progress bar
- b) Scene counter
- c) Corner brackets
- d) Rings
- e) Floating shapes
- f) Lower-third / source attribution
- g) None of them

**Q30. Source attribution (where the story came from):**
- a) Always visible, designed as a feature
- b) Brief, on the first scene only
- c) Keep it minimal/quiet ← roughly now

---

## §9 — Color

**Q31. Palette approach:**
- a) One accent color per video, everything else neutral
- b) Two-color system (primary + secondary) ← now
- c) Full gradient/multi-hue
- d) Monochrome + one accent that changes per scene

**Q32. Grade intensity — backgrounds are currently darkened to ~0.6–0.76 brightness for text contrast:**
- a) Let the photo be brighter/more colorful, solve contrast with plates behind text
- b) Current balance is right ← now
- c) Darker / moodier

**Q33. Should color shift ACROSS a video?** (e.g. cool at the problem, warm at the payoff)
- a) Yes — a deliberate color arc
- b) Subtle drift only
- c) No, one palette per video ← now

---

## §10 — Sound & sync

**Q34. Should visuals sync to the music beat?**
- a) Yes — cuts land on the beat
- b) Only accents pulse to the beat, cuts stay free
- c) No — sync to the voiceover instead (cut on sentence ends)
- d) No sync ← roughly now

**Q35. Whooshes / SFX on transitions (currently ~2-3 loud cuts per video get one):**
- a) More
- b) About right ← now
- c) Fewer
- d) None

---

## §11 — Free text

**Hard NOs** — effects that must never appear, no matter what the seed rolls:

**References** — any account, video, or still whose motion/graphics you want to steal from:

**Anything else** you've noticed watching your own output that bugs you:
