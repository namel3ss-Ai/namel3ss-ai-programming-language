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
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PagesPanel;
