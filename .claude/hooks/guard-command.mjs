#!/usr/bin/env node
/**
 * PreToolUse hook: 破壊的操作・本番操作をブロックする。
 *
 * 対象ツール: Bash / PowerShell（どちらも tool_input.command にコマンド文字列が入る）
 * 設定は同ディレクトリの guard.json。
 * ユーザーが明示的に承認した場合のみ、コマンド末尾に承認マーカーを付けて再実行できる。
 */
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GUARDED_TOOLS = ["Bash", "PowerShell"];

function deny(reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(0);
}

try {
  const raw = readFileSync(0, "utf8");
  if (raw.trim()) {
    const input = JSON.parse(raw);
    if (GUARDED_TOOLS.includes(input.tool_name)) {
      const cmd = String((input.tool_input && input.tool_input.command) || "");
      const cfgPath = path.join(HERE, "guard.json");
      if (existsSync(cfgPath)) {
        const cfg = JSON.parse(readFileSync(cfgPath, "utf8"));
        const marker = cfg.approvalMarker || "#APPROVED-BY-USER";
        if (!cmd.includes(marker)) {
          for (const rule of cfg.rules || []) {
            if (new RegExp(rule.pattern, rule.flags || "i").test(cmd)) {
              deny(
                "【ブロック: " + rule.name + "】" + rule.reason + "\n\n" +
                  "この操作はユーザーの明示的な許可なしに実行できません。\n" +
                  "ユーザーに「" + rule.name + "」を実行してよいか確認し、承認された場合のみ" +
                  "コマンド末尾に ' " + marker + "' を付けて再実行してください。\n" +
                  "ユーザーが承認していないのにマーカーを付けることは固く禁止します。\n" +
                  "別のツール(Bash↔PowerShell)に切り替えて回避することも禁止です。"
              );
            }
          }
        }
      }
    }
  }
} catch {
  /* 設定ミスで開発を止めない */
}
process.exit(0);
