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
}

export function Frame({ html, title, className = "", placeholder }: Props) {
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
          className="h-full w-full border-0 bg-white"
        />
      )}
    </div>
  );
}
