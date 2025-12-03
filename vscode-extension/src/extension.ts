import * as vscode from "vscode";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

async function runCommand(cmd: string, filePath: string) {
  const terminal = vscode.window.createOutputChannel("Namel3ss");
  terminal.appendLine(`Running: ${cmd} ${filePath}`);
  try {
    const { stdout, stderr } = await execAsync(`${cmd} ${filePath}`);
    terminal.append(stdout);
    if (stderr) terminal.append(stderr);
    vscode.window.showInformationMessage(`${cmd} succeeded`);
  } catch (err: any) {
    terminal.appendLine(String(err));
    vscode.window.showErrorMessage(`${cmd} failed: ${err?.message || err}`);
  }
  terminal.show(true);
}

export function activate(context: vscode.ExtensionContext) {
  const parse = vscode.commands.registerCommand("namel3ss.runParse", async () => {
    const doc = vscode.window.activeTextEditor?.document;
    if (!doc) {
      vscode.window.showWarningMessage("No active .ai file to parse");
      return;
    }
    await doc.save();
    await runCommand("n3 parse", doc.fileName);
  });

  const diagnostics = vscode.commands.registerCommand("namel3ss.runDiagnostics", async () => {
    const doc = vscode.window.activeTextEditor?.document;
    if (!doc) {
      vscode.window.showWarningMessage("No active .ai file to diagnose");
      return;
    }
    await doc.save();
    await runCommand("n3 diagnostics --file", doc.fileName);
  });

  context.subscriptions.push(parse, diagnostics);
}

export function deactivate() {
  // nothing to clean up
}
