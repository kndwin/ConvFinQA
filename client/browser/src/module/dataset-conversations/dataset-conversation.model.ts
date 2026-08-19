import type { components } from "@/platform/api/openapi-schema";
import { z } from "zod";

export const datasetConversationSchema: z.ZodType<
  components["schemas"]["DatasetConversationResponse"]
> = z.object({
  id: z.number().nullable(),
  source_id: z.string(),
  split: z.string(),
  pre_text: z.string(),
  post_text: z.string(),
  num_dialogue_turns: z.number().nullable(),
  has_type2_question: z.boolean().nullable(),
  has_duplicate_columns: z.boolean().nullable(),
  has_non_numeric_values: z.boolean().nullable(),
  features_json: z.string(),
  doc_json: z.string().nullable(),
  dialogue_json: z.string(),
  candidate_qa: z.array(z.object({ question: z.string(), answer: z.string().nullable() })),
});

export type DatasetConversation = z.infer<typeof datasetConversationSchema>;

export function datasetConversationKey(item: DatasetConversation) {
  return item.id == null ? `${item.source_id}:${item.split}` : String(item.id);
}
