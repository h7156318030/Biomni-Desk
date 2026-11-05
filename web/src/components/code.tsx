"use client";

import { Fragment } from "react";

const KEYWORDS = new Set(
  "import from def class return for in if elif else while try except finally with as None True False and or not lambda pass raise break continue yield global assert del is".split(" "),
);
const BUILTINS = new Set("print len range list dict set tuple str int float open type isinstance enumerate zip sorted sum min max map filter".split(" "));

// comment | string | word | number
const TOKEN = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|([A-Za-z_][A-Za-z0-9_]*)|(\b\d+(?:\.\d+)?\b)/g;

export type Piece = { text: string; kind: "plain" | "comment" | "string" | "keyword" | "builtin" | "number" };

/** Split Python source into coloured pieces; the pieces always join back to the original text. */
export function tokenize(code: string): Piece[] {
  const out: Piece[] = [];
  let last = 0;
  for (const m of code.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ text: code.slice(last, at), kind: "plain" });
    const [text, comment, str, word, num] = m;
    let kind: Piece["kind"] = "plain";
    if (comment) kind = "comment";
    else if (str) kind = "string";
    else if (word) kind = KEYWORDS.has(word) ? "keyword" : BUILTINS.has(word) ? "builtin" : "plain";
    else if (num) kind = "number";
    out.push({ text, kind });
    last = at + text.length;
  }
  if (last < code.length) out.push({ text: code.slice(last), kind: "plain" });
  return out;
}

const CLASS: Record<Piece["kind"], string> = {
  plain: "",
  comment: "tok-comment",
  string: "tok-string",
  keyword: "tok-keyword",
  builtin: "tok-builtin",
  number: "tok-number",
};

export function CodeBlock({ code }: { code: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md bg-codebg p-3 font-mono text-[13px] leading-snug">
      <code>
        {tokenize(code).map((p, i) =>
          p.kind === "plain" ? (
            <Fragment key={i}>{p.text}</Fragment>
          ) : (
            <span key={i} className={CLASS[p.kind]}>
              {p.text}
            </span>
          ),
        )}
      </code>
    </pre>
  );
}
