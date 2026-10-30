import { redirect } from "next/navigation";

export default async function TeachHome({ params }: PageProps<"/teach/[tenant]">) {
  redirect(`/teach/${(await params).tenant}/classes`);
}
