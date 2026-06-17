"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useMemo, useState } from "react";
import { ColumnConfig, Job, ModelConfig, ModelProvider, StudioState, downloadUrl, studioFetch } from "./api";

const sections = [
  ["Project", "DB"],
  ["Providers", "SR"],
  ["Models", "MD"],
  ["Columns", "CL"],
  ["Jobs", "RN"],
  ["Analytics", "AN"],
  ["Review", "RV"],
  ["Export", "EX"],
] as const;

export default function StudioPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["studio-state"],
    queryFn: () => studioFetch<StudioState>("/api/state"),
    refetchInterval: 3000,
  });

  const [provider, setProvider] = useState({ name: "modal-vllm", endpoint: "", api_key_secret: "MODAL_MODEL_API_KEY" });
  const [model, setModel] = useState({ role: "Generator", alias: "modal-chat", model: "modal-chat", endpoint: "", max_tokens: 1024 });
  const [column, setColumn] = useState({ type: "Generated Column", name: "output", depends: "instruction", prompt: "" });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["studio-state"] });
  const addProvider = useMutation({
    mutationFn: () => studioFetch<ModelProvider>("/api/model-providers", { method: "POST", body: JSON.stringify(provider) }),
    onSuccess: invalidate,
  });
  const addModel = useMutation({
    mutationFn: () =>
      studioFetch<ModelConfig>("/api/model-configs", {
        method: "POST",
        body: JSON.stringify({ ...model, temperature: 0.7, top_p: 0.9, parallel: 4 }),
      }),
    onSuccess: invalidate,
  });
  const addColumn = useMutation({
    mutationFn: () => studioFetch<ColumnConfig>("/api/columns", { method: "POST", body: JSON.stringify(column) }),
    onSuccess: invalidate,
  });
  const preview = useMutation({
    mutationFn: () => studioFetch<Job>("/api/preview-jobs", { method: "POST", body: JSON.stringify({ rows: 10 }) }),
    onSuccess: invalidate,
  });
  const generate = useMutation({
    mutationFn: () =>
      studioFetch<Job>("/api/generation-jobs", {
        method: "POST",
        body: JSON.stringify({ target_records: data?.project.dataset_size ?? 100 }),
      }),
    onSuccess: invalidate,
  });
  const exportJob = useMutation({
    mutationFn: () => studioFetch<{ download_url?: string }>("/api/exports", { method: "POST", body: JSON.stringify({ format: "JSONL" }) }),
    onSuccess: invalidate,
  });

  const previewColumns = useMemo(() => Object.keys(data?.preview_records[0]?.data ?? {}), [data?.preview_records]);

  if (isLoading) {
    return <main className="shell">Loading Studio...</main>;
  }
  if (error || !data) {
    return <main className="shell error">Studio API is not reachable. Check FastAPI and the admin token.</main>;
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">DataDesigner</p>
          <h1>Synthetic Data Studio</h1>
        </div>
        <nav>
          {sections.map(([label, icon]) => (
            <a href={`#${label.toLowerCase()}`} key={label}>
              <span className="nav-icon">{icon}</span>
              {label}
            </a>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Current project</p>
            <h2>{data.project.name}</h2>
          </div>
          <button onClick={() => invalidate()} title="Refresh state">
            <span className="button-icon">R</span>
            Refresh
          </button>
        </header>

        <section className="band metrics">
          <Metric label="Target" value={data.project.dataset_size.toLocaleString()} />
          <Metric label="Models" value={data.models.length.toString()} />
          <Metric label="Columns" value={data.columns.length.toString()} />
          <Metric label="Reviews" value={data.reviews.length.toString()} />
        </section>

        <section className="grid">
          <Panel id="project" title="Project">
            <p>{data.project.description}</p>
            <pre>{data.project.output_schema}</pre>
          </Panel>

          <Panel id="providers" title="Providers">
            <List rows={data.model_providers.map((item) => [item.name, item.endpoint])} />
            <form onSubmit={(event) => submit(event, () => addProvider.mutate())}>
              <input value={provider.name} onChange={(event) => setProvider({ ...provider, name: event.target.value })} />
              <input
                placeholder="https://host/v1"
                value={provider.endpoint}
                onChange={(event) => setProvider({ ...provider, endpoint: event.target.value })}
              />
              <button>Add</button>
            </form>
          </Panel>

          <Panel id="models" title="Models">
            <List rows={data.models.map((item) => [item.alias, `${item.role} · ${item.model}`])} />
            <form onSubmit={(event) => submit(event, () => addModel.mutate())}>
              <select value={model.role} onChange={(event) => setModel({ ...model, role: event.target.value })}>
                <option>Generator</option>
                <option>Judge</option>
                <option>Validator</option>
                <option>Embedding</option>
              </select>
              <input value={model.alias} onChange={(event) => setModel({ ...model, alias: event.target.value })} />
              <input value={model.model} onChange={(event) => setModel({ ...model, model: event.target.value })} />
              <button>Add</button>
            </form>
          </Panel>

          <Panel id="columns" title="Columns">
            <List rows={data.columns.map((item) => [item.name, `${item.type} · ${item.depends || "root"}`])} />
            <form onSubmit={(event) => submit(event, () => addColumn.mutate())}>
              <select value={column.type} onChange={(event) => setColumn({ ...column, type: event.target.value })}>
                <option>Sampler</option>
                <option>Generated Column</option>
                <option>Derived Column</option>
                <option>Retrieval Column</option>
                <option>Judge Score</option>
                <option>Static</option>
              </select>
              <input value={column.name} onChange={(event) => setColumn({ ...column, name: event.target.value })} />
              <input value={column.depends} onChange={(event) => setColumn({ ...column, depends: event.target.value })} />
              <textarea value={column.prompt} onChange={(event) => setColumn({ ...column, prompt: event.target.value })} />
              <button>Add</button>
            </form>
          </Panel>
        </section>

        <section className="band" id="jobs">
          <div className="section-heading">
            <h3>Jobs</h3>
            <div className="actions">
              <button onClick={() => preview.mutate()}>
                <span className="button-icon">P</span>
                Preview
              </button>
              <button onClick={() => generate.mutate()}>
                <span className="button-icon">G</span>
                Generate
              </button>
            </div>
          </div>
          <div className="jobline">
            <span>{data.generation_job?.status ?? "No generation job"}</span>
            <strong>{data.generation_job?.completed_records ?? 0}</strong>
            <span>{data.generation_job?.samples_per_second ?? 0} samples/sec</span>
          </div>
          <PreviewTable columns={previewColumns} rows={data.preview_records} />
        </section>

        <section className="grid">
          <Panel id="analytics" title="Analytics">
            <List
              rows={[
                ["Duplicate groups", data.analytics.duplicate_groups.toString()],
                ["Largest cluster", data.analytics.largest_cluster],
                ["Diversity score", data.analytics.diversity_score.toFixed(2)],
              ]}
            />
          </Panel>
          <Panel id="review" title="Human Review">
            <List rows={data.reviews.map((item) => [item.status, `${item.title}: ${item.detail}`])} />
          </Panel>
          <Panel id="export" title="Export">
            <button onClick={() => exportJob.mutate()}>
              <span className="button-icon">D</span>
              Prepare JSONL
            </button>
            {exportJob.data?.download_url ? <a href={downloadUrl(exportJob.data.download_url)}>Download export</a> : null}
            <pre>{data.yaml}</pre>
          </Panel>
        </section>
      </section>
    </main>
  );
}

function submit(event: FormEvent<HTMLFormElement>, action: () => void) {
  event.preventDefault();
  action();
}

function Metric({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({ id, title, children }: Readonly<{ id: string; title: string; children: React.ReactNode }>) {
  return (
    <section className="panel" id={id}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function List({ rows }: Readonly<{ rows: string[][] }>) {
  return (
    <div className="list">
      {rows.map(([left, right]) => (
        <div className="row" key={`${left}-${right}`}>
          <strong>{left}</strong>
          <span>{right}</span>
        </div>
      ))}
    </div>
  );
}

function PreviewTable({ columns, rows }: Readonly<{ columns: string[]; rows: StudioState["preview_records"] }>) {
  if (rows.length === 0) {
    return <p>No preview records yet.</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {columns.map((column) => (
                <td key={column}>{String(row.data[column] ?? "")}</td>
              ))}
              <td>{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
