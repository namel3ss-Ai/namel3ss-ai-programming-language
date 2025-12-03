const fs = require("fs");
const path = require("path");

function validatePackage() {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  if (!pkg.contributes || !pkg.contributes.languages) {
    throw new Error("Missing language contribution");
  }
  const commands = pkg.contributes.commands || [];
  const hasParse = commands.find((c) => c.command === "namel3ss.runParse");
  const hasDiag = commands.find((c) => c.command === "namel3ss.runDiagnostics");
  if (!hasParse || !hasDiag) {
    throw new Error("Commands not registered");
  }
  console.log("VS Code extension manifest looks valid.");
}

validatePackage();
