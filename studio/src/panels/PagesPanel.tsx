import React, { useState } from "react";
import { ApiClient } from "../api/client";
import { PageSummary } from "../api/types";

interface Props {
  code: string;
  client: typeof ApiClient;
}

const PagesPanel: React.FC<Props> = ({ code, client }) => {
  const [pages, setPages] = useState<PageSummary[]>([]);
  const [selected, setSelected] = useState<PageSummary | null>(null);
  const [ui, setUi] = useState<any | null>(null);
   const [currentPage, setCurrentPage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadPages = async () => {
    if (!code.trim()) {
      setError("Provide program code to load pages.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchPages(code);
      setPages(res.pages);
      setSelected(null);
      setUi(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadUI = async (page: PageSummary) => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchPageUI(code, page.name);
      setSelected(page);
      setUi(res.ui);
      setCurrentPage(page.name);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resolvePageManifest = (uiManifest: any, name: string | null) => {
    if (!uiManifest) return null;
    if (Array.isArray(uiManifest.pages)) {
      if (name) {
        return uiManifest.pages.find((p: any) => p.name === name) || uiManifest.pages[0];
      }
      return uiManifest.pages[0];
    }
    // fallback single-page shape
    if (uiManifest.name) {
      return uiManifest;
    }
    return null;
  };

  const findButtons = (layout: any[]): any[] => {
    const result: any[] = [];
    for (const el of layout || []) {
      if (el.type === "button") {
        result.push(el);
      }
      if (el.layout) {
        result.push(...findButtons(el.layout));
      }
      if (el.when) {
        el.when.forEach((child: any) => result.push(...findButtons(child.layout || [])));
      }
      if (el.otherwise) {
        el.otherwise.forEach((child: any) => result.push(...findButtons(child.layout || [])));
      }
    }
    return result;
  };

  const handleNavigate = async (onClick: any) => {
    if (!onClick || onClick.kind !== "navigate") return;
    const target = onClick.target || {};
    let targetName: string | null = target.pageName ?? onClick.targetPage ?? null;
    const targetPath: string | null = target.path ?? onClick.targetPath ?? null;
    if (!targetName && targetPath && pages.length > 0) {
      const match = pages.find((p) => p.route === targetPath);
      targetName = match?.name || null;
    }
    if (!targetName) {
      return;
    }
    const targetSummary = pages.find((p) => p.name === targetName);
    if (!targetSummary) {
      return;
    }
    await loadUI(targetSummary);
  };

  return (
    <div className="panel" aria-label="pages-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Pages Browser</h3>
        <button onClick={loadPages} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {pages.length === 0 && !loading ? <div>No pages loaded.</div> : null}
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1 }}>
          <ul>
            {pages.map((p) => (
              <li key={p.name}>
                <button onClick={() => loadUI(p)}>{p.name}</button> — {p.route || "(no route)"}
              </li>
            ))}
          </ul>
        </div>
        <div style={{ flex: 1 }}>
          {selected && (
            <div>
              <h4>
                {selected.name} ({selected.route})
              </h4>
              <div>Title: {selected.title}</div>
              <pre>{JSON.stringify(ui, null, 2)}</pre>
              {ui && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Preview (navigation-enabled)</div>
                  {(() => {
                    const pageManifest = resolvePageManifest(ui, currentPage);
                    if (!pageManifest) return <div>No UI manifest available.</div>;
                    const buttons = findButtons(pageManifest.layout || []);
                    return (
                      <div>
                        <div style={{ marginBottom: 8 }}>Current page: {pageManifest.name || "(unknown)"}</div>
                        {buttons.map((btn, idx) => (
                          <button
                            key={`${btn.id || btn.label}-${idx}`}
                            onClick={() => handleNavigate(btn.onClick)}
                            className={btn.className}
                            style={{ ...(btn.style || {}), marginRight: 8 }}
                          >
                            {btn.label}
                          </button>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PagesPanel;
