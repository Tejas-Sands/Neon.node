import { Composition, CalculateMetadataFunction, getRemotionEnvironment } from "remotion";
import { z } from "zod";
import {
  COMP_NAME,
  defaultMyCompProps,
  DURATION_IN_FRAMES,
  VIDEO_FPS,
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
  ASPECT_RATIO_MAP,
  CompositionProps,
  SCENERY_COMP_NAME,
  SceneryProps,
  defaultSceneryProps,
} from "../../types/constants";

// Only initialize Theatre.js studio in development mode and when not rendering
if (
  process.env.NODE_ENV !== "production" &&
  !getRemotionEnvironment().isRendering &&
  typeof window !== "undefined"
) {
  import("@theatre/studio")
    .then((studio) => {
      studio.default.initialize();
    })
    .catch((err) => {
      console.warn("Failed to initialize Theatre.js studio:", err);
    });
}

import { Main } from "./MyComp/Main";
import { ArtisticScenery } from "./Scenery/ArtisticScenery";
import { NextLogo } from "./MyComp/NextLogo";
import { TestimonialVideo } from "./TestimonialVideo";
import { AvatarOverlayVideo } from "./AvatarOverlayVideo";
import { DataVizInfographic } from "./DataVizInfographic";
import { ProductShowcase } from "./ProductShowcase";
import { ListicleVideo } from "./ListicleVideo";
import { EventPromoVideo } from "./EventPromoVideo";

// Scenery film: duration comes straight from props (long-take plan, decided
// by the backend) — there are no scenes whose frames could be summed.
const calculateSceneryMetadata: CalculateMetadataFunction<z.infer<typeof SceneryProps>> = async ({ props }) => {
  return {
    durationInFrames: Math.max(300, Math.min(600, Math.round(props.durationInFrames || 450))),
    width: 1080,
    height: 1920,
  };
};

const calculateMetadata: CalculateMetadataFunction<z.infer<typeof CompositionProps>> = async ({ props }) => {
  const totalFrames = props.scenes?.reduce((acc, scene) => acc + (scene.durationInFrames || 90), 0) || DURATION_IN_FRAMES;

  // Dynamic aspect ratio from theme props
  const aspectRatio = props.theme?.aspectRatio ?? "9:16";
  const dimensions = ASPECT_RATIO_MAP[aspectRatio] ?? ASPECT_RATIO_MAP["9:16"];

  return {
    durationInFrames: totalFrames,
    width: dimensions.width,
    height: dimensions.height,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id={COMP_NAME}
        component={Main}
        durationInFrames={DURATION_IN_FRAMES}
        fps={VIDEO_FPS}
        width={VIDEO_WIDTH}
        height={VIDEO_HEIGHT}
        defaultProps={defaultMyCompProps}
        calculateMetadata={calculateMetadata}
      />
      <Composition
        id={SCENERY_COMP_NAME}
        component={ArtisticScenery}
        durationInFrames={450}
        fps={VIDEO_FPS}
        width={VIDEO_WIDTH}
        height={VIDEO_HEIGHT}
        schema={SceneryProps}
        defaultProps={defaultSceneryProps}
        calculateMetadata={calculateSceneryMetadata}
      />
      <Composition
        id="NextLogo"
        component={NextLogo}
        durationInFrames={300}
        fps={30}
        width={140}
        height={140}
        defaultProps={{
          outProgress: 0,
        }}
      />
      <Composition
        id="TestimonialVideo"
        component={TestimonialVideo}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="AvatarOverlayVideo"
        component={AvatarOverlayVideo}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="DataVizInfographic"
        component={DataVizInfographic}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="ProductShowcase"
        component={ProductShowcase}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="ListicleVideo"
        component={ListicleVideo}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="EventPromoVideo"
        component={EventPromoVideo}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};
