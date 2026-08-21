import { z } from "zod";

export const explorerSearchSchema = z.object({
  q: z.string().catch(""),
  split: z.string().min(1).catch("all"),
  page: z.coerce.number().int().positive().catch(1),
  tags: z.preprocess(
    (value) => (Array.isArray(value) ? value : typeof value === "string" ? [value] : []),
    z
      .array(z.string())
      .transform((values) =>
        [
          ...new Set(
            values
              .map((value) => value.trim())
              .filter((value) => value.length > 0 && value.length <= 100),
          ),
        ].slice(0, 50),
      )
      .catch([]),
  ),
});

export type ExplorerSearch = z.infer<typeof explorerSearchSchema>;
