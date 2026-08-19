import createClient from "openapi-fetch";
import type { paths } from "./openapi-schema";

export const openapiClient = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL || "/api",
});
