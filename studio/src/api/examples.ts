export interface ExampleSource {
  name: string;
  path: string;
  source: string;
}

export async function fetchExampleSource(name: string): Promise<ExampleSource> {
  const url = `/api/example-source?name=${encodeURIComponent(name)}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load example '${name}' (${res.status})`);
  }
  return res.json();
}
