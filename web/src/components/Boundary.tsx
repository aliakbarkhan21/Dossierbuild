/**
 * Something to look at when a screen throws.
 *
 * React unmounts the whole tree when a render throws and nothing catches it,
 * so one bad read in one panel took the entire application down to an empty
 * dark rectangle -- no message, no navigation, nothing to act on. That is the
 * worst possible failure for a desktop app somebody keeps their CV in: it
 * looks like the data is gone.
 *
 * The first thing this asks about is the version, because that is what it has
 * actually been twice. A server started before a rebuild keeps serving its own
 * Python while the browser has the new bundle, and the two disagree about the
 * shape of a payload. Restarting is the fix, and it is worth saying so before
 * anybody starts looking for a lost profile.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Named so the message can say which screen went, not just "something". */
  where?: string;
}

interface State {
  error: Error | null;
}

export class Boundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // The console is where this is actually diagnosable, so the stack goes
    // there whole rather than being summarised onto the page.
    console.error(`[${this.props.where ?? "screen"}]`, error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-md">
          <h2 className="font-display text-lg font-semibold text-ink">
            This screen stopped.
          </h2>
          <p className="mt-2 text-sm text-muted">
            The rest of the app is still fine — the sidebar will take you
            somewhere else, and nothing has been written to your CV.
          </p>
          <p className="mt-3 text-sm text-muted">
            The usual cause is a Dossierbuild that has been rebuilt while it was
            running: the page is new and the server behind it is not. Close this
            window and start it again from the desktop shortcut, which will now
            stop the old one for you.
          </p>
          <p className="mt-3 font-mono text-2xs text-faint">{error.message}</p>
          <button
            type="button"
            className="btn btn-quiet mt-4 px-2.5 py-1 text-xs"
            onClick={() => this.setState({ error: null })}
          >
            Try this screen again
          </button>
        </div>
      </div>
    );
  }
}
