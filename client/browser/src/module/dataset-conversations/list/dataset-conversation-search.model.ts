import { z } from "zod";

export const explorerSearchSchema = z.object({
  q: z.string().catch(""),
  split: z.string().min(1).catch("all"),
  page: z.coerce.number().int().positive().catch(1),
});

export type ExplorerSearch = z.infer<typeof explorerSearchSchema>;
