import * as vscode from "vscode";
import { execFile } from "child_process";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;
let lintCollection: vscode.DiagnosticCollection | undefined;

const keywordDocs: Record<string, { description: string; link?: string }> = {
  app: { description: "Defines the root application.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/concepts/language.md" },
  page: { description: "Declares a UI page.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/concepts/ui-components.md" },
  flow: { description: "Declarative, async control flow for your app.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/concepts/flows.md" },
  agent: { description: "Defines an agent with memory and planning.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/concepts/agents.md" },
  ai: { description: "AI/model invocation with prompts, tools, and memory.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/concepts/ai.md" },
  memory: { description: "Memory configuration for conversations or vector stores.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/quickstart/rag-and-memory.md" },
  record: { description: "Record/CRUD schema.", link: "https://github.com/namel3ss-ai/namel3ss-ai-programming-language/blob/main/docs/concepts/records-crud.md" },
};

function createClient(): LanguageClient {
  const config = vscode.workspace.getConfiguration("namel3ss");
  const command = config.get<string>("lsp.command", "n3");
  const args = config.get<string[]>("lsp.args", ["lsp"]);
  const trace = config.get<string>("lsp.trace.server", "off");

  const serverOptions: ServerOptions = {
    command,
    args,
    transport: TransportKind.stdio,
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "namel3ss" }],
    synchronize: {
      configurationSection: "namel3ss",
    },
    traceOutputChannel:
      trace === "off"
        ? undefined
        : vscode.window.createOutputChannel("Namel3ss LSP Trace"),
  };

  const lc = new LanguageClient(
    "namel3ss",
    "Namel3ss Language Server",
    serverOptions,
    clientOptions
  );

  return lc;
}

function toVscodeDiagnostic(item: any): vscode.Diagnostic {
  const severity =
    item.severity === "error"
      ? vscode.DiagnosticSeverity.Error
      : item.severity === "warning"
        ? vscode.DiagnosticSeverity.Warning
        : vscode.DiagnosticSeverity.Information;
  const line = Math.max((item.line ?? 1) - 1, 0);
  const col = Math.max((item.column ?? 1) - 1, 0);
  const range = new vscode.Range(line, col, line, col + 1);
  const message = item.hint ? `${item.message}\nHint: ${item.hint}` : item.message;
  const diag = new vscode.Diagnostic(range, message, severity);
  diag.code = item.code;
  if (item.doc_url) {
    diag.codeDescription = { href: vscode.Uri.parse(item.doc_url) };
  }
  return diag;
}

async function runLintForDocument(doc: vscode.TextDocument): Promise<void> {
  if (!lintCollection) {
    return;
  }
  const config = vscode.workspace.getConfiguration("namel3ss");
  const command = config.get<string>(
    "lint.command",
    config.get<string>("lsp.command", "n3") || "n3"
  );
  const args = config.get<string[]>("lint.args", ["lint", "--json"]);
  return new Promise((resolve) => {
    execFile(
      command,
      [...args, doc.fileName],
      { cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath },
      (err, stdout, stderr) => {
        if (err && !stdout) {
          const warning = new vscode.Diagnostic(
            new vscode.Range(0, 0, 0, 1),
            `Lint failed: ${stderr || err.message}`,
            vscode.DiagnosticSeverity.Warning
          );
          lintCollection!.set(doc.uri, [warning]);
          return resolve();
        }
        try {
          const payload = JSON.parse(stdout || "{}");
          const diags = Array.isArray(payload.lint)
            ? payload.lint.map((item: any) => toVscodeDiagnostic(item))
            : [];
          lintCollection!.set(doc.uri, diags);
        } catch (parseErr: any) {
          const warning = new vscode.Diagnostic(
            new vscode.Range(0, 0, 0, 1),
            `Lint output could not be parsed: ${parseErr?.message || parseErr}`,
            vscode.DiagnosticSeverity.Warning
          );
          lintCollection!.set(doc.uri, [warning]);
        }
        resolve();
      }
    );
  });
}

async function startClient() {
  if (client) {
    return client;
  }
  client = createClient();
  try {
    await client.start();
  } catch (err: any) {
    vscode.window.showErrorMessage(
      `Failed to start Namel3ss language server: ${err?.message || err}`
    );
    client = undefined;
    throw err;
  }
  return client;
}

async function restartClient() {
  if (client) {
    await client.stop();
    client = undefined;
  }
  return startClient();
}

export async function activate(context: vscode.ExtensionContext) {
  await startClient();

  lintCollection = vscode.languages.createDiagnosticCollection("namel3ss-lint");

  const restart = vscode.commands.registerCommand("namel3ss.restartServer", async () => {
    try {
      await restartClient();
      vscode.window.showInformationMessage("Namel3ss language server restarted.");
    } catch {
      // error already surfaced
    }
  });

  const lintCmd = vscode.commands.registerCommand("namel3ss.runLint", async () => {
    const doc = vscode.window.activeTextEditor?.document;
    if (!doc || doc.languageId !== "namel3ss") {
      vscode.window.showInformationMessage("Open a Namel3ss (.ai) file to lint.");
      return;
    }
    await runLintForDocument(doc);
  });

  const hoverProvider = vscode.languages.registerHoverProvider("namel3ss", {
    provideHover(document, position) {
      const range = document.getWordRangeAtPosition(position);
      if (!range) return undefined;
      const word = document.getText(range);
      const entry = keywordDocs[word];
      if (!entry) return undefined;
      const md = new vscode.MarkdownString();
      md.appendMarkdown(`**${word}** — ${entry.description}`);
      if (entry.link) {
        md.appendMarkdown(`\n\n[Docs](${entry.link})`);
        md.isTrusted = true;
      }
      return new vscode.Hover(md, range);
    },
  });

  const lintOnSave = vscode.workspace.onDidSaveTextDocument(async (doc) => {
    const config = vscode.workspace.getConfiguration("namel3ss");
    if (doc.languageId === "namel3ss" && config.get<boolean>("lint.onSave", true)) {
      await runLintForDocument(doc);
    }
  });

  context.subscriptions.push(
    restart,
    lintCmd,
    hoverProvider,
    lintOnSave,
    lintCollection,
    { dispose: () => client?.stop() }
  );
}

export async function deactivate() {
  if (client) {
    await client.stop();
    client = undefined;
  }
  if (lintCollection) {
    lintCollection.dispose();
    lintCollection = undefined;
  }
}
