/** The Contact form's topics (the API's `Topic`), in the order the chips show. */
export const TOPICS = ["payments", "account", "classes", "courses", "teaching", "institutes", "partnership", "other"] as const;
export type Topic = (typeof TOPICS)[number];
