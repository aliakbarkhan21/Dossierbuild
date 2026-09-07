/**
 * Reading the filename a download arrives with.
 *
 * The file is fetched as a blob and handed over with `<a download>`, so the
 * browser never reads `Content-Disposition` itself -- whatever this function
 * returns is the name the file lands under. It used to read only
 * `filename="..."`, the transliterated ASCII half, so an applicant called
 * 李明 downloaded `Resume-Classic.pdf` with their name deleted.
 */

import { describe, expect, it } from "vitest";

import { filenameFrom } from "./api";

const HAN = "李明";
const TURKISH = "Ünsal-Öztürk";

describe("filenameFrom", () => {
  it("prefers the encoded half, which carries the real characters", () => {
    const header =
      `attachment; filename="Resume-Classic.pdf"; ` +
      `filename*=UTF-8''%E6%9D%8E%E6%98%8E-Resume-Classic.pdf`;
    expect(filenameFrom(header, "Resume.pdf")).toBe(`${HAN}-Resume-Classic.pdf`);
  });

  it("keeps accents rather than the folded fallback", () => {
    const header =
      `attachment; filename="Unsal-Ozturk-Resume.pdf"; ` +
      `filename*=UTF-8''%C3%9Cnsal-%C3%96zt%C3%BCrk-Resume.pdf`;
    expect(filenameFrom(header, "Resume.pdf")).toBe(`${TURKISH}-Resume.pdf`);
  });

  it("falls back to the plain half when there is no encoded one", () => {
    const header = `attachment; filename="Priya-Raman-Resume.pdf"`;
    expect(filenameFrom(header, "Resume.pdf")).toBe("Priya-Raman-Resume.pdf");
  });

  it("accepts a lower-case charset, which the RFC allows", () => {
    const header = `attachment; filename="a.pdf"; filename*=utf-8''%C3%9C.pdf`;
    expect(filenameFrom(header, "Resume.pdf")).toBe("Ü.pdf");
  });

  it("does not fail a download over a malformed percent sequence", () => {
    const header = `attachment; filename="Good-Name.pdf"; filename*=UTF-8''%E0%A4%A`;
    expect(filenameFrom(header, "Resume.pdf")).toBe("Good-Name.pdf");
  });

  it("uses the caller's fallback when the header says nothing useful", () => {
    expect(filenameFrom("", "Cover-Letter.pdf")).toBe("Cover-Letter.pdf");
    expect(filenameFrom("attachment", "Cover-Letter.pdf")).toBe("Cover-Letter.pdf");
  });

  it("is not confused by a parameter following the encoded one", () => {
    const header = `attachment; filename*=UTF-8''Resume.pdf; charset=utf-8`;
    expect(filenameFrom(header, "x.pdf")).toBe("Resume.pdf");
  });
});
