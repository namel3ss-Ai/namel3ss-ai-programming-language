import React, { useMemo, useState } from "react";
import Sidebar from "./components/Sidebar";
import CodeInput from "./components/CodeInput";
import PagesPanel from "./panels/PagesPanel";
import RunnerPanel from "./panels/RunnerPanel";
import TracePanel from "./panels/TracePanel";
import MetricsPanel from "./panels/MetricsPanel";
import JobsPanel from "./panels/JobsPanel";
import DiagnosticsPanel from "./panels/DiagnosticsPanel";
import RagMemoryPanel from "./panels/RagMemoryPanel";
import FlowsPanel from "./panels/FlowsPanel";
import PluginsPanel from "./panels/PluginsPanel";
import OptimizerPanel from "./panels/OptimizerPanel";
import AgentsDebuggerPanel from "./panels/AgentsDebuggerPanel";
import { ApiClient } from "./api/client";

const DEFAULT_CODE = `app "support":
  entry_page "home"
page "home":
  route "/"
  section "hero":
    component "text":
      value "Welcome to Namel3ss"
model "default":
  provider "openai:gpt-4.1-mini"
ai "summarise":
  model "default"
  input from user_message
`;

const PANELS = [
  "Pages",
  "Runner",
  "Traces",
  "Flows",
  "Agents",
  "Metrics",
  "Jobs",
  "RAG & Memory",
  "Plugins",
  "Optimizer",
  "Diagnostics",
];

const App: React.FC = () => {
  const [panel, setPanel] = useState<string>("Pages");
  const [code, setCode] = useState<string>(DEFAULT_CODE);

  const client = useMemo(() => ApiClient, []);

  const renderPanel = () => {
    switch (panel) {
      case "Pages":
        return <PagesPanel code={code} client={client} />;
      case "Runner":
        return <RunnerPanel code={code} client={client} />;
      case "Traces":
        return <TracePanel client={client} />;
      case "Flows":
        return <FlowsPanel code={code} client={client} />;
      case "Agents":
        return <AgentsDebuggerPanel client={client} />;
      case "Metrics":
        return <MetricsPanel client={client} />;
      case "Jobs":
        return <JobsPanel client={client} />;
      case "RAG & Memory":
        return <RagMemoryPanel client={client} />;
      case "Plugins":
        return <PluginsPanel client={client} />;
      case "Optimizer":
        return <OptimizerPanel client={client} />;
      case "Diagnostics":
        return <DiagnosticsPanel code={code} client={client} />;
      default:
        return null;
    }
  };

  return (
    <div className="app">
      <Sidebar panels={PANELS} current={panel} onSelect={setPanel} />
      <div className="content">
        <div className="topbar">
          <h1>Namel3ss Studio</h1>
          <div>Panel: {panel}</div>
        </div>
        <CodeInput value={code} onChange={setCode} />
        {renderPanel()}
      </div>
    </div>
  );
};

export default App;
