import { StaticPage, staticMetadata } from "@/components/static-page";

export const metadata = staticMetadata("static.privacy.title");

export default function PrivacyPage() {
  return <StaticPage title="static.privacy.title" sections={[["static.privacy.collectH", "static.privacy.collect"], ["static.privacy.useH", "static.privacy.use"], ["static.privacy.paymentsH", "static.privacy.payments"]]} />;
}
