import { describe, expect, it } from "vitest";

import { groupByPerson, oneLine } from "./cvName";
import type { CVSummary } from "./types";

function cv(person: string, label: string): CVSummary {
  return {
    id: `${person}-${label}`,
    person,
    label,
    name: oneLine({ person, label }),
    created: "",
    updated: "",
    focus: "",
    blank: false,
    auto_named: false,
  };
}

describe("groupByPerson", () => {
  it("collapses a person's CVs into one entry", () => {
    const groups = groupByPerson([
      cv("Priya Raman", ""),
      cv("Priya Raman", "Education"),
      cv("Priya Raman", "Research"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.person).toBe("Priya Raman");
    expect(groups[0]?.cvs.map((c) => c.label)).toEqual(["", "Education", "Research"]);
  });

  it("keeps people in first-seen order, not alphabetical", () => {
    // Sorting would make rows jump under a rename, which is the one moment
    // somebody is looking straight at the list.
    const groups = groupByPerson([
      cv("Zara Ahmed", ""),
      cv("Adam Cole", ""),
      cv("Zara Ahmed", "Research"),
    ]);
    expect(groups.map((g) => g.person)).toEqual(["Zara Ahmed", "Adam Cole"]);
    expect(groups[0]?.cvs).toHaveLength(2);
  });

  it("gives a person with one CV a group of one, not a special case", () => {
    const groups = groupByPerson([cv("Priya Raman", "")]);
    expect(groups).toEqual([{ person: "Priya Raman", cvs: [cv("Priya Raman", "")] }]);
  });

  it("returns nothing for nothing", () => {
    expect(groupByPerson([])).toEqual([]);
  });
});

describe("oneLine", () => {
  it("joins the halves when there is a label", () => {
    expect(oneLine({ person: "Priya Raman", label: "Education" })).toBe(
      "Priya Raman — Education",
    );
  });

  it("is just the person when there is not", () => {
    expect(oneLine({ person: "Priya Raman", label: "" })).toBe("Priya Raman");
  });
});
