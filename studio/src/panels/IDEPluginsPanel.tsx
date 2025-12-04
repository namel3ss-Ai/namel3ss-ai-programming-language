import React, { useEffect, useState } from "react";
import type { PluginMetadata } from "../api/types";
import { ApiClient } from "../api/client";
import { PluginList } from "../components/PluginList";

export const IDEPluginsPanel: React.FC = () => {
  const [plugins, setPlugins] = useState<PluginMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const data = await ApiClient.fetchPlugins();
        if (!cancelled) {
          setPlugins(data);
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage("Failed to load plugins");
          setPlugins([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="n3-ide-plugins-panel">
      <h3>Plugins</h3>
      {isLoading && <div className="n3-plugins-loading">Loading plugins...</div>}
      {errorMessage && <div className="n3-plugins-error">{errorMessage}</div>}
      {!isLoading && !errorMessage && <PluginList plugins={plugins} />}
    </div>
  );
};
