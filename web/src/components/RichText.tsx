/**
 * A field that can carry bold, italic and underline — and nothing else.
 *
 * Used for every piece of writing on the resume: the name, a job title, an
 * organisation, a skill group, a bullet, the summary. Three deliberate
 * limits, because a resume is not a document with rich text in it, it is a
 * plain document with the occasional emphasised number.
 *
 * **Three marks.** No colours, no sizes, no fonts, no lists. Those are the
 * design's job and they live on Resume, where changing one changes the whole
 * document rather than one line of it. A field that can set type size is a
 * field somebody uses to make one bullet bigger than its neighbours.
 *
 * **The stored value is still plain text.** Only the six substrings `<b>`,
 * `</b>`, `<i>`, `</i>`, `<u>` and `</u>` mean anything; every other
 * character, `<` and `&` included, is literal. That is what lets every
 * existing profile, every import and every AI rewrite keep meaning exactly
 * what it meant — see `dossier/core/markup.py`, which is the same contract
 * read from the other end.
 *
 * **Paste arrives plain.** Most text pasted into a CV comes out of Word or a
 * job posting and brings its own fonts, sizes and colours with it. Taking the
 * words and leaving the styling is not a limitation here, it is the feature.
 *
 * Four kinds of field deliberately do *not* get one. Email, phone and links
 * are addresses, and an `href` built out of marked-up text is a link that
 * goes nowhere. Dates and the employment-type dropdown are structured values
 * rather than writing.
 *
 * `document.execCommand` is deprecated and is still the only API that will
 * bold a selection spanning several text nodes in every browser. The
 * alternative is reimplementing range splitting by hand to arrive at what the
 * built-in already does. What comes out of it is normalised by `serialize` on
 * the way to the store, so the deprecated call's output shape is never what
 * gets saved.
 */

import { Bold, Italic, Underline } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

/** What the three buttons do, in the order they are shown. */
const MARKS = [
  { key: "bold", tag: "b", label: "Bold", icon: Bold, shortcut: "B" },
  { key: "italic", tag: "i", label: "Italic", icon: Italic, shortcut: "I" },
  { key: "underline", tag: "u", label: "Underline", icon: Underline, shortcut: "U" },
] as const;

/** Elements a browser may produce for a mark, mapped to the one we store. */
const AS: Record<string, string> = { B: "b", STRONG: "b", I: "i", EM: "i", U: "u" };

/** Elements that end a line, whatever else they are. */
const BLOCK = /^(DIV|P|LI|TR|BLOCKQUOTE|H[1-6])$/;

/**
 * The stored string as nodes for a contenteditable.
 *
 * Everything is escaped first and only the six tags are let back through, so
 * this is the exact mirror of `markup.rich` on the server: what the field
 * shows is what the PDF prints, and a `<` typed into a bullet is a `<` in
 * both.
 */
function toHtml(value: string, singleLine: boolean): string {
  const escaped = (value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, singleLine ? " " : "<br>");
  return escaped.replace(/&lt;(\/?)(b|i|u)&gt;/g, "<$1$2>");
}

/**
 * The nodes back to a stored string, keeping only the three marks.
 *
 * Walking the tree rather than regexing `innerHTML` is what makes the output
 * balanced by construction: a tag can only be closed here by returning from
 * the call that opened it. A span, a font, a colour or a pasted table
 * contributes its text and nothing else.
 */
function serialize(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.nodeValue ?? "";
  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const el = node as HTMLElement;
  if (el.tagName === "BR") return "\n";

  let inner = "";
  el.childNodes.forEach((child) => {
    inner += serialize(child);
  });

  const tag = AS[el.tagName];
  // An empty mark is noise: bolding a selection and then deleting it leaves
  // `<b></b>` behind, which would count as a change and dirty the profile.
  if (tag) return inner.trim() ? `<${tag}>${inner}</${tag}>` : inner;
  if (BLOCK.test(el.tagName) && inner) return `\n${inner}`;
  return inner;
}

function read(root: HTMLElement, singleLine: boolean): string {
  let out = "";
  root.childNodes.forEach((child) => {
    out += serialize(child);
  });
  // A contenteditable's first block is the field's own first line, so the
  // newline that opened it is an artefact of the markup rather than a line
  // the writer typed.
  out = out.replace(/^\n+/, "").replace(/\n{3,}/g, "\n\n");
  return singleLine ? out.replace(/\s*\n+\s*/g, " ") : out;
}

export function RichText({
  value,
  onChange,
  placeholder,
  className = "",
  blockId,
  ariaLabel,
  singleLine = false,
  id,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  className?: string;
  /** Kept so the Health screen can still scroll to and flash one bullet. */
  blockId?: string;
  ariaLabel?: string;
  /** A name, a job title, an organisation: one line, and Enter ends it. */
  singleLine?: boolean;
  id?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [focused, setFocused] = useState(false);
  // Whether to draw the placeholder. Tracked rather than left to `:empty`,
  // because a contenteditable that has been typed in and cleared keeps a
  // stray `<br>` in most browsers — so it is not `:empty`, and a CSS
  // placeholder would never come back.
  const [blank, setBlank] = useState(!value);
  // Which marks the caret currently sits inside, for the pressed state.
  const [active, setActive] = useState<string[]>([]);

  /**
   * Follow the value when it changes from somewhere else — an undo, an
   * import, an AI rewrite, the read-back after a save.
   *
   * Guarded on the *serialized* form rather than the raw HTML. Without the
   * guard, every keystroke would write back the DOM the component had just
   * read, collapsing the selection and putting the caret at the start; with
   * it, typing leaves the node alone and only a genuine outside change
   * redraws it.
   */
  useEffect(() => {
    const el = ref.current;
    if (!el || document.activeElement === el) return;
    if (read(el, singleLine) !== value) el.innerHTML = toHtml(value, singleLine);
    setBlank(!value);
  }, [value, singleLine]);

  useEffect(() => {
    const el = ref.current;
    if (el && !el.innerHTML) el.innerHTML = toHtml(value, singleLine);
    // Once, on mount: the effect above deliberately skips a focused field.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sync = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const next = read(el, singleLine);
    setBlank(!next);
    onChange(next);
  }, [onChange, singleLine]);

  const refreshMarks = useCallback(() => {
    setActive(
      MARKS.filter((mark) => {
        try {
          return document.queryCommandState(mark.key);
        } catch {
          return false;
        }
      }).map((mark) => mark.key),
    );
  }, []);

  const apply = (command: string) => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    try {
      // Off, so the browser writes `<b>` rather than a span with an inline
      // font-weight. A span would survive the round trip as unstyled text and
      // the mark would vanish on the next save.
      document.execCommand("styleWithCSS", false, "false");
      document.execCommand(command);
    } catch {
      return;
    }
    sync();
    refreshMarks();
  };

  return (
    <div className="relative">
      {/* Behind the field rather than inside it: text put *into* a
          contenteditable is text the caret can land in and the serializer
          would read back as content the writer never typed. */}
      {blank && placeholder && (
        <span
          aria-hidden
          className="pointer-events-none absolute left-[0.6rem] top-[0.4rem] z-0 select-none truncate text-faint"
          style={{ maxWidth: "calc(100% - 1.2rem)" }}
        >
          {placeholder}
        </span>
      )}

      <div
        ref={ref}
        id={id}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline={!singleLine}
        aria-label={ariaLabel}
        data-block-id={blockId}
        spellCheck
        className={[
          "field relative z-10 break-words bg-transparent",
          singleLine
            ? "overflow-x-auto whitespace-nowrap"
            : "resize-y overflow-auto whitespace-pre-wrap",
          className,
        ].join(" ")}
        onInput={sync}
        onKeyUp={refreshMarks}
        onMouseUp={refreshMarks}
        onFocus={() => {
          setFocused(true);
          refreshMarks();
        }}
        onBlur={() => {
          setFocused(false);
          sync();
        }}
        onKeyDown={(event) => {
          const hit = MARKS.find(
            (mark) => (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === mark.tag,
          );
          if (hit) {
            // The browser would do this anyway, but not with styleWithCSS
            // turned off — so the shortcut and the button have to be one code
            // path or they produce different markup.
            event.preventDefault();
            apply(hit.key);
            return;
          }
          // A job title is one line. Enter would otherwise open a second one
          // inside a box only tall enough for the first.
          if (singleLine && event.key === "Enter") {
            event.preventDefault();
            event.currentTarget.blur();
          }
        }}
        onPaste={(event) => {
          event.preventDefault();
          const text = event.clipboardData.getData("text/plain");
          document.execCommand("insertText", false, singleLine ? text.replace(/\s+/g, " ") : text);
          sync();
        }}
      />

      {/* Above the field, not inside it. Inside meant reserving a strip of
          every field for a toolbar that is visible a fraction of the time,
          and a one-line box has no room to reserve. Only while the field has
          focus: a permanent strip on forty fields is how a small feature
          makes a whole editor look busy. */}
      {focused && (
        <div
          className="absolute bottom-full right-0 z-30 mb-1 flex gap-0.5 rounded-md border border-line bg-surface p-0.5 shadow-raised"
          // The field must not lose the selection to a button press, or the
          // command would have nothing to act on.
          onMouseDown={(event) => event.preventDefault()}
        >
          {MARKS.map((mark) => (
            <button
              key={mark.key}
              type="button"
              className={[
                "btn btn-quiet px-1.5 py-0.5",
                active.includes(mark.key) ? "bg-accent-soft text-accent" : "",
              ].join(" ")}
              aria-pressed={active.includes(mark.key)}
              title={`${mark.label} (Ctrl+${mark.shortcut})`}
              aria-label={mark.label}
              onClick={() => apply(mark.key)}
            >
              <mark.icon size={13} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
