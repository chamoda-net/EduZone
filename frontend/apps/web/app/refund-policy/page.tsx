import { StaticPage, staticMetadata } from "@/components/static-page";

export const metadata = staticMetadata("static.refunds.title");

export default function RefundPolicyPage() {
  return <StaticPage title="static.refunds.title" sections={[["static.refunds.whenH", "static.refunds.when"], ["static.refunds.howH", "static.refunds.how"]]} />;
}
