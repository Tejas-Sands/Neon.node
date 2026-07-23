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
import {
  FONT_FAMILY,
  SafeZone,
  useSpringEntrance,
  CountUp,
  Icons,
} from "./videoCommons";

// ─── Demo Data ───────────────────────────────────────────────────────────────
const REPORT = {
  title: "AI Industry Report",
  year: "2024",
  source: "Global Tech Research Institute",
  bigNumber: 184,
  bigNumberPrefix: "$",
  bigNumberSuffix: "B",
  bigNumberLabel: "Global AI Market Size",
  barData: [
    { label: "Machine Learning", value: 38, color: "#2563eb" },
    { label: "NLP / LLMs", value: 27, color: "#7c3aed" },
    { label: "Computer Vision", value: 18, color: "#06b6d4" },
    { label: "Robotics & Auto", value: 11, color: "#f59e0b" },
    { label: "Other AI", value: 6, color: "#64748b" },
  ],
  donutData: [
    { label: "North America", value: 42, color: "#2563eb" },
    { label: "Asia Pacific", value: 31, color: "#7c3aed" },
    { label: "Europe", value: 19, color: "#06b6d4" },
    { label: "Rest of World", value: 8, color: "#f59e0b" },
  ],
  trendData: [12, 18, 29, 45, 67, 95, 128, 184],
  trendYears: ["2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024"],
  takeaways: [
    "AI spending grew 43% year-over-year",
    "LLM adoption doubled in enterprise",
    "75% of Fortune 500 now use AI tools",
  ],
};

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bg: "#f0f4f8",
  cardBg: "#ffffff",
  primary: "#2563eb",
  primaryLight: "#3b82f6",
  text: "#0f172a",
  textSecondary: "#64748b",
  border: "#e2e8f0",
  track: "#f1f5f9",
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 1 — Title Card (2.5s = 75 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene1Title: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    fps,
    frame,
    config: { damping: 13, stiffness: 110 },
  });
  const titleScale = interpolate(titleSpring, [0, 1], [0.8, 1]);

  const lineWidth = interpolate(frame, [15, 40], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const sourceOpacity = interpolate(frame, [30, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      {/* Decorative circles */}
      <div
        style={{
          position: "absolute",
          top: 100,
          right: -50,
          width: 300,
          height: 300,
          borderRadius: "50%",
          border: `2px solid ${C.primary}10`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 200,
          left: -80,
          width: 200,
          height: 200,
          borderRadius: "50%",
          background: `${C.primary}08`,
        }}
      />

      <SafeZone>
        {/* Year badge */}
        <div
          style={{
            backgroundColor: C.primary,
            color: "#fff",
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 28,
            padding: "8px 28px",
            borderRadius: 40,
            marginBottom: 30,
            opacity: titleSpring,
            transform: `scale(${titleScale})`,
          }}
        >
          {REPORT.year}
        </div>

        {/* Title */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 60,
            color: C.text,
            textAlign: "center",
            lineHeight: 1.15,
            transform: `scale(${titleScale})`,
            opacity: titleSpring,
          }}
        >
          {REPORT.title}
        </div>

        {/* Decorative line */}
        <div
          style={{
            width: `${lineWidth}%`,
            height: 4,
            backgroundColor: C.primary,
            borderRadius: 2,
            marginTop: 30,
          }}
        />

        {/* Source */}
        <div
          style={{
            marginTop: 24,
            fontFamily: FONT_FAMILY,
            fontWeight: 400,
            fontSize: 26,
            color: C.textSecondary,
            opacity: sourceOpacity,
            textAlign: "center",
          }}
        >
          {REPORT.source}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 2 — Big Number Reveal (3s = 90 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene2BigNumber: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const numSpring = spring({
    fps,
    frame,
    config: { damping: 15, stiffness: 90 },
  });
  const numScale = interpolate(numSpring, [0, 1], [0.5, 1]);

  const labelOpacity = interpolate(frame, [25, 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      {/* Decorative background chart lines */}
      <svg
        style={{ position: "absolute", inset: 0, opacity: 0.06 }}
        viewBox="0 0 1080 1920"
        fill="none"
      >
        <polyline
          points="60,1600 200,1400 400,1300 600,1100 800,800 1020,500"
          stroke={C.primary}
          strokeWidth="4"
          fill="none"
        />
        <polyline
          points="60,1650 250,1500 450,1450 650,1350 850,1200 1020,1000"
          stroke={C.primary}
          strokeWidth="2"
          fill="none"
        />
      </svg>

      <SafeZone>
        {/* Giant number */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 120,
            color: C.primary,
            textAlign: "center",
            transform: `scale(${numScale})`,
            opacity: numSpring,
          }}
        >
          <CountUp
            from={0}
            to={REPORT.bigNumber}
            startFrame={5}
            endFrame={55}
            prefix={REPORT.bigNumberPrefix}
            suffix={REPORT.bigNumberSuffix}
            style={{ fontFamily: FONT_FAMILY, fontWeight: 800 }}
          />
        </div>

        {/* Label */}
        <div
          style={{
            marginTop: 16,
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 36,
            color: C.text,
            opacity: labelOpacity,
            textAlign: "center",
          }}
        >
          {REPORT.bigNumberLabel}
        </div>

        {/* Trend arrow */}
        <div
          style={{
            marginTop: 20,
            display: "flex",
            alignItems: "center",
            gap: 10,
            opacity: labelOpacity,
          }}
        >
          {Icons.trendingUp(28, "#22c55e")}
          <span
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 28,
              color: "#22c55e",
            }}
          >
            +43% YoY
          </span>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 3 — Horizontal Bar Chart (4s = 120 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene3BarChart: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone style={{ justifyContent: "flex-start", paddingTop: 40 }}>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 40,
            color: C.text,
            marginBottom: 16,
            textAlign: "center",
            opacity: titleOpacity,
            width: "100%",
          }}
        >
          Market Breakdown
        </div>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 400,
            fontSize: 24,
            color: C.textSecondary,
            marginBottom: 50,
            textAlign: "center",
            opacity: titleOpacity,
          }}
        >
          by segment, % of total revenue
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 28,
            width: "100%",
          }}
        >
          {REPORT.barData.map((bar, i) => {
            const delay = 12 + i * 8;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 15, stiffness: 80 },
            });
            const barWidth = interpolate(s, [0, 1], [0, bar.value]);
            const countVal = Math.round(
              interpolate(frame, [delay + 5, delay + 40], [0, bar.value], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })
            );

            return (
              <div key={i} style={{ opacity: s }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 8,
                  }}
                >
                  <span
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 600,
                      fontSize: 26,
                      color: C.text,
                    }}
                  >
                    {bar.label}
                  </span>
                  <span
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 700,
                      fontSize: 26,
                      color: bar.color,
                    }}
                  >
                    {countVal}%
                  </span>
                </div>
                <div
                  style={{
                    width: "100%",
                    height: 20,
                    backgroundColor: C.track,
                    borderRadius: 10,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${barWidth}%`,
                      height: "100%",
                      backgroundColor: bar.color,
                      borderRadius: 10,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 4 — Donut Chart (3s = 90 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene4Donut: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const RADIUS = 120;
  const STROKE = 40;
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Calculate offsets for each segment
  let cumulativeOffset = 0;
  const segments = REPORT.donutData.map((seg, i) => {
    const segLength = (seg.value / 100) * CIRCUMFERENCE;
    const dashOffset = CIRCUMFERENCE - segLength;
    const rotation = (cumulativeOffset / 100) * 360 - 90;
    cumulativeOffset += seg.value;

    const delay = 10 + i * 10;
    const drawProgress = spring({
      fps,
      frame: Math.max(0, frame - delay),
      config: { damping: 20, stiffness: 60 },
    });
    const animatedDashOffset = interpolate(
      drawProgress,
      [0, 1],
      [CIRCUMFERENCE, dashOffset]
    );

    return { ...seg, segLength, animatedDashOffset, rotation, drawProgress };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 38,
            color: C.text,
            marginBottom: 40,
            textAlign: "center",
            opacity: titleOpacity,
          }}
        >
          Regional Market Share
        </div>

        {/* Donut SVG */}
        <svg width={300} height={300} viewBox="0 0 300 300">
          {segments.map((seg, i) => (
            <circle
              key={i}
              cx="150"
              cy="150"
              r={RADIUS}
              fill="none"
              stroke={seg.color}
              strokeWidth={STROKE}
              strokeDasharray={`${seg.segLength} ${CIRCUMFERENCE - seg.segLength}`}
              strokeDashoffset={seg.animatedDashOffset}
              transform={`rotate(${seg.rotation} 150 150)`}
              strokeLinecap="round"
            />
          ))}
        </svg>

        {/* Legend */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 16,
            marginTop: 40,
            width: "100%",
          }}
        >
          {REPORT.donutData.map((seg, i) => {
            const legendOpacity = interpolate(
              frame,
              [20 + i * 8, 35 + i * 8],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  opacity: legendOpacity,
                }}
              >
                <div
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 4,
                    backgroundColor: seg.color,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 600,
                    fontSize: 28,
                    color: C.text,
                    flex: 1,
                  }}
                >
                  {seg.label}
                </span>
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 700,
                    fontSize: 28,
                    color: seg.color,
                  }}
                >
                  {seg.value}%
                </span>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 5 — Line Chart / Trend (3.5s = 105 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene5LineChart: React.FC = () => {
  const frame = useCurrentFrame();

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Chart dimensions
  const chartW = 860;
  const chartH = 500;
  const padL = 80;
  const padR = 40;
  const padT = 40;
  const padB = 60;
  const plotW = chartW - padL - padR;
  const plotH = chartH - padT - padB;

  const maxVal = Math.max(...REPORT.trendData);
  const points = REPORT.trendData.map((val, i) => {
    const x = padL + (i / (REPORT.trendData.length - 1)) * plotW;
    const y = padT + plotH - (val / maxVal) * plotH;
    return { x, y, val };
  });

  const polylineStr = points.map((p) => `${p.x},${p.y}`).join(" ");

  // Approximate path length for stroke animation
  let pathLength = 0;
  for (let i = 1; i < points.length; i++) {
    pathLength += Math.sqrt(
      (points[i].x - points[i - 1].x) ** 2 +
        (points[i].y - points[i - 1].y) ** 2
    );
  }

  const drawProgress = interpolate(frame, [10, 70], [pathLength, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone style={{ justifyContent: "flex-start", paddingTop: 30 }}>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 38,
            color: C.text,
            marginBottom: 8,
            textAlign: "center",
            opacity: titleOpacity,
            width: "100%",
          }}
        >
          Growth Trend
        </div>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 400,
            fontSize: 24,
            color: C.textSecondary,
            marginBottom: 30,
            textAlign: "center",
            opacity: titleOpacity,
          }}
        >
          AI market size, 2017–2024 ($B)
        </div>

        <svg width={chartW} height={chartH}>
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((frac, i) => {
            const y = padT + plotH * (1 - frac);
            const label = Math.round(maxVal * frac);
            return (
              <g key={i}>
                <line
                  x1={padL}
                  y1={y}
                  x2={chartW - padR}
                  y2={y}
                  stroke={C.border}
                  strokeWidth={1}
                />
                <text
                  x={padL - 12}
                  y={y + 5}
                  textAnchor="end"
                  fill={C.textSecondary}
                  fontSize={20}
                  fontFamily={FONT_FAMILY}
                >
                  ${label}B
                </text>
              </g>
            );
          })}

          {/* X axis labels */}
          {points.map((p, i) => (
            <text
              key={i}
              x={p.x}
              y={chartH - 10}
              textAnchor="middle"
              fill={C.textSecondary}
              fontSize={18}
              fontFamily={FONT_FAMILY}
            >
              {REPORT.trendYears[i].slice(2)}
            </text>
          ))}

          {/* Area fill */}
          <polygon
            points={`${padL},${padT + plotH} ${polylineStr} ${
              points[points.length - 1].x
            },${padT + plotH}`}
            fill={`${C.primary}15`}
          />

          {/* Line */}
          <polyline
            points={polylineStr}
            fill="none"
            stroke={C.primary}
            strokeWidth={4}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={pathLength}
            strokeDashoffset={drawProgress}
          />

          {/* Data points */}
          {points.map((p, i) => {
            const dotDelay = 10 + (i / points.length) * 50;
            const dotOpacity = interpolate(
              frame,
              [dotDelay, dotDelay + 10],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={6}
                fill={C.primary}
                stroke="#fff"
                strokeWidth={3}
                opacity={dotOpacity}
              />
            );
          })}
        </svg>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 6 — Key Takeaways (2s = 60 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene6Takeaways: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 40,
            color: C.text,
            marginBottom: 50,
            textAlign: "center",
            opacity: interpolate(frame, [0, 12], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Key Takeaways
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 28,
            width: "100%",
          }}
        >
          {REPORT.takeaways.map((item, i) => {
            const delay = 8 + i * 10;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 14, stiffness: 100 },
            });
            const x = interpolate(s, [0, 1], [-40, 0]);

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  opacity: s,
                  transform: `translateX(${x}px)`,
                  backgroundColor: C.cardBg,
                  padding: "24px 28px",
                  borderRadius: 16,
                  border: `1px solid ${C.border}`,
                  boxShadow: "0 2px 12px rgba(0,0,0,0.04)",
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 12,
                    backgroundColor: `${C.primary}12`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {Icons.checkCircle(24, C.primary)}
                </div>
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 600,
                    fontSize: 30,
                    color: C.text,
                  }}
                >
                  {item}
                </span>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 7 — Source/CTA (2s = 60 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene7Source: React.FC = () => {
  const entrance = useSpringEntrance(0);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone>
        <div
          style={{
            transform: `scale(${entrance.scale})`,
            opacity: entrance.opacity,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 24,
          }}
        >
          {Icons.barChart(56, C.primary)}

          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 800,
              fontSize: 48,
              color: C.text,
              textAlign: "center",
            }}
          >
            {REPORT.title}
          </div>

          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 800,
              fontSize: 56,
              color: C.primary,
            }}
          >
            {REPORT.year}
          </div>

          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 400,
              fontSize: 26,
              color: C.textSecondary,
              textAlign: "center",
              marginTop: 16,
            }}
          >
            Source: {REPORT.source}
          </div>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═════════════════════════════════════════════════════════════════════════════
export const DataVizInfographic: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    <Series>
      <Series.Sequence durationInFrames={120} layout="none">
        <Scene1Title />
      </Series.Sequence>
      <Series.Sequence durationInFrames={120} layout="none">
        <Scene2BigNumber />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene3BarChart />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene4Donut />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene5LineChart />
      </Series.Sequence>
      <Series.Sequence durationInFrames={120} layout="none">
        <Scene6Takeaways />
      </Series.Sequence>
      <Series.Sequence durationInFrames={90} layout="none">
        <Scene7Source />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);
