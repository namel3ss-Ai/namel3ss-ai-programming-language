import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;

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

  const restart = vscode.commands.registerCommand("namel3ss.restartServer", async () => {
    try {
      await restartClient();
      vscode.window.showInformationMessage("Namel3ss language server restarted.");
    } catch {
      // error already surfaced
    }
  });

  context.subscriptions.push(restart, { dispose: () => client?.stop() });
}

export async function deactivate() {
  if (client) {
    await client.stop();
    client = undefined;
  }
}
