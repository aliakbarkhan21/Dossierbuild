/**
 * An iframe fed a complete HTML document.
 *
 * The renderer returns a whole document -- its own fonts, its own stylesheet,
 * its own measuring script -- and that is the point: what the frame shows is
 * byte-for-byte what Chromium prints. Putting it in an iframe rather than
 * injecting it into the page keeps the resume's CSS and the app's CSS from
 * ever meeting.
 *
 * `srcDoc` is swapped only when the document actually changes, so typing does
 * not tear down and rebuild the frame on every keystroke.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  html: string;
  title: string;
  className?: string;
  /** Shown until the first document arrives, so the pane never flashes empty. */
  placeholder?: React.ReactNode;
  /**
   * A picture inside a button, rather than a document to be read.
   *
   * An iframe eats the click that lands on it, so a card built around one is
   * only clickable on the strip of caption underneath -- which is exactly how
   * the template gallery behaved: pressing the picture of the template you
   * wanted did nothing at all. A decorative frame passes the click through to
   * whatever wraps it, and stays out of the tab order.
   */
  decorative?: boolean;
}

export function Frame({ html, title, className = "", placeholder, decorative = false }: Props) {
  const ref = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (html) setLoaded(true);
  }, [html]);

  return (
    <div className={`relative ${className}`}>
      {!loaded && placeholder}
      {html && (
        <iframe
          ref={ref}
          title={title}
          srcDoc={html}
          // The document is ours, generated server-side from validated data,
          // and it runs a measuring script -- so scripts are allowed, but it
          // stays in its own opaque origin with no access to this page.
          sandbox="allow-scripts"
          tabIndex={decorative ? -1 : undefined}
          aria-hidden={decorative || undefined}
          className={`h-full w-full border-0 bg-white ${decorative ? "pointer-events-none" : ""}`}
        />
      )}
    </div>
  );
}
