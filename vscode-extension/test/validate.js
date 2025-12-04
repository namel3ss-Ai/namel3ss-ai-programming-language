const fs = require("fs");
const path = require("path");

function validatePackage() {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  if (!pkg.contributes || !pkg.contributes.languages) {
    throw new Error("Missing language contribution");
  }
  if (!pkg.activationEvents || !pkg.activationEvents.includes("onLanguage:namel3ss")) {
    throw new Error("Missing activation event for namel3ss language");
  }
  const commands = pkg.contributes.commands || [];
  const hasRestart = commands.find((c) => c.command === "namel3ss.restartServer");
  if (!hasRestart) {
    throw new Error("Restart command not registered");
  }
  if (!pkg.contributes.configuration || !pkg.contributes.configuration.properties["namel3ss.lsp.command"]) {
    throw new Error("Configuration for LSP command missing");
  }
  if (pkg.main !== "./dist/extension.js") {
    throw new Error("Main entry should point to dist/extension.js");
  }
  console.log("VS Code extension manifest looks valid.");
}

validatePackage();
