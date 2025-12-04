import React from "react";
import type { Template } from "../templates/templates";
import { TEMPLATES } from "../templates/templates";

export interface TemplateWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onApplyTemplate: (template: Template) => void;
}

export const TemplateWizard: React.FC<TemplateWizardProps> = ({ isOpen, onClose, onApplyTemplate }) => {
  const [activeId, setActiveId] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isOpen) {
      setActiveId(TEMPLATES[0]?.id ?? null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const activeTemplate = TEMPLATES.find((t) => t.id === activeId) ?? TEMPLATES[0] ?? null;

  return (
    <div className="n3-template-wizard-backdrop" onClick={onClose}>
      <div
        className="n3-template-wizard"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="n3-template-wizard-header">
          <h2>Templates</h2>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="n3-template-wizard-body">
          <ul className="n3-template-list">
            {TEMPLATES.map((t) => (
              <li
                key={t.id}
                className={"n3-template-list-item" + (t.id === activeTemplate?.id ? " n3-active" : "")}
                onClick={() => setActiveId(t.id)}
              >
                <div className="n3-template-name">{t.name}</div>
                <div className="n3-template-description">{t.description}</div>
              </li>
            ))}
          </ul>
          <div className="n3-template-preview">
            {activeTemplate ? (
              <>
                <h3>{activeTemplate.name}</h3>
                <pre>
                  <code>{activeTemplate.content}</code>
                </pre>
              </>
            ) : (
              <div>No template selected.</div>
            )}
          </div>
        </div>
        <div className="n3-template-wizard-footer">
          <button
            type="button"
            onClick={() => {
              if (activeTemplate) {
                onApplyTemplate(activeTemplate);
                onClose();
              }
            }}
            disabled={!activeTemplate}
          >
            Use this template
          </button>
        </div>
      </div>
    </div>
  );
};
