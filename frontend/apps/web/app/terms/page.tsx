import { StaticPage, staticMetadata } from "@/components/static-page";

export const metadata = staticMetadata("static.terms.title");

export default function TermsPage() {
  return <StaticPage title="static.terms.title" sections={[["static.terms.serviceH", "static.terms.service"], ["static.terms.paymentsH", "static.terms.payments"], ["static.terms.accountH", "static.terms.account"]]} />;
}
