import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TemplateWizard } from "../components/TemplateWizard";
import { TEMPLATES } from "../templates/templates";

describe("TemplateWizard", () => {
  it("renders nothing when closed", () => {
    render(<TemplateWizard isOpen={false} onClose={() => {}} onApplyTemplate={() => {}} />);
    expect(screen.queryByText("Templates")).not.toBeInTheDocument();
  });

  it("shows templates and preview when open", () => {
    render(<TemplateWizard isOpen={true} onClose={() => {}} onApplyTemplate={() => {}} />);

    expect(screen.getAllByText(TEMPLATES[0].name).length).toBeGreaterThan(0);
    expect(screen.getByText("Use this template")).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes(TEMPLATES[0].content.substring(0, 5)))).toBeInTheDocument();
  });

  it("calls onApplyTemplate and onClose when using a template", () => {
    const onApply = vi.fn();
    const onClose = vi.fn();

    render(<TemplateWizard isOpen={true} onClose={onClose} onApplyTemplate={onApply} />);

    const useButton = screen.getByText("Use this template");
    fireEvent.click(useButton);

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(TEMPLATES).toContain(onApply.mock.calls[0][0]);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
