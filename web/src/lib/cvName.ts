/**
 * What to call a copy of a CV.
 *
 * A mirror of `_copy_name` in `dossier/core/cvs.py`, and it has to be one: the
 * server only names a copy when the client does not, and the switcher always
 * does. It fills the box with a suggestion so the name can be edited before
 * the document exists rather than corrected after — which means the server's
 * version of this logic never runs for anything the menu creates, and the
 * "(copy 2)" case would be lost if it lived only there.
 */

/** `NameIn` on the route refuses anything longer, so nothing longer is offered. */
export const CV_NAME_MAX = 80;

export function copyName(source: string, taken: Iterable<string>): string {
  const names = new Set(taken);
  // The stem is trimmed to fit, never the finished string. Cutting the tail
  // would take the "(copy 2)" off the end, every candidate would come out
  // identical, and the loop below would never find a free one.
  const stem = source.slice(0, CV_NAME_MAX - 12).trimEnd();
  let candidate = `${stem} (copy)`;
  for (let n = 2; names.has(candidate); n += 1) candidate = `${stem} (copy ${n})`;
  return candidate;
}
