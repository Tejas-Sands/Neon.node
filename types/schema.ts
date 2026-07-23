import { z } from "zod";
import { CompositionProps } from "./constants";

export const RenderRequest = z.object({
  id: z.string(),
  inputProps: CompositionProps.optional(),
  prompt: z.string().optional(),
  text_gen_key: z.string().optional(),
  image_gen_key: z.string().optional(),
  text_api_base: z.string().optional(),
  text_model_name: z.string().optional(),
  image_api_base: z.string().optional(),
  image_model_name: z.string().optional(),
  image_urls: z.array(z.string()).optional(),
});

export type RenderResponse =
  | {
      type: "error";
      message: string;
    }
  | {
      type: "done";
      url: string;
      size: number;
    };

export type SSEMessage =
  | { type: "phase"; phase: string; progress: number; subtitle?: string }
  | { type: "done"; url: string; size: number }
  | { type: "error"; message: string };
