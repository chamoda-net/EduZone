import { Fragment, type ReactNode } from "react";

/** A small, safe Markdown renderer for article lectures: headings, paragraphs, bold, italics, inline code, code
 * blocks, bullet and numbered lists, block quotes and links (http/https only). It builds React elements and never
 * injects HTML, so an instructor's text can't run scripts. */
export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      blocks.push(<pre key={i} className="overflow-x-auto rounded-ez bg-brand-950 p-4 font-mono text-sm text-brand-50">{code.join("\n")}</pre>);
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const cls = ["font-display text-3xl font-semibold", "font-display text-2xl font-semibold", "text-xl font-semibold", "text-lg font-semibold"][level - 1];
      const Tag = (["h2", "h3", "h4", "h5"] as const)[level - 1];
      blocks.push(<Tag key={i} className={cls}>{inline(heading[2])}</Tag>);
      i++;
      continue;
    }
    if (/^\s*([-*])\s+/.test(line) || /^\s*\d+[.)]\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: string[] = [];
      while (i < lines.length && (ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*]\s+/).test(lines[i])) {
        items.push(lines[i].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*]\s+/, ""));
        i++;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List key={i} className={ordered ? "list-decimal space-y-1.5 pl-6" : "list-disc space-y-1.5 pl-6"}>
          {items.map((it, n) => <li key={n}>{inline(it)}</li>)}
        </List>,
      );
      continue;
    }
    if (line.startsWith(">")) {
      const quote: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) quote.push(lines[i++].replace(/^>\s?/, ""));
      blocks.push(<blockquote key={i} className="border-l-4 border-gold pl-4 text-foreground/80 italic">{inline(quote.join(" "))}</blockquote>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|>|\s*[-*]\s|\s*\d+[.)]\s)/.test(lines[i])) para.push(lines[i++]);
    blocks.push(<p key={i}>{inline(para.join(" "))}</p>);
  }
  return <div className="flex flex-col gap-4 text-[1.0625rem] leading-relaxed text-foreground/90">{blocks}</div>;
}

const TOKEN = /(\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g;

function inline(text: string): ReactNode {
  return text.split(TOKEN).map((part, n) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <strong key={n}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return <code key={n} className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[0.9em]">{part.slice(1, -1)}</code>;
    }
    if ((part.startsWith("*") && part.endsWith("*") || part.startsWith("_") && part.endsWith("_")) && part.length > 2) {
      return <em key={n}>{part.slice(1, -1)}</em>;
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      const safe = /^https?:\/\//i.test(link[2]);
      return safe ? (
        <a key={n} href={link[2]} target="_blank" rel="noopener noreferrer nofollow" className="font-medium text-brand underline underline-offset-2">
          {link[1]}
        </a>
      ) : <Fragment key={n}>{link[1]}</Fragment>;
    }
    return <Fragment key={n}>{part}</Fragment>;
  });
}
