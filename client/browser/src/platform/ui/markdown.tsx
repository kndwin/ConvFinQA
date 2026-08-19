import type { ElementType, ReactNode } from "react";

function inlineMarkdown(value: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern =
    /(\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+?`|\[[^\]]+\]\([^\s)]+\)|~~[^~]+?~~|\*[^*\n]+?\*|_[^_\n]+?_)/g;
  let lastIndex = 0;
  for (const match of value.matchAll(pattern)) {
    const text = match[0];
    const index = match.index ?? 0;
    if (index > lastIndex) nodes.push(value.slice(lastIndex, index));
    if (text.startsWith("**") || text.startsWith("__")) {
      nodes.push(<strong key={`${index}-strong`}>{text.slice(2, -2)}</strong>);
    } else if (text.startsWith("`")) {
      nodes.push(<code key={`${index}-code`}>{text.slice(1, -1)}</code>);
    } else if (text.startsWith("~~")) {
      nodes.push(<del key={`${index}-del`}>{text.slice(2, -2)}</del>);
    } else if (text.startsWith("[") && text.endsWith(")")) {
      const link = /^\[([^\]]+)\]\(([^\s)]+)\)$/.exec(text);
      if (link?.[2].startsWith("http://") || link?.[2].startsWith("https://")) {
        nodes.push(
          <a href={link[2]} key={`${index}-link`} rel="noreferrer" target="_blank">
            {link[1]}
          </a>,
        );
      } else {
        nodes.push(text);
      }
    } else {
      nodes.push(<em key={`${index}-em`}>{text.slice(1, -1)}</em>);
    }
    lastIndex = index + text.length;
  }
  if (lastIndex < value.length) nodes.push(value.slice(lastIndex));
  return nodes;
}

/** Render model output as safe Markdown while retaining the shared typeset styling. */
export function MarkdownContent({ children }: { children: string }) {
  const lines = children.split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push(<p key={`paragraph-${blocks.length}`}>{inlineMarkdown(paragraph.join("\n"))}</p>);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (!list) return;
    const List = list.ordered ? "ol" : "ul";
    blocks.push(
      <List key={`list-${blocks.length}`}>
        {list.items.map((item) => (
          <li key={item}>{inlineMarkdown(item)}</li>
        ))}
      </List>,
    );
    list = null;
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] ?? "";
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    const item = /^\s*(?:(\d+)\.|[-*+])\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const Heading = `h${heading[1].length}` as ElementType;
      blocks.push(<Heading key={`heading-${index}`}>{inlineMarkdown(heading[2])}</Heading>);
    } else if (item) {
      flushParagraph();
      const ordered = item[1] !== undefined;
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(item[2]);
    } else if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();

  return <div className="typeset typeset-docs">{blocks}</div>;
}
