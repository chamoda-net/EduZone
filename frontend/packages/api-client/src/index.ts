// Types generated from the backend's OpenAPI document (src/schema.ts; `npm run api-client`).
// The backend still declares some enums as plain strings, so hand-written types in
// @eduzone/lib/types move over here one screen at a time.
import type { components, operations, paths } from "./schema";

export type { components, operations, paths };
export type Schemas = components["schemas"];
export type Schema<Name extends keyof Schemas> = Schemas[Name];
