import { StaticPage, staticMetadata } from "@/components/static-page";

export const metadata = staticMetadata("static.about.title");

export default function AboutPage() {
  return <StaticPage title="static.about.title" sections={[["static.about.whoH", "static.about.who"], ["static.about.howH", "static.about.how"]]} />;
}
