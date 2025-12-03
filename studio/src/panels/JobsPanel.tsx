import React, { useState } from "react";
import { ApiClient } from "../api/client";
import { JobsResponse } from "../api/types";

interface Props {
  client: typeof ApiClient;
}

const JobsPanel: React.FC<Props> = ({ client }) => {
  const [jobs, setJobs] = useState<JobsResponse["jobs"]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.fetchJobs();
      setJobs(res.jobs);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" aria-label="jobs-panel">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Job Queue</h3>
        <button onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {jobs.length === 0 ? (
        <div>No jobs in queue.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>Target</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.id}</td>
                <td>{job.type}</td>
                <td>{job.target}</td>
                <td>{job.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default JobsPanel;
