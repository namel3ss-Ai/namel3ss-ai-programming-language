import React from "react";

export interface RunStatusProps {
  isRunning: boolean;
  lastStatus?: string | null;
  lastMessage?: string | null;
  lastError?: string | null;
  className?: string;
}

export const RunStatus: React.FC<RunStatusProps> = ({
  isRunning,
  lastStatus,
  lastMessage,
  lastError,
  className,
}) => {
  return (
    <div className={className ?? "n3-run-status"}>
      {isRunning && <span className="n3-run-status-running">Running app...</span>}
      {!isRunning && lastStatus && (
        <span
          className={
            "n3-run-status-result" + (lastStatus === "ok" ? " n3-run-status-ok" : " n3-run-status-error")
          }
        >
          {lastStatus === "ok" ? "Last run: OK" : "Last run: Error"}
          {lastMessage && (
            <>
              {" "}
              <span className="n3-run-status-message">{lastMessage}</span>
            </>
          )}
          {lastError && (
            <>
              {" "}
              <span className="n3-run-status-error-message">{lastError}</span>
            </>
          )}
        </span>
      )}
      {!isRunning && !lastStatus && <span className="n3-run-status-idle">App has not been run yet.</span>}
    </div>
  );
};
