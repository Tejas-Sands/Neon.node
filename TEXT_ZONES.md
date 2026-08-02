# Text-zone inventory — contrast substrates

Generated 2026-07-26 by a six-way parallel source sweep of every component that draws text
over the graded media. **This is the gate on raising photo brightness (Q32).**

A brightness lift is GLOBAL — it brightens the photo behind every surface below, while only
the plated ones can be compensated by thickening a plate. Any surface listed as `none`,
`shadow-only` or `scrim-only` regresses unless it is given a substrate first.

Background is usually MOVING STOCK VIDEO (`SCENE_VIDEO_MODE` defaults to `all` in `main.py:147`),
so no surface may assume a calm or dark backdrop. Worst case is a blown-out white frame.


**103 distinct surfaces** — critical 27, high 15, medium 31, low 30.

Substrates: {'shadow-only': 12, 'none': 22, 'alpha-plate': 59, 'scrim-only': 4, 'blend-mode': 1, 'solid-plate': 5}


> `shadow-only` is **not** a pass. `ft.textGlow()` returns the literal string `"none"` on the
> `glass` and `print` finishes (`looks.ts:339`, `:349`), so surfaces relying on it have zero
> protection on half the finish catalogue.


## CRITICAL (27)

### HUD vhs-glitch — "PLAY ▶"

- **at** `src/remotion/MyComp/HudOverlay.tsx:238` — scenes: whole video whenever activeTheme.overlayType === "vhs-glitch"
- **colour** `"#fff"`
- **substrate** `shadow-only` — textShadow: `2px 0 0 ${secondaryColor}, -2px 0 0 ${primaryColor}` — a CHROMATIC-ABERRATION offset in two brand hues, zero blur, zero black. It provides no darkening whatsoever; on a bright frame it just smears two more light-ish colors around the glyph. No plate, no scrim (top of frame).
- Text node HudOverlay.tsx:239. The only thing under it is the CRT scanline layer (HudOverlay.tsx:173-183, `linear-gradient(rgba(0,0,0,0.2) 50%, rgba(255,255,255,0.03) 50%)` at 4px pitch) — that averages roughly 10% darkening across the frame, which is not a sub

### HUD vhs-glitch — timecode readout ("00:12:07")

- **at** `src/remotion/MyComp/HudOverlay.tsx:240` — scenes: whole video whenever overlayType === "vhs-glitch"
- **colour** `"#fff" inherited from HudOverlay.tsx:238`
- **substrate** `shadow-only` — Inherits the chromatic textShadow from its parent at HudOverlay.tsx:238 (textShadow IS a CSS-inherited property). Same non-darkening two-hue offset. No plate, no scrim.
- Text node HudOverlay.tsx:241. Smallest white glyphs in the whole area (10px at 0.8 alpha) sitting in the completely unprotected top band. Worst readability-per-pixel of any surface here.

### HUD vhs-glitch — "CH 04"

- **at** `src/remotion/MyComp/HudOverlay.tsx:244` — scenes: whole video whenever overlayType === "vhs-glitch"
- **colour** `"#fff"`
- **substrate** `none` — Literally nothing: no background, no textShadow (unlike its left-hand sibling at :238 it declares no shadow at all), no scrim at this height.
- Text node HudOverlay.tsx:245. Highest-risk category — pure white 12px glyphs with zero substrate of any kind, top-right corner. Relies 100% on the photo being crushed dark.

### HUD vhs-glitch — "REC" indicator label

- **at** `src/remotion/MyComp/HudOverlay.tsx:250` — scenes: whole video whenever overlayType === "vhs-glitch"
- **colour** `"#fff"`
- **substrate** `none` — No background, no textShadow, no scrim. The sibling red dot at HudOverlay.tsx:249 has a boxShadow glow but that is a separate element and does not back the label.
- Same exposure as CH 04 but dimmer (0.7 alpha at 11px). If the vhs-glitch HUD is kept after the brightness lift, all four of its top-band readouts (:239, :241, :245, :250) need one shared dark chip — they are clustered in the same top:50px strip and could share

### LowerThird component — RESOLVED 2026-08-02 (finish/palette integration)

- **at** `src/remotion/MyComp/LowerThird.tsx` — scenes: all LowerThird usages
- **substrate** `alpha-plate` — LowerThirdProps now accepts optional `palette` + `finish`; all three Main.tsx call sites pass them. accent-bar panel = `ft.panelBg(palette)` + `ft.panelBorder` + `ft.radiusPanel` + `ft.panelShadow`; news-ticker bar = `withAlpha(palette.ink, 0.78)`; minimal gains its own ink plate `withAlpha(palette.ink, 0.55)` at `ft.radiusChip`. Accent-coloured subtitles pass through `clampAccentLuminance`. Props absent = legacy hardcoded dressing byte-for-byte (old fixtures unaffected).
- (Historical: this was the STRUCTURAL BLOCKER row — the component took no look inputs at all.)

### cta — bare subtitle fallback (no ctaText, no button copy)

- **at** `src/remotion/MyComp/Main.tsx:1292` — scenes: cta (only when `subtitle && !ctaText`)
- **colour** `color: "rgba(255,255,255,0.6)"`
- **substrate** `none` — No background, no border, no textShadow, no glow — the div is literally { fontSize, color, textAlign } (Main.tsx:1292).
- Element 1291-1295. Completely naked 60%-alpha white in the mid-frame. Rarely hit (needs subtitle present and ctaText absent) but when hit it is unreadable the moment the plate-free backdrop brightens.

### Outro @handle line — RESOLVED 2026-08-02 (brand card rework)

- **at** `src/remotion/MyComp/Main.tsx` outro renderer — scenes: outro
- **substrate** `alpha-plate` — the handle now sits in its own pill (`withAlpha(palette.ink, 0.7)` + hairline `palette.edge` border, BRAND chrome face), and the whole outro stack (kicker + logo + name + handle) lives inside one finish-aware card (`ft.panelBg/panelBorder/radiusPanel/panelShadow`). The old coloured-glow-only monospace line is gone.

### Data-scene heading — gradient-fill treatment variant (PLATE IS CLIPPED AWAY)

- **at** `src/remotion/MyComp/Main.tsx:1495` — scenes: bar-chart, chart, line-chart, rating — when look.titleTreatment === "gradient-fi
- **colour** `backgroundImage: `linear-gradient(135deg, #ffffff 20%, ${glowColor})` with WebkitBackgroundClip/backgroundClip: "text", color: "transparent", textShad`
- **substrate** `none` — NONE in practice: decorationStyle sets backgroundColor rgba(0,0,0,0.55), but treatmentStyle then sets background-clip:text on the same element (AnimatedText.tsx:638-642 merges decoration then treatment), which clips the background PAINTING AREA — colour and image alike — to the glyphs. The dark plate stops existing and
- Highest-value finding in this range. A gradient that starts at #ffffff, no shadow, no plate, sitting mid-frame above the scrim. This is a cross-cutting AnimatedText defect (same code path serves lines 704, 842, 951, 1033, 1233, 1495, 1795), so fixing it once a

### Data-scene caption (subtitle under the panel)

- **at** `src/remotion/MyComp/Main.tsx:1529` — scenes: bar-chart, chart, line-chart, rating (rating also falls back to `text` here, Mai
- **colour** `"rgba(255,255,255,0.8)" (style at Main.tsx:1518-1527)`
- **substrate** `shadow-only` — textShadow: "0 2px 10px rgba(0,0,0,0.7)" only. No backgroundColor, no border, no panel — it is deliberately OUTSIDE the GlassCard (sibling after it at 1516).
- Every chart scene carries a full sentence here with nothing but a 10px black blur behind it. Its neighbours (the chart itself) all sit on a real panel, so the caption is the odd one out — the obvious fix is extending the panel or giving the caption its own chi

### Split-fallback main text (AnimatedText) — gradient-fill branch (PLATE CLIPPED AWAY)

- **at** `src/remotion/MyComp/Main.tsx:1795` — scenes: split — when look.titleTreatment === "gradient-fill" (1 of 4 seeds) and the anim
- **colour** `treatment={titleTreatment === "gradient-fill" ? "gradient-fill" : "solid"} => backgroundImage `linear-gradient(135deg, #ffffff 20%, ${theme.primaryCol`
- **substrate** `none` — NONE: background-clip:text clips the decorationStyle backgroundColor to the glyphs, and the treatment explicitly sets textShadow:"none". Nothing else is drawn behind this text.
- Same AnimatedText clipping defect as the data-scene heading zone, reached through an explicit ternary here. This is the scene type used as the catch-all fallback, so it renders often.

### karaoke style 6 (karaoke fill) — ACTIVE word, background-clip:text gradient (transparent glyphs)

- **at** `src/remotion/MyComp/Main.tsx:2203` — scenes: styleType 6 (the fallback `else` branch, i.e. ((seed>>>3)%7)===6)
- **colour** `color: "transparent" with backgroundImage `linear-gradient(90deg, ${theme.primaryColor} ${wp*100}%, rgba(255,255,255,0.38) ${wp*100}%)` + WebkitBackgr`
- **substrate** `alpha-plate` — shared caption plate only, and textShadow is EXPLICITLY set to "none" (line 2207) because a shadow would render under transparent glyphs. So the not-yet-swept portion of the active word is 38%-alpha white with zero local protection.
- THE other high-risk variant the audit asked for: the sweep leaves the right-hand part of the currently-spoken word at rgba(255,255,255,0.38), no shadow, no pill — on a 0.45-alpha soft plate over a bright clip the un-swept half of the live word disappears mid-r

### stat-token accent override (numbers / % / $) in classic styles 0–4

- **at** `src/remotion/MyComp/Main.tsx:2219` — scenes: styleType 0,1,2,3,4 — not 5, not 6
- **colour** `isPast ? theme.secondaryColor : `${theme.secondaryColor}99` (0x99 = 60% alpha) — overwrites whatever colour the style branch chose (lines 2219-2223)`
- **substrate** `alpha-plate` — shared caption plate only. The override is colour-only and runs for `styleType <= 4 && !isActive && isStatToken(word.text)` (isStatToken = /[\d%$]/, line 1956); it does NOT add any shadow, pill or border, and it also strips no protection — but note it replaces the 40%-white with a 60%-alpha BRAND hue whose luminance is
- This is the surface that carries the numbers — the single most content-critical token in a caption — at 60% alpha of an arbitrary secondaryColor over the weakest plate. Pastel/light secondaries (the packs where p.surface mixing already washes out) will vanish 

### hero title — gradient-fill treatment variant (NO PLATE)

- **at** `src/remotion/MyComp/Main.tsx:704` — scenes: hero, including sceneIndex 0 (the scroll-stopping hook frame)
- **colour** ``linear-gradient(135deg, #ffffff 20%, ${glowColor})` painted via WebkitBackgroundClip/backgroundClip:"text" with color:"transparent" and textShadow:"n`
- **substrate** `none` — none — backgroundClip:"text" clips the decorationStyle backgroundColor rgba(0,0,0,0.55) to the glyph shapes, so the plate is never painted as a panel. textShadow is explicitly set to "none". All that survives is the neon accent side-bars (borderLeft/borderRight, glowColor) and the soft hero contact-shadow radial at Mai
- HIGHEST-RISK SURFACE IN THIS RANGE. treatment={titleTreatment} is passed at Main.tsx:704 and titleTreatment is a uniform pick of ["solid","outline","gradient-fill","boxed"] (looks.ts:182) → ~25% of all seeds. gradient-fill only applies when animResult.mode ===

### testimonial eyebrow / speaker line (raw div, `title`)

- **at** `src/remotion/MyComp/Main.tsx:779` — scenes: testimonial
- **colour** `color: theme.secondaryColor (raw style pack hex, frequently a light/pastel secondary) — NO textShadow, NO glow of any kind`
- **substrate** `none` — none — bare div inside the quote container at Main.tsx:778; the container carries only opacity/transform. Nearest scrim contribution at y≈57-62% is ~0.03-0.07 ink alpha, i.e. nothing.
- Zero protection of ANY kind — no plate, no shadow, no meaningful scrim. Uppercase 28px letterspaced accent-coloured text straight onto the moving clip. Already fragile on a bright shot today and guaranteed to be unreadable after a brightness lift. This is the 

### testimonial quote body (raw div, `text`, italic, left accent bar)

- **at** `src/remotion/MyComp/Main.tsx:781` — scenes: testimonial
- **colour** `color: "#fff" with textShadow "0 2px 16px rgba(0,0,0,0.8)"; borderLeft `4px solid ${theme.primaryColor}`; boxShadow `inset 4px 0 12px ${theme.primaryC`
- **substrate** `shadow-only` — only the blurred textShadow "0 2px 16px rgba(0,0,0,0.8)". The `boxShadow: inset 4px 0 12px ${theme.primaryColor}20` is a ~12% alpha accent glow on the left edge only — it is decorative, not a plate. Scrim at bottom:32% (y≈65-70%) is ~0.10-0.15 ink alpha.
- The longest body copy in the scene with only a soft black halo behind it. A blown-white clip graded at brightness(0.68) contrast(1.16) still renders ~180/255, giving white text ~2.1:1 before any lift — this is already marginal today and cannot survive a bright

### metric scene title — gradient-fill treatment variant (NO PLATE)

- **at** `src/remotion/MyComp/Main.tsx:842` — scenes: metric, whenever look.titleTreatment === "gradient-fill" (~25% of seeds, looks.t
- **colour** ``linear-gradient(135deg, #ffffff 20%, ${glowColor})` via backgroundClip:"text", color:"transparent", textShadow:"none" (AnimatedText.tsx:616-623)`
- **substrate** `none` — none — the plate backgroundColor is clipped to the glyphs by backgroundClip:"text"; and unlike the hero there is no contact-shadow radial in this scene, so there is literally nothing behind it.
- Same defect as the hero gradient-fill variant (Main.tsx:704) but strictly worse: the metric scene has no contact-shadow fallback. Fixing gradient-fill inside AnimatedText (an un-clipped wrapper plate) fixes both call sites at once.

### metric giant number (counted-up hero stat, raw div)

- **at** `src/remotion/MyComp/Main.tsx:868` — scenes: metric (numeric branch — whenever `text` parses as a leading number)
- **colour** `color: theme.primaryColor with textShadow: ft.textGlow(theme.primaryColor) — which is "none" for finish glass and print, "0 2px 12px rgba(0,0,0,0.5)" `
- **substrate** `none` — none — no plate. The only nearby geometry is the decorative rotating ring at Main.tsx:849-866, which is a `2px solid ${theme.primaryColor}25` circle inset -40px around the number: a thin 15%-alpha stroke, not a substrate. For finish glass/print the textShadow is literally "none".
- The single biggest unplated raw-text element in the range: a ~80-98px accent-coloured number at frame centre with, for two of the four finishes, no shadow at all. The neon finish makes it WORSE on a bright frame — a coloured outward glow adds light against lig

### metric giant number — numeric count-up variant

- **at** `src/remotion/MyComp/Main.tsx:875` — scenes: metric (rendered whenever text matches /^([\d][\d,.]*)(.*)$/, i.e. the normal ca
- **colour** `color: theme.primaryColor`
- **substrate** `none` — textShadow: ft.textGlow(theme.primaryColor) (Main.tsx:876) — and FINISH_TOKENS.textGlow returns literally "none" for finish "glass" (looks.ts:339) and "print" (looks.ts:349). So on 2 of 4 finishes there is ZERO protection; on "neon" it is a same-colour glow (looks.ts:359, adds no contrast against a bright frame) and on
- Element block is 867-886. The largest type in the scene, in a saturated brand hue, with no plate whatsoever. Raising background brightness makes this the first thing to disappear — especially light primaries (cyan/yellow packs) over a white-blown Pexels clip.

### metric label / caption (raw div, `secondaryText`)

- **at** `src/remotion/MyComp/Main.tsx:900` — scenes: metric
- **colour** `color: theme.secondaryColor with textShadow: ft.textGlow(theme.secondaryColor) — "none" for finish glass and print, "0 2px 12px rgba(0,0,0,0.5)" for s`
- **substrate** `none` — none — bare div, no plate, no border, no box. For glass/print finishes textShadow resolves to the string "none", i.e. absolutely zero protection.
- Small uppercase accent-coloured caption with no substrate — the same defect as the testimonial eyebrow at Main.tsx:779, and the same fix applies. At 26px it is well below the size where a bare colour-on-photo can hold up.

### countdown giant number — the dial readout

- **at** `src/remotion/MyComp/Main.tsx:988` — scenes: countdown
- **colour** `color: theme.primaryColor`
- **substrate** `none` — textShadow: ft.textGlow(theme.primaryColor) (Main.tsx:989) → "none" on glass/print. The 280px ring behind it is SVG with fill="none" (Main.tsx:968-980) — stroke-only arcs plus rgba(255,255,255,0.12) tick marks; the ring's interior is fully transparent, so the number sits directly on the moving clip.
- Element 982-998. Identical exposure to the metric number. The ring reads as a plate in mockups but has no fill — a solid or alpha disc inside r=126 would be the natural substrate here.

### PrismLayers GiantWord — oversized masked display word (DISABLED 2026-07-28 — prism gate hard-off in prism.ts)

- **at** `src/remotion/MyComp/PrismLayers.tsx:506` — scenes: hero scenes (Main.tsx:667) and outro/cta scenes (Main.tsx:1331), gated on `prism
- **colour** `"transparent" — the fill is `backgroundImage: linear-gradient(160deg, withAlpha(palette.primarySoft,0.9), withAlpha(palette.secondary,0.75)), url("${i`
- **substrate** `none` — No plate, no shadow, no scrim. zIndex 12, centered at top:40% — far above the bottom scrim's reach. It is a knockout of the SAME imagery it sits on.
- Text node PrismLayers.tsx:510. THE most brightness-coupled surface in the renderer, and it fails in the opposite direction from everything else. Its fill uses the RAW `imageUrl` (PrismLayers.tsx:500) — NOT the graded media — screen-blended toward palette color

### AnimatedBar — bar value count-up (right of the bar, with optional unit suffix)

- **at** `src/remotion/MyComp/VideoFX.tsx:216` — scenes: bar-chart (Main.tsx:1537-1551)
- **colour** ``color2` — the caller-resolved chart colour (VideoFX.tsx:210). From BarChart this is `colors[i]` = `palette(primaryColor, secondaryColor, rows.length)`
- **substrate** `shadow-only` — `textShadow: "0 0 10px ${color2}40"` (VideoFX.tsx:212) — this is a SAME-HUE GLOW at 25% alpha, not a dark shadow. It adds zero luminance separation from a bright backdrop; it actively makes the glyph bloom lighter. The wrapper div (VideoFX.tsx:205-215) has no background/padding/border.
- No palette/finish/plate access. This is the single worst chart-numeral case in the file: a saturated theme colour with a same-colour glow and no plate of its own. The `suffix` prop (units like %, k, ms) renders inside the same span, so the unit text inherits i

### DonutChart — centre giant percentage ("NN%")

- **at** `src/remotion/MyComp/VideoFX.tsx:347` — scenes: chart (donut/pie) — Main.tsx:1554-1569
- **colour** ``active.color` (VideoFX.tsx:346) = `colors[i % colors.length]` from `palette(primaryColor, secondaryColor, …)` (VideoFX.tsx:274, 287) — a saturated th`
- **substrate** `shadow-only` — `textShadow: "0 0 14px ${active.color}55"` (VideoFX.tsx:346) — a same-hue glow at 33% alpha. The overlay div (VideoFX.tsx:334-345) is `position:absolute; inset:0` with NO background. Critically, the donut HOLE is empty: the track circle (VideoFX.tsx:305) and all segment circles (VideoFX.tsx:316-329) are `fill="none"` s
- No palette/finish/plate access. The glyph is large (56px) which helps a little, but it is a saturated hue over a literally transparent hole, so the moving stock clip shows through the middle of the donut. Only the external 0.45-0.78 alpha GlassCard (Main.tsx:1

### DonutChart — centre segment name (uppercase label under the percentage)

- **at** `src/remotion/MyComp/VideoFX.tsx:350` — scenes: chart (donut/pie) — Main.tsx:1554-1569
- **colour** `"#fff" (hard-coded, VideoFX.tsx:349)`
- **substrate** `none` — NONE. The style object at VideoFX.tsx:349 sets fontSize, fontWeight, color, fontFamily, textTransform, letterSpacing, maxWidth, textAlign, lineHeight — and no textShadow, no background, no padding, no filter. It sits in the same empty donut hole as the percentage.
- No palette/finish/plate access. Highest-risk surface in the whole file: pure white 22px letter-spaced caps with literally zero self-protection, sitting over an empty SVG hole through which the Pexels/Pixabay clip is fully visible. Only mitigation anywhere is t

### LineChart — x-axis category labels under each data point (SVG <text>)

- **at** `src/remotion/MyComp/VideoFX.tsx:450` — scenes: line-chart — Main.tsx:1572-1586
- **colour** `fill="rgba(255,255,255,0.7)" (hard-coded, VideoFX.tsx:449) — only 70% opaque white`
- **substrate** `none` — NONE. The <text> element (VideoFX.tsx:449-451) carries only x/y/textAnchor/fill/fontSize/fontFamily — no filter, no drop-shadow, no <rect> backing plate, no stroke/paint-order halo. Its parent <g> (VideoFX.tsx:447) only sets opacity. The area-fill polygon (VideoFX.tsx:421-425) stops at baseY, and the labels are drawn a
- No palette/finish/plate access. 18px at 70% white with zero shadow is the most fragile small text in the file. ALSO NOTE THE ABSENCES: LineChart draws no y-axis labels, no gridline values and no per-point value numbers — the only other non-text mark near them 

### StarRating — numeric rating value (the numerator count-up, e.g. "4.8")

- **at** `src/remotion/MyComp/VideoFX.tsx:543` — scenes: rating — Main.tsx:1589-1606
- **colour** ``primaryColor` — the caller-resolved theme primary (VideoFX.tsx:542; Main.tsx:1598 passes theme.primaryColor)`
- **substrate** `shadow-only` — `textShadow: "0 0 14px ${primaryColor}50"` (VideoFX.tsx:542) — again a SAME-HUE glow (31% alpha), not a dark shadow. The wrapper div has no background, no padding, no border. The stars above it (VideoFX.tsx:519-540) are a separate flex row, never behind the number.
- No palette/finish/plate access. Saturated theme primary with a same-hue glow — identical failure mode to the AnimatedBar value. Only external protection is `ft.panelBg(palette)` on the GlassCard (Main.tsx:1511), weakest rgba(0,0,0,0.45).

### StarRating — denominator span (" / 5")

- **at** `src/remotion/MyComp/VideoFX.tsx:544` — scenes: rating — Main.tsx:1589-1606
- **colour** `"rgba(255,255,255,0.6)" (hard-coded, VideoFX.tsx:544) — only 60% opaque white`
- **substrate** `shadow-only` — The span itself declares NO textShadow — it only inherits the parent div's `textShadow: "0 0 14px ${primaryColor}50"` (VideoFX.tsx:542), i.e. a primary-coloured glow bleeding around 60%-white glyphs. No background, no padding, no plate of its own.
- No palette/finish/plate access. Distinct zone from the numerator: different colour (60% white vs theme primary), different size (26px vs 44px), and no shadow of its own. 60%-alpha white at 26px is the weakest colour value on the rating card and is the first th


## HIGH (15)

### LowerThird "minimal" — title

- **at** `src/remotion/MyComp/LowerThird.tsx:116` — scenes: testimonial scene only (Main.tsx:766, variant="minimal"); title is actually the 
- **colour** `"#ffffff"`
- **substrate** `shadow-only` — textShadow: `0 2px 20px rgba(0,0,0,0.8), 0 0 10px ${accentColor}40` (LowerThird.tsx:119). No panel, no plate, no background of any kind on the wrapper (LowerThird.tsx:102-111) or the text div.
- Text node at LowerThird.tsx:122. It DOES sit inside the Main.tsx bottom scrim (Main.tsx:551-561, height 45%, 5 stops of palette.ink). Interpolating that gradient at 16-18.3% from bottom gives only ~0.48-0.55 ink alpha — roughly half strength, not the 0.88 peak

### LowerThird "minimal" — subtitle

- **at** `src/remotion/MyComp/LowerThird.tsx:128` — scenes: minimal variant with a subtitle — currently UNREACHABLE: the one minimal call si
- **colour** `"rgba(255,255,255,0.7)"`
- **substrate** `scrim-only` — NOTHING of its own. The textShadow at LowerThird.tsx:119 is on the SIBLING title div, not on a shared parent, so it does not inherit. The only thing under it is the Main.tsx bottom scrim.
- Text node LowerThird.tsx:135. Dead today but live the moment anyone passes `subtitle` to the minimal variant. 70%-alpha white at 28px with zero own protection is the weakest LowerThird surface by construction. Scrim alpha at 16% from bottom ≈ 0.55 ink.

### comparison BEFORE — panel label ("BEFORE" / leftLabel)

- **at** `src/remotion/MyComp/Main.tsx:1051` — scenes: comparison
- **colour** `color: "rgba(255,255,255,0.55)" (spread over cmpLabelStyle)`
- **substrate** `alpha-plate` — Parent panel background: ft.panelBg(palette) (Main.tsx:1040) = glass → palette.surface = withAlpha(mixHex("#07080d", primaryDeep, 0.28), 0.62) (looks.ts:299/336); print → withAlpha(p.ink, 0.78) (looks.ts:346); neon → "rgba(0,0,0,0.55)" (looks.ts:356); soft → "rgba(0,0,0,0.45)" (looks.ts:366). CRITICALLY the whole panel
- Deliberately de-emphasised text (0.55 white) on a deliberately de-emphasised plate (×0.9 opacity) — the two dimming decisions multiply. Over a bright clip the soft-finish case composites to ~55% white behind ~50% white glyphs: effectively gone. The panel plate

### comparison BEFORE — panel body text

- **at** `src/remotion/MyComp/Main.tsx:1054` — scenes: comparison
- **colour** `color: "rgba(255,255,255,0.85)"`
- **substrate** `alpha-plate` — Same panel as the BEFORE label: background ft.panelBg(palette) (Main.tsx:1040) + backdropFilter blur(12px) + border ft.panelBorder(palette), all under opacity: slideInLeft * 0.9 (Main.tsx:1046). Effective plate alpha 0.40-0.70 depending on finish; no textShadow of any kind on this div.
- Carries the actual 'before' claim — the most content-bearing text in the scene — at 0.85 white × 0.9 opacity with zero text shadow.

### Outro prism GiantWord (masked display word behind the logo stack) (DISABLED 2026-07-28 — prism gate hard-off)

- **at** `src/remotion/MyComp/Main.tsx:1330` — scenes: outro, only when prismBase > 0 && prism.giantWord
- **colour** `color: "transparent" + backgroundImage: `linear-gradient(160deg, withAlpha(palette.primarySoft,0.9), withAlpha(palette.secondary,0.75)), url(imageUrl)`
- **substrate** `blend-mode` — none behind it; the glyph fill IS the photo screen-blended with brand colors (PrismLayers.tsx:500-506), sitting at zIndex 12 directly over BackgroundLayer
- Screen-blend of the photo into the letterforms: as the plate brightens the word washes toward the surrounding frame and the 1px 35%-alpha stroke is all that separates it. Decorative, but it is a text surface and it degrades monotonically with background bright

### Data-scene heading — outline treatment variant

- **at** `src/remotion/MyComp/Main.tsx:1495` — scenes: bar-chart, chart, line-chart, rating — only when look.titleTreatment === "outlin
- **colour** `color: "transparent" with WebkitTextStroke: "2px #ffffff", textShadow: `0 0 18px ${glowColor}88` (AnimatedText.tsx:610-615)`
- **substrate** `alpha-plate` — decorationStyle backgroundColor survives (rgba(0,0,0,0.55) / 0.72 print / 0.8 vhs) — but the glyph interior is transparent, so the plate is what shows THROUGH the letters
- Hollow letters: the reading contrast is 2px white stroke vs the plate colour. Brighten the photo and the 0.55-alpha plate lifts toward mid-grey, at which point a white hairline stroke on grey is close to illegible. Needs an opaque plate, not a darker glow.

### lead-in preview words (dim pre-roll, 8 frames before a phrase)

- **at** `src/remotion/MyComp/Main.tsx:2011` — scenes: all styles EXCEPT styleType 5 (line 1988 `if (styleType === 5) return null;`)
- **colour** `color: "rgba(255, 255, 255, 0.4)" — but the whole box (plate + text) is multiplied by leadOpacity which ramps 0 → 0.35 (line 1997-2002, applied at 200`
- **substrate** `alpha-plate` — the shared plate — but at `opacity: leadOpacity` (max 0.35), so effective plate alpha is only 0.35 × 0.45–0.78 = 0.16–0.27, and effective text alpha is 0.4 × 0.35 = 0.14 white
- Effective ~14% white over an effective ~16–27% plate. Already the faintest surface in the file; on a bright frame it is completely gone (or reads as a grey smear). Harm is limited because it is a decorative ghost preview — but if the plate is strengthened, str

### karaoke style 0 (bounce highlight) — UPCOMING (unspoken) words

- **at** `src/remotion/MyComp/Main.tsx:2110` — scenes: styleType 0
- **colour** `"rgba(255, 255, 255, 0.4)"`
- **substrate** `alpha-plate` — shared caption plate only; textShadow "none" for non-active words
- 40%-alpha white. Over a soft-finish plate on a blown-out clip the text and the plate interior converge (≈186 vs ≈140 luminance, ~1.5:1) → unreadable. Every classic style carries this same dimmed-upcoming pattern; they are the single biggest regression class.

### karaoke style 3 (minimalist grow & lift) — ACTIVE word (NO shadow, NO pill, NO underline)

- **at** `src/remotion/MyComp/Main.tsx:2153` — scenes: styleType 3
- **colour** `theme.primaryColor`
- **substrate** `alpha-plate` — shared caption plate ONLY — style 3's wordStyle (lines 2152-2158) sets only color, fontSize and transform: there is no textShadow, no backgroundColor, no border of any kind
- The most naked of the classic styles: every glyph's readability is 100% delegated to the shared plate. Arbitrary brand primaryColor (which can be a light yellow/cyan/pastel) with zero shadow over a plate that may be only 45% black.

### karaoke style 6 (karaoke fill) — PAST words

- **at** `src/remotion/MyComp/Main.tsx:2212` — scenes: styleType 6
- **colour** `theme.primaryColor (note: style 6 is the only style whose PAST words are brand-coloured rather than white)`
- **substrate** `alpha-plate` — shared caption plate only; no shadow, no pill, no border in this branch (lines 2210-2213)
- An arbitrary brand hex at 100% alpha with zero local substrate. Light primaries (yellow/lime/pastel packs) already sit near the plate's interior luminance; a brightness lift pushes them past it.

### GiantWord — oversized prism hook word (media masked through letterforms) (DISABLED 2026-07-28 — prism gate hard-off)

- **at** `src/remotion/MyComp/Main.tsx:667` — scenes: hero scenes where prismSceneStrength > 0 AND prism.giantWord is set (Main.tsx:66
- **colour** `color: "transparent" with the fill supplied by `linear-gradient(160deg, ${withAlpha(palette.primarySoft, 0.9)} 0%, ${withAlpha(palette.secondary, 0.75`
- **substrate** `none` — none — no plate, no textShadow. The only separation is the 1px 35%-alpha stroke and the fact that the screen-blended fill is brighter than the graded backdrop. It sits at zIndex 12, UNDER both the contact shadow (19) and the title stack (20), so it gets no help from either.
- This surface's contrast is DEFINED by the brightness delta between the (ungraded) still used as its fill and the graded backdrop around it. Its background-image uses raw `imageUrl` with no imgFilter, so raising the backdrop brightness closes that gap directly 

### testimonial attribution — LowerThird variant="minimal" title

- **at** `src/remotion/MyComp/Main.tsx:766` — scenes: testimonial (only when subtitle is present)
- **colour** `color: "#ffffff" with textShadow `0 2px 20px rgba(0,0,0,0.8), 0 0 10px ${accentColor}40` (LowerThird.tsx:112-123); accentColor = theme.primaryColor`
- **substrate** `scrim-only` — NO panel of its own — the "minimal" variant is a bare div (LowerThird.tsx:100-139); the accent-bar and news-ticker variants have panels (rgba(0,0,0,0.5) / rgba(0,0,0,0.75)) but minimal has none. Its only real substrate is the Main.tsx:551-561 bottom scrim, which at bottom:16% (y≈82%) is ~0.49 ink alpha. Plus the weak t
- The least-bad of the unplated surfaces because it genuinely sits in the scrim band, but 0.49 alpha over a blown-white clip still only lands at ~135/255 → white 36px text at ~3.8:1 with no plate. It is also the ONLY LowerThird variant with no panel, so switchin

### Scene counter badge — "/ 05" total

- **at** `src/remotion/MyComp/SceneImpactFrame.tsx:214` — scenes: same as the index number (look.showSceneCounter)
- **colour** `"rgba(255,255,255,0.4)"`
- **substrate** `alpha-plate` — Same rgba(0,0,0,0.55) + blur(12px) chip (SceneImpactFrame.tsx:187-197). No shadow, no own background.
- Text node SceneImpactFrame.tsx:218. WEAKEST surface in SceneImpactFrame: 40%-alpha white at 18px. Measured against the chip today (grade 0.7, blown-white clip): chip ≈80, glyph ≈150 → ~2.96:1, already sub-AA. Lift the grade to ~1.0 and it becomes chip ≈115, gl

### CountUp — bare number span (primitive)

- **at** `src/remotion/MyComp/VideoFX.tsx:116` — scenes: internal to bar-chart (via AnimatedBar) and rating (via StarRating); also export
- **colour** `none set by the component; colour is 100% inherited from the caller's `style` prop (VideoFX.tsx:96/116 `...style`)`
- **substrate** `none` — none — the span sets only `fontVariantNumeric: "tabular-nums"`; no textShadow, no background, no padding, no plate
- Zero palette/finish/plate access. The primitive itself draws naked text; whatever protection exists is entirely whatever the two internal call sites (VideoFX.tsx:216 and VideoFX.tsx:543) or a future external caller wrap around it. No current external importer:

### AnimatedBar — row category label (left of the bar)

- **at** `src/remotion/MyComp/VideoFX.tsx:179` — scenes: bar-chart (Main.tsx:1537-1551 → BarChart → AnimatedBar)
- **colour** `"#fff" (hard-coded, VideoFX.tsx:171)`
- **substrate** `shadow-only` — `textShadow: "0 1px 6px rgba(0,0,0,0.6)"` (VideoFX.tsx:176) — a 6px-blur dark shadow, the only self-drawn protection. The div (style block VideoFX.tsx:165-177) has no background, no padding, no border. The bar track at VideoFX.tsx:181-191 is a SIBLING flex child, so it is beside the label, never behind it.
- No palette/finish/plate access — colour is a literal "#fff", not `palette.text`. Real substrate is external only: DataSceneShell's GlassCard `background: ft.panelBg(palette)` (Main.tsx:1511), weakest case rgba(0,0,0,0.45) on the `soft` finish (looks.ts:366). W


## MEDIUM / LOW

| risk | surface | at | substrate |
|---|---|---|---|
| medium | LowerThird "accent-bar" — title (default variant) | `src/remotion/MyComp/LowerThird.tsx:262` | alpha-plate |
| medium | split — LowerThird subtitle (accent-coloured kicker) | `src/remotion/MyComp/LowerThird.tsx:274` | alpha-plate |
| medium | comparison AFTER — panel label ("AFTER" / rightLabel) | `src/remotion/MyComp/Main.tsx:1088` | alpha-plate |
| medium | comparison AFTER — panel body text | `src/remotion/MyComp/Main.tsx:1091` | alpha-plate |
| medium | list — item index numeral inside the circular chip | `src/remotion/MyComp/Main.tsx:1175` | alpha-plate |
| medium | list — item body text | `src/remotion/MyComp/Main.tsx:1177` | alpha-plate |
| medium | Outro brand name / title (AnimatedText, 54px) | `src/remotion/MyComp/Main.tsx:1423` | alpha-plate |
| medium | Data-scene heading — solid / boxed treatment | `src/remotion/MyComp/Main.tsx:1486` | alpha-plate |
| medium | Chart panel plate (GlassCard) — the substrate every chart-internal lab | `src/remotion/MyComp/Main.tsx:1502` | alpha-plate |
| medium | Bar chart row labels + value counters | `src/remotion/MyComp/Main.tsx:1542` | alpha-plate |
| medium | Donut chart centre percentage + segment label | `src/remotion/MyComp/Main.tsx:1560` | alpha-plate |
| medium | Line chart x-axis point labels | `src/remotion/MyComp/Main.tsx:1577` | alpha-plate |
| medium | Star rating value + "/ max" | `src/remotion/MyComp/Main.tsx:1595` | alpha-plate |
| medium | split — secondaryText badge | `src/remotion/MyComp/Main.tsx:1818` | alpha-plate |
| medium | Split-fallback secondaryText chip | `src/remotion/MyComp/Main.tsx:1830` | alpha-plate |
| medium | caption plate opacity envelope (plate is weakest exactly at phrase in/ | `src/remotion/MyComp/Main.tsx:2053` | alpha-plate |
| medium | karaoke style 5 — SHARED CAPTION PLATE IS STRIPPED (boxOverride) | `src/remotion/MyComp/Main.tsx:2073` | none |
| medium | karaoke style 0 (bounce highlight) — ACTIVE word | `src/remotion/MyComp/Main.tsx:2106` | alpha-plate |
| medium | karaoke style 0 (bounce highlight) — PAST (already-spoken) words | `src/remotion/MyComp/Main.tsx:2109` | alpha-plate |
| medium | karaoke style 1 (pill) — PAST words (pill removed, transparent backgro | `src/remotion/MyComp/Main.tsx:2123` | alpha-plate |
| medium | karaoke style 2 (neon glow) — ACTIVE word | `src/remotion/MyComp/Main.tsx:2141` | shadow-only |
| medium | karaoke style 2 (neon glow) — PAST words | `src/remotion/MyComp/Main.tsx:2141` | alpha-plate |
| medium | karaoke style 4 (underline sweep) — ACTIVE + PAST words | `src/remotion/MyComp/Main.tsx:2164` | alpha-plate |
| medium | scene counter badge (SharedLayers → SceneImpactFrame) | `src/remotion/MyComp/Main.tsx:568` | alpha-plate |
| medium | hero title (AnimatedText) — solid / outline treatment | `src/remotion/MyComp/Main.tsx:692` | alpha-plate |
| medium | hero accent line (divider rule under the title) | `src/remotion/MyComp/Main.tsx:711` | none |
| medium | hero body text (AnimatedText) | `src/remotion/MyComp/Main.tsx:724` | alpha-plate |
| medium | hero subtitle (AnimatedText) | `src/remotion/MyComp/Main.tsx:729` | alpha-plate |
| medium | metric scene title (AnimatedText) — plated treatments | `src/remotion/MyComp/Main.tsx:833` | alpha-plate |
| medium | metric non-numeric fallback (AnimatedText) | `src/remotion/MyComp/Main.tsx:888` | alpha-plate |
| medium | Scene counter badge — index number ("02") | `src/remotion/MyComp/SceneImpactFrame.tsx:203` | alpha-plate |
| low | hero / metric title — boxed treatment variant | `src/remotion/MyComp/AnimatedText.tsx:624` | solid-plate |
| low | HUD grid-hud — telemetry readout ("SYS.OK — 003s") | `src/remotion/MyComp/HudOverlay.tsx:146` | scrim-only |
| low | LowerThird "news-ticker" — title | `src/remotion/MyComp/LowerThird.tsx:191` | alpha-plate |
| low | LowerThird "news-ticker" — subtitle | `src/remotion/MyComp/LowerThird.tsx:203` | alpha-plate |
| low | countdown — caption under the ring (AnimatedText) | `src/remotion/MyComp/Main.tsx:1001` | alpha-plate |
| low | comparison — scene title (AnimatedText) | `src/remotion/MyComp/Main.tsx:1033` | alpha-plate |
| low | list — LowerThird title (accent-bar variant) | `src/remotion/MyComp/Main.tsx:1115` | alpha-plate |
| low | cta — headline (AnimatedText) | `src/remotion/MyComp/Main.tsx:1224` | alpha-plate |
| low | cta — supporting line (AnimatedText) | `src/remotion/MyComp/Main.tsx:1239` | alpha-plate |
| low | cta — button label + arrow glyph | `src/remotion/MyComp/Main.tsx:1273` | solid-plate |
| low | outro — "FOLLOW FOR MORE" header (AnimatedText) | `src/remotion/MyComp/Main.tsx:1370` | alpha-plate |
| low | UI-demo window chrome URL pill | `src/remotion/MyComp/Main.tsx:1683` | alpha-plate |
| low | UI-demo TypingField typed query + placeholder + caret | `src/remotion/MyComp/Main.tsx:1689` | alpha-plate |
| low | UI-demo TypingField label ("PROMPT" / subtitle) | `src/remotion/MyComp/Main.tsx:1693` | alpha-plate |
| low | UI-demo result row text | `src/remotion/MyComp/Main.tsx:1720` | alpha-plate |
| low | UI-demo in-app CTA button label | `src/remotion/MyComp/Main.tsx:1744` | solid-plate |
| low | split — LowerThird title (accent-bar) | `src/remotion/MyComp/Main.tsx:1771` | alpha-plate |
| low | Split-fallback LowerThird subtitle | `src/remotion/MyComp/Main.tsx:1772` | alpha-plate |
| low | split — main body text (AnimatedText) | `src/remotion/MyComp/Main.tsx:1786` | alpha-plate |
| low | split — subtitle promoted to body when there is no title (AnimatedText | `src/remotion/MyComp/Main.tsx:1801` | alpha-plate |
| low | [reference] caption wrapper — vertical anchoring + z-order (not a text | `src/remotion/MyComp/Main.tsx:1843` | none |
| low | caption plate (shared box) — RETRO variant, theme.overlayType === "vhs | `src/remotion/MyComp/Main.tsx:1871` | alpha-plate |
| low | karaoke style 1 (pill / karaoke block) — ACTIVE word pill | `src/remotion/MyComp/Main.tsx:2124` | solid-plate |
| low | karaoke style 5 (spoken-word pop-in) — ACTIVE word pill | `src/remotion/MyComp/Main.tsx:2185` | solid-plate |
| low | karaoke style 5 (spoken-word pop-in) — already-spoken word pills | `src/remotion/MyComp/Main.tsx:2187` | alpha-plate |
| low | [reference] bottom scrim gradient — the ONLY global substrate under th | `src/remotion/MyComp/Main.tsx:558` | scrim-only |
| low | countdown — scene title (AnimatedText) | `src/remotion/MyComp/Main.tsx:951` | alpha-plate |
| low | TypingField — field label (uppercase caption above the input box) | `src/remotion/MyComp/VideoFX.tsx:839` | none |
| low | TypingField — typed query text (the value being typed, char-by-char) | `src/remotion/MyComp/VideoFX.tsx:855` | alpha-plate |
| low | TypingField — blinking caret glyph "▌" | `src/remotion/MyComp/VideoFX.tsx:856` | alpha-plate |

## Added 2026-08-02 (brand chrome pass)

| priority | surface | at | substrate |
|---|---|---|---|
| medium | Watermark chip (pipeline.watermark handle) | `src/remotion/MyComp/Main.tsx` watermark block | alpha-plate (`withAlpha(palette.ink, 0.72)` pill + edge border, BRAND face) |
| medium | Outro handle pill | `src/remotion/MyComp/Main.tsx` outro renderer | alpha-plate (`withAlpha(palette.ink, 0.7)` pill inside the finish-aware outro card) |
| medium | Outro kicker "FOLLOW FOR MORE" | `src/remotion/MyComp/Main.tsx` outro renderer | alpha-plate (sits on the outro card `ft.panelBg`) |
| medium | LowerThird minimal plate (when palette/finish passed) | `src/remotion/MyComp/LowerThird.tsx` minimal variant | alpha-plate (`withAlpha(palette.ink, 0.55)` at `ft.radiusChip`) |
| medium | Source-attribution chip "via {domain}" (scene 1 only) | `src/remotion/MyComp/Main.tsx` SharedLayers | alpha-plate (`withAlpha(palette.ink, 0.7)` + edge border, BRAND face) |
| low | vhs-glitch top-band readouts (PLAY/timecode/CH/REC) | `src/remotion/MyComp/HudOverlay.tsx` | alpha-plate (shared `rgba(8,10,14,0.6)` chips — closes 4 CRITICAL rows above) |
