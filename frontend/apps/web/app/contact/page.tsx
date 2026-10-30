import { StaticPage, staticMetadata } from "@/components/static-page";

export const metadata = staticMetadata("static.contact.title");

export default function ContactPage() {
  return <StaticPage title="static.contact.title" sections={[["static.contact.studentsH", "static.contact.students"], ["static.contact.companyH", "static.contact.company"]]} />;
}
