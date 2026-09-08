/**
 * The words without the marks.
 *
 * Mirrors `plain` in `dossier/core/markup.py`, and exists for the same
 * reason: a profile field can now carry `<b>`, `<i>` and `<u>`, and only the
 * resume itself should ever show them as formatting. Everywhere the dashboard
 * displays a piece of profile text as a plain string — a title bar, a tab, a
 * card, a label on a chart — it wants the words.
 *
 * Never use this on anything heading for the page. The rendering path
 * deliberately keeps the marks; that is the whole feature.
 */
export function plain(value: string | null | undefined): string {
  return (value || "").replace(/<\/?[biu]>/gi, "");
}
