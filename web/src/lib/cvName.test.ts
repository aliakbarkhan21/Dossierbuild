import { describe, expect, it } from "vitest";

import { copyName, CV_NAME_MAX } from "./cvName";

describe("copyName", () => {
  it("adds (copy) when nothing is in the way", () => {
    expect(copyName("Priya Raman", [])).toBe("Priya Raman (copy)");
  });

  it("counts up rather than repeating a name already in the list", () => {
    const taken = ["Priya Raman", "Priya Raman (copy)"];
    expect(copyName("Priya Raman", taken)).toBe("Priya Raman (copy 2)");
    expect(copyName("Priya Raman", [...taken, "Priya Raman (copy 2)"])).toBe(
      "Priya Raman (copy 3)",
    );
  });

  it("trims the stem, not the suffix, so a long name still fits and still says (copy)", () => {
    // 79 characters: long enough that " (copy)" would push it past the cap the
    // route enforces, which is a 422 rather than a copy.
    const long = "R".repeat(79);
    const result = copyName(long, []);
    expect(result.length).toBeLessThanOrEqual(CV_NAME_MAX);
    expect(result.endsWith(" (copy)")).toBe(true);
  });

  it("does not try to be clever about a name that already ends in (copy)", () => {
    expect(copyName("Priya Raman (copy)", [])).toBe("Priya Raman (copy) (copy)");
  });
});
