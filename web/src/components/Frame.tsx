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
  /**
   * The frame itself, for a caller that talks to the document inside it.
   *
   * The document is sandboxed into an opaque origin, so there is no reaching
   * into it -- but `postMessage` crosses that boundary, and the fit script
   * listens for a zoom. That is how the full-page view scales without
   * fetching a second copy of the page.
   */
  frameRef?: React.RefObject<HTMLIFrameElement | null>;
  /** Fired once the document inside has parsed and run its script. */
  onLoad?: () => void;
}

export function Frame({
  html,
  title,
  className = "",
  placeholder,
  decorative = false,
  frameRef,
  onLoad,
}: Props) {
  const own = useRef<HTMLIFrameElement>(null);
  const ref = frameRef ?? own;
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
          // `allow-popups` so a link in the CV can open in a tab, and
          // `-to-escape-sandbox` so the site it opens is a normal page rather
          // than one inheriting this opaque origin and rendering broken. The
          // document is ours, generated from validated data, and its hrefs are
          // limited to http, https, mailto and tel before they are written.
          sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
          onLoad={onLoad}
          tabIndex={decorative ? -1 : undefined}
          aria-hidden={decorative || undefined}
          className={`h-full w-full border-0 bg-white ${decorative ? "pointer-events-none" : ""}`}
        />
      )}
    </div>
  );
}
