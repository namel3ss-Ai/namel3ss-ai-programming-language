import { describe, it, expect } from "vitest";
import { TEMPLATES } from "../templates/templates";

describe("templates model", () => {
  it("exposes at least one template", () => {
    expect(TEMPLATES.length).toBeGreaterThan(0);
  });

  it("templates have required fields", () => {
    for (const tpl of TEMPLATES) {
      expect(typeof tpl.id).toBe("string");
      expect(tpl.id.length).toBeGreaterThan(0);
      expect(typeof tpl.name).toBe("string");
      expect(tpl.name.length).toBeGreaterThan(0);
      expect(typeof tpl.description).toBe("string");
      expect(tpl.description.length).toBeGreaterThan(0);
      expect(typeof tpl.content).toBe("string");
      expect(tpl.content.length).toBeGreaterThan(0);
    }
  });
});
