import React from "react";
import {
  AbsoluteFill,
  Series,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

// ─── Font Loading ────────────────────────────────────────────────────────────
const interFont = loadFont("normal", {
  subsets: ["latin"],
  weights: ["400", "600", "700", "800"],
});

const FONT_FAMILY = interFont.fontFamily;

// ─── Business Data (from Sand AI website scrape) ─────────────────────────────
const BUSINESS = {
  name: "Sand AI",
  category: "Digital Marketing Agency",
  rating: 4.9,
  totalReviews: 127,
  location: "India",
  website: "www.sand-ai.com",
  ctaText: "Book a Call",
};

const REVIEWS = [
  {
    stars: 5,
    text: "Sand AI transformed our local business. Our Google Ads ROAS went from 2x to 7x in just three months. The dashboards are incredible.",
    name: "Rahul",
  },
  {
    stars: 5,
    text: "Finally a marketing team that actually understands data. They set up our CRM pipeline and now we never miss a lead. Highly recommend!",
    name: "Priya",
  },
  {
    stars: 5,
    text: "Their diagnostic approach found exactly where we were losing customers. Revenue is up 40% since we started working with them.",
    name: "Amit",
  },
];

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bg: "#f8f9fa",
  cardBg: "#ffffff",
  textPrimary: "#1a1a1a",
  textSecondary: "#64748b",
  gold: "#f59e0b",
  goldLight: "#fbbf24",
  border: "#e2e8f0",
  warmGradientStart: "#fff7ed",
  mutedGray: "#94a3b8",
  trackGray: "#f1f5f9",
};

// ─── Safe Zone Constants ─────────────────────────────────────────────────────
const SAFE = {
  top: 150,
  bottom: 170,
  side: 60,
};

// ─── SVG Components ──────────────────────────────────────────────────────────

/** Gold star SVG */
const StarSVG: React.FC<{
  size?: number;
  filled?: boolean;
  fillPercent?: number;
  color?: string;
}> = ({ size = 40, filled = true, fillPercent = 100, color = C.gold }) => {
  const id = `star-clip-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {fillPercent < 100 && (
        <defs>
          <clipPath id={id}>
            <rect x="0" y="0" width={`${(fillPercent / 100) * 24}`} height="24" />
          </clipPath>
        </defs>
      )}
      {/* Unfilled background star */}
      <path
        d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
        fill="#e2e8f0"
      />
      {/* Filled star */}
      <path
        d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
        fill={filled ? color : "none"}
        clipPath={fillPercent < 100 ? `url(#${id})` : undefined}
      />
    </svg>
  );
};

/** Star row component — renders n filled stars at a given size */
const StarRow: React.FC<{
  rating: number;
  size?: number;
  gap?: number;
}> = ({ rating, size = 40, gap = 4 }) => {
  return (
    <div style={{ display: "flex", gap, alignItems: "center" }}>
      {[1, 2, 3, 4, 5].map((i) => {
        const fillPercent =
          i <= Math.floor(rating)
            ? 100
            : i === Math.ceil(rating)
            ? (rating % 1) * 100
            : 0;
        return (
          <StarSVG
            key={i}
            size={size}
            filled={fillPercent > 0}
            fillPercent={fillPercent}
          />
        );
      })}
    </div>
  );
};

/** Google "G" logo (4-color SVG) */
const GoogleGLogo: React.FC<{ size?: number }> = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 48 48">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
  </svg>
);

/** People/Users icon SVG */
const PeopleIcon: React.FC<{ size?: number; color?: string }> = ({
  size = 28,
  color = C.gold,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

/** Map pin icon SVG */
const MapPinIcon: React.FC<{ size?: number; color?: string }> = ({
  size = 28,
  color = C.gold,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
    <circle cx="12" cy="10" r="3" />
  </svg>
);

/** Star icon for stat line */
const StarIcon: React.FC<{ size?: number; color?: string }> = ({
  size = 28,
  color = C.gold,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

/** Thumbs up icon */
const ThumbsUpIcon: React.FC<{ size?: number; color?: string }> = ({
  size = 48,
  color = C.gold,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
    <path d="M14.5 2.19a2 2 0 0 1 1.4.58l.1.1a2 2 0 0 1 .5 1.8L15 10h5.25a2 2 0 0 1 1.95 2.45l-1.85 8A2 2 0 0 1 18.4 22H7V11l3.5-8.5a1 1 0 0 1 .34-.31z" />
  </svg>
);

/** Large quotation mark SVG */
const QuoteMark: React.FC<{
  size?: number;
  color?: string;
  opacity?: number;
}> = ({ size = 200, color = C.gold, opacity = 0.1 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 100 100"
    fill={color}
    opacity={opacity}
  >
    <path d="M30 60c-8.3 0-15-6.7-15-15s6.7-15 15-15c2.8 0 5.4.8 7.6 2.1C35.2 22.4 27.5 15 18 15v-5c16.6 0 30 13.4 30 30v5c0 8.3-6.7 15-15 15h-3zm40 0c-8.3 0-15-6.7-15-15s6.7-15 15-15c2.8 0 5.4.8 7.6 2.1C75.2 22.4 67.5 15 58 15v-5c16.6 0 30 13.4 30 30v5c0 8.3-6.7 15-15 15h-3z" />
  </svg>
);

// ─── Utility: truncate text to max lines ─────────────────────────────────────
const truncateText = (text: string, maxChars: number): string => {
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars).trimEnd() + "...";
};

// ─── Safe Zone Wrapper ───────────────────────────────────────────────────────
const SafeZone: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ children, style }) => (
  <div
    style={{
      position: "absolute",
      top: SAFE.top,
      bottom: SAFE.bottom,
      left: SAFE.side,
      right: SAFE.side,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      ...style,
    }}
  >
    {children}
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// SCENE 1 — Hook (3 seconds = 90 frames)
// ═══════════════════════════════════════════════════════════════════════════════
const Scene1Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring animation for text entrance
  const textSpring = spring({
    fps,
    frame,
    config: { damping: 15, stiffness: 120, mass: 0.8 },
  });
  const textY = interpolate(textSpring, [0, 1], [40, 0]);
  const textOpacity = interpolate(textSpring, [0, 1], [0, 1]);

  // Stars fade in 10 frames after text
  const starsOpacity = interpolate(frame, [10, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${C.warmGradientStart} 0%, ${C.bg} 60%)`,
      }}
    >
      {/* Decorative gold star cluster (background) */}
      <div style={{ position: "absolute", top: 80, right: 40, opacity: 0.15 }}>
        <svg width="200" height="200" viewBox="0 0 200 200" fill={C.gold}>
          <path
            d="M60 20l5.15 10.44L77 32.12l-8.33 8.12 1.97 11.47L60 46.28l-10.64 5.43 1.97-11.47L43 32.12l11.85-1.68L60 20z"
            transform="rotate(-15 60 40)"
          />
          <path
            d="M140 50l7.73 15.66L165 68.18l-12.5 12.18 2.95 17.2L140 89.42l-15.45 8.14 2.95-17.2L115 68.18l17.27-2.52L140 50z"
            transform="rotate(10 140 70)"
          />
          <path
            d="M90 100l4.12 8.35L104 109.7l-6.67 6.5 1.58 9.18L90 120.62l-8.91 4.76 1.58-9.18L76 109.7l9.88-1.35L90 100z"
            transform="rotate(25 90 110)"
          />
        </svg>
      </div>

      <SafeZone>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
            transform: `translateY(${textY}px)`,
            opacity: textOpacity,
          }}
        >
          {/* Line 1 */}
          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 44,
              color: C.textPrimary,
              textAlign: "center",
              lineHeight: 1.2,
            }}
          >
            What people are saying about
          </div>
          {/* Line 2 — Business name in gold */}
          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 800,
              fontSize: 56,
              color: C.gold,
              textAlign: "center",
              lineHeight: 1.2,
            }}
          >
            {BUSINESS.name}
          </div>
        </div>

        {/* Star row + rating number */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginTop: 40,
            opacity: starsOpacity,
          }}
        >
          <StarRow rating={BUSINESS.rating} size={40} gap={6} />
          <span
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 44,
              color: C.textPrimary,
            }}
          >
            {BUSINESS.rating}
          </span>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// SCENE 2 — Star Rating Reveal (3 seconds = 90 frames)
// ═══════════════════════════════════════════════════════════════════════════════
const Scene2StarRating: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Each star fills in with spring, staggered by 8 frames
  const starScales = [0, 1, 2, 3, 4].map((i) => {
    const delay = i * 8;
    const localFrame = Math.max(0, frame - delay);
    return spring({
      fps,
      frame: localFrame,
      config: { damping: 12, stiffness: 150, mass: 0.6 },
    });
  });

  // Rating count-up animation
  const ratingCountEnd = 55; // frames
  const currentRating = interpolate(
    frame,
    [15, ratingCountEnd],
    [0, BUSINESS.rating],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    }
  );

  // Review count animation
  const reviewCount = Math.round(
    interpolate(frame, [25, 65], [0, BUSINESS.totalReviews], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    })
  );

  // "Based on X reviews" fade in
  const basedOnOpacity = interpolate(frame, [35, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      {/* Subtle gold shimmer behind stars */}
      <div
        style={{
          position: "absolute",
          top: "35%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: 500,
          height: 200,
          background: `radial-gradient(ellipse, ${C.gold}15 0%, transparent 70%)`,
          filter: "blur(30px)",
        }}
      />

      <SafeZone>
        {/* 5 large stars */}
        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {[0, 1, 2, 3, 4].map((i) => {
            const isLastStar = i === 4;
            const fillPercent = isLastStar
              ? (BUSINESS.rating % 1) * 100
              : 100;
            return (
              <div
                key={i}
                style={{
                  transform: `scale(${starScales[i]})`,
                  opacity: starScales[i],
                }}
              >
                <StarSVG
                  size={60}
                  filled={starScales[i] > 0.1}
                  fillPercent={
                    starScales[i] > 0.5 ? fillPercent : 0
                  }
                />
              </div>
            );
          })}
        </div>

        {/* Rating number counting up */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 80,
            color: C.textPrimary,
            marginTop: 40,
            textAlign: "center",
          }}
        >
          {currentRating.toFixed(1)}
        </div>

        {/* "Based on X reviews" */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 36,
            color: C.textSecondary,
            marginTop: 16,
            opacity: basedOnOpacity,
            textAlign: "center",
          }}
        >
          Based on {reviewCount} reviews
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// SCENE 3 — Review Carousel (9 seconds = 270 frames, 90 per review)
// ═══════════════════════════════════════════════════════════════════════════════

/** Single review card */
const ReviewCard: React.FC<{
  review: (typeof REVIEWS)[0];
  index: number;
}> = ({ review, index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const FRAMES_PER_REVIEW = 120;

  // Card entrance spring
  const enterSpring = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 100, mass: 0.7 },
  });
  const enterX = interpolate(enterSpring, [0, 1], [400, 0]);
  const enterOpacity = interpolate(enterSpring, [0, 1], [0, 1]);

  // Card exit (last 12 frames)
  const exitStart = FRAMES_PER_REVIEW - 12;
  const exitProgress = interpolate(
    frame,
    [exitStart, FRAMES_PER_REVIEW],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitX = interpolate(exitProgress, [0, 1], [0, -400]);
  const exitOpacity = interpolate(exitProgress, [0, 1], [1, 0]);

  const translateX = frame < exitStart ? enterX : exitX;
  const opacity = frame < exitStart ? enterOpacity : exitOpacity;

  // Decorative elements based on review index
  const renderDecorativeBelow = () => {
    if (index === 0) {
      // Rating bar chart
      const barData = [
        { label: "5★", percent: 78 },
        { label: "4★", percent: 15 },
        { label: "3★", percent: 5 },
        { label: "2★", percent: 1 },
        { label: "1★", percent: 1 },
      ];
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            width: "100%",
            maxWidth: 600,
            marginTop: 30,
            opacity: 0.45,
          }}
        >
          {barData.map((bar, bi) => {
            const barSpring = spring({
              fps,
              frame: Math.max(0, frame - 10 - bi * 5),
              config: { damping: 15, stiffness: 80 },
            });
            const barWidth = interpolate(barSpring, [0, 1], [0, bar.percent]);
            return (
              <div
                key={bi}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontSize: 24,
                    fontWeight: 600,
                    color: C.mutedGray,
                    width: 40,
                    textAlign: "right",
                  }}
                >
                  {bar.label}
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 14,
                    backgroundColor: C.trackGray,
                    borderRadius: 7,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${barWidth}%`,
                      height: "100%",
                      backgroundColor: C.gold,
                      borderRadius: 7,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    if (index === 1) {
      // Thumbs up + count
      const thumbSpring = spring({
        fps,
        frame: Math.max(0, frame - 8),
        config: { damping: 10, stiffness: 130 },
      });
      const thumbScale = interpolate(thumbSpring, [0, 1], [0.3, 1]);
      const countVal = Math.round(
        interpolate(frame, [15, 60], [0, BUSINESS.totalReviews], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      );
      return (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginTop: 40,
            opacity: 0.4,
          }}
        >
          <div style={{ transform: `scale(${thumbScale})` }}>
            <ThumbsUpIcon size={56} color={C.gold} />
          </div>
          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 40,
              color: C.mutedGray,
            }}
          >
            {countVal}+ reviews
          </div>
        </div>
      );
    }

    // index === 2: map pin + location
    const pinPulse = 1 + Math.sin(frame * 0.15) * 0.08;
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginTop: 40,
          opacity: 0.4,
        }}
      >
        <div style={{ transform: `scale(${pinPulse})` }}>
          <MapPinIcon size={48} color={C.gold} />
        </div>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 36,
            color: C.mutedGray,
          }}
        >
          {BUSINESS.location}
        </div>
      </div>
    );
  };

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone style={{ justifyContent: "flex-start", paddingTop: 40 }}>
        {/* Decorative quotation mark above card */}
        <div
          style={{
            position: "absolute",
            top: SAFE.top + 10,
            left: SAFE.side + 10,
            opacity: enterOpacity * 0.1,
          }}
        >
          <QuoteMark size={180} />
        </div>

        {/* Review card */}
        <div
          style={{
            transform: `translateX(${translateX}px)`,
            opacity,
            width: "100%",
            marginTop: 100,
          }}
        >
          <div
            style={{
              backgroundColor: C.cardBg,
              border: `1px solid ${C.border}`,
              borderRadius: 16,
              padding: "40px 36px",
              boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
              display: "flex",
              flexDirection: "column",
              gap: 24,
            }}
          >
            {/* Stars row */}
            <StarRow rating={review.stars} size={28} gap={4} />

            {/* Review text */}
            <div
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 400,
                fontSize: 36,
                color: C.textPrimary,
                lineHeight: 1.45,
                fontStyle: "italic",
              }}
            >
              "{truncateText(review.text, 150)}"
            </div>

            {/* Reviewer name + Google Review */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span
                style={{
                  fontFamily: FONT_FAMILY,
                  fontWeight: 600,
                  fontSize: 28,
                  color: C.textSecondary,
                }}
              >
                {review.name}
              </span>
              <span
                style={{
                  color: C.textSecondary,
                  fontSize: 28,
                  fontFamily: FONT_FAMILY,
                }}
              >
                •
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <GoogleGLogo size={20} />
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 400,
                    fontSize: 28,
                    color: C.textSecondary,
                  }}
                >
                  Google Review
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Progress dots */}
        <div
          style={{
            display: "flex",
            gap: 12,
            marginTop: 30,
            justifyContent: "center",
          }}
        >
          {[0, 1, 2].map((di) => (
            <div
              key={di}
              style={{
                width: di === index ? 32 : 10,
                height: 10,
                borderRadius: 5,
                backgroundColor: di === index ? C.gold : C.border,
                transition: "all 0.3s",
              }}
            />
          ))}
        </div>

        {/* Decorative element below card */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            opacity: enterOpacity,
          }}
        >
          {renderDecorativeBelow()}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

/** Scene 3 wraps 3 review cards in a Series */
const Scene3ReviewCarousel: React.FC = () => {
  const FRAMES_PER_REVIEW = 120;
  return (
    <Series>
      {REVIEWS.map((review, i) => (
        <Series.Sequence
          key={i}
          durationInFrames={FRAMES_PER_REVIEW}
          layout="none"
        >
          <ReviewCard review={review} index={i} />
        </Series.Sequence>
      ))}
    </Series>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// SCENE 4 — Social Proof Stack (3 seconds = 90 frames)
// ═══════════════════════════════════════════════════════════════════════════════
const Scene4SocialProof: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const lines = [
    {
      icon: <StarIcon size={36} color={C.gold} />,
      text: `${BUSINESS.rating} star rating`,
      countUp: false,
    },
    {
      icon: <PeopleIcon size={36} color={C.gold} />,
      text: `+ happy customers`,
      countUp: true,
      countTarget: BUSINESS.totalReviews,
    },
    {
      icon: <MapPinIcon size={36} color={C.gold} />,
      text: BUSINESS.location,
      countUp: false,
    },
  ];

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 48,
            width: "100%",
          }}
        >
          {lines.map((line, i) => {
            const delay = i * 10;
            const lineSpring = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 14, stiffness: 110, mass: 0.7 },
            });
            const lineY = interpolate(lineSpring, [0, 1], [50, 0]);
            const lineOpacity = interpolate(lineSpring, [0, 1], [0, 1]);

            let displayText = line.text;
            if (line.countUp && line.countTarget) {
              const countVal = Math.round(
                interpolate(
                  frame,
                  [delay + 5, delay + 50],
                  [0, line.countTarget],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: Easing.out(Easing.cubic),
                  }
                )
              );
              displayText = `${countVal}${line.text}`;
            }

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  transform: `translateY(${lineY}px)`,
                  opacity: lineOpacity,
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 16,
                    backgroundColor: `${C.gold}15`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {line.icon}
                </div>
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 700,
                    fontSize: 44,
                    color: C.textPrimary,
                  }}
                >
                  {displayText}
                </span>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// SCENE 5 — CTA (2 seconds = 60 frames)
// ═══════════════════════════════════════════════════════════════════════════════
const Scene5CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Business name scales in
  const nameSpring = spring({
    fps,
    frame,
    config: { damping: 13, stiffness: 120, mass: 0.6 },
  });
  const nameScale = interpolate(nameSpring, [0, 1], [0.7, 1]);
  const nameOpacity = interpolate(nameSpring, [0, 1], [0, 1]);

  // Button enters from below
  const btnSpring = spring({
    fps,
    frame: Math.max(0, frame - 8),
    config: { damping: 14, stiffness: 100, mass: 0.7 },
  });
  const btnY = interpolate(btnSpring, [0, 1], [60, 0]);
  const btnOpacity = interpolate(btnSpring, [0, 1], [0, 1]);

  // URL fades in
  const urlOpacity = interpolate(frame, [18, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone>
        {/* Business name */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 56,
            color: C.textPrimary,
            textAlign: "center",
            transform: `scale(${nameScale})`,
            opacity: nameOpacity,
          }}
        >
          {BUSINESS.name}
        </div>

        {/* CTA Button */}
        <div
          style={{
            marginTop: 50,
            width: "100%",
            transform: `translateY(${btnY}px)`,
            opacity: btnOpacity,
          }}
        >
          <div
            style={{
              width: "100%",
              height: 72,
              borderRadius: 16,
              backgroundColor: C.gold,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 700,
                fontSize: 40,
                color: "#ffffff",
                letterSpacing: 1,
              }}
            >
              {BUSINESS.ctaText}
            </span>
          </div>
        </div>

        {/* Website URL */}
        <div
          style={{
            marginTop: 24,
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 36,
            color: C.textSecondary,
            opacity: urlOpacity,
            textAlign: "center",
          }}
        >
          {BUSINESS.website}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN TESTIMONIAL VIDEO COMPOSITION
// ═══════════════════════════════════════════════════════════════════════════════
export const TestimonialVideo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Series>
        {/* Scene 1: Hook — 5s */}
        <Series.Sequence durationInFrames={150} layout="none">
          <Scene1Hook />
        </Series.Sequence>

        {/* Scene 2: Star Rating Reveal — 5s */}
        <Series.Sequence durationInFrames={150} layout="none">
          <Scene2StarRating />
        </Series.Sequence>

        {/* Scene 3: Review Carousel — 12s (3 reviews × 4s each) */}
        <Series.Sequence durationInFrames={360} layout="none">
          <Scene3ReviewCarousel />
        </Series.Sequence>

        {/* Scene 4: Social Proof Stack — 4s */}
        <Series.Sequence durationInFrames={120} layout="none">
          <Scene4SocialProof />
        </Series.Sequence>

        {/* Scene 5: CTA — 4s */}
        <Series.Sequence durationInFrames={120} layout="none">
          <Scene5CTA />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
