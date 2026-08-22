#!/usr/bin/env node
/**
 * guard-command.mjs の回帰テスト。
 *
 *   node .claude/hooks/guard.test.mjs
 *
 * ケースをこのファイルに書いてあるのは、テストコマンド自体を shell に書くと
 * guard が「危険なコマンド」として自分のテストをブロックしてしまうため。
 */
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GUARD = path.join(HERE, "guard-command.mjs");

// [説明, ツール名, コマンド, ブロックされるべきか]
const CASES = [
  // ---- git ----
  ["git reset --hard", "Bash", "git reset --hard HEAD", true],
  ["git -C <path> reset --hard", "Bash", "git -C /c/Users/x/proj reset --hard HEAD", true],
  ["git clean -fd", "Bash", "git clean -fd", true],
  ["git checkout -- <path>", "Bash", "git checkout -- src/app.ts", true],
  ["git restore .", "Bash", "git restore .", true],
  ["git push --force", "Bash", "git push --force origin master", true],
  ["git -C <path> push --force", "Bash", "git -C /c/Users/x/proj push --force", true],
  ["git filter-branch", "Bash", "git filter-branch --tree-filter rm -f secret", true],
  ["git status", "Bash", "git status", false],
  ["git -C <path> status", "Bash", "git -C /c/Users/x/proj status --short", false],
  ["git push (通常)", "Bash", "git push origin master", false],
  ["git log", "Bash", "git log --oneline -10", false],

  // ---- リモート ----
  ["ssh", "Bash", "ssh -i ~/.ssh/k.pem root@203.0.113.9", true],
  ["scp", "Bash", "scp dump.sql root@203.0.113.9:/tmp/", true],

  // ---- HTTP 書き込み ----
  ["curl -X POST 外部", "Bash", "curl -u a:b -X POST http://203.0.113.9/api/v1/trigger", true],
  ["curl --request POST 外部", "Bash", "curl --request POST https://example.com/api", true],
  ["curl --data (暗黙POST)", "Bash", "curl --data '{}' https://example.com/api", true],
  ["curl -d 外部", "Bash", "curl -d @body.json https://example.com/api", true],
  ["curl -F アップロード", "Bash", "curl -F file=@a.zip https://example.com/upload", true],
  ["PS Invoke-RestMethod POST", "PowerShell", "Invoke-RestMethod -Uri https://example.com/api -Method Post", true],
  ["curl GET 外部", "Bash", "curl -u a:b http://203.0.113.9/api/v1/races", false],
  ["curl -X POST localhost", "Bash", "curl -X POST http://localhost:8000/api/v1/races/1/hedge", false],
  ["curl --data localhost", "Bash", "curl --data '{}' http://localhost:8000/api", false],

  // ---- インフラ / DB ----
  ["prod docker compose", "Bash", "docker compose -f docker/docker-compose.prod.yml up -d --build", true],
  ["VPS DB同期", "Bash", "bash sync_jravan_derived_to_vps.sh", true],
  ["alembic downgrade", "Bash", "uv run alembic downgrade -1", true],
  ["dropdb", "Bash", "dropdb kbar", true],
  ["local docker compose", "Bash", "docker compose -f docker/docker-compose.yml --env-file .env up -d", false],
  ["alembic upgrade head", "Bash", "cd backend && uv run alembic upgrade head", false],

  // ---- 認証情報 ----
  ["htpasswd", "Bash", "htpasswd -bc .htpasswd admin pass", true],
  ["gh secret set", "Bash", "gh secret set MY_TOKEN", true],

  // ---- 依存追加 ----
  ["npm install <pkg>", "Bash", "npm install lodash", true],
  ["npm i -D <pkg>", "Bash", "npm i --save-dev @types/lodash", true],
  ["uv add", "Bash", "uv add requests", true],
  ["pip install", "Bash", "pip install requests", true],
  ["npm install (復元)", "Bash", "npm install", false],
  ["npm run dev", "Bash", "npm run dev", false],
  ["npx playwright install", "Bash", "npx playwright install chromium", false],
  ["uv run pytest", "Bash", "uv run pytest -q", false],
  ["uv sync", "Bash", "uv sync", false],

  // ---- 削除 ----
  ["rm -rf /", "Bash", "rm -rf /", true],
  ["rm -rf ./*", "Bash", "rm -rf ./*", true],
  ["rm -rf ../", "Bash", "rm -rf ../", true],
  ["rm -rf $HOME", "Bash", "rm -rf $HOME/stuff", true],
  ["rm -rf ~", "Bash", "rm -rf ~/tmp", true],
  ["rm -rf *", "Bash", "rm -rf *", true],
  ["PS Remove-Item -Recurse *", "PowerShell", "Remove-Item -Recurse -Force .\\*", true],
  ["rm -rf <特定ディレクトリ>", "Bash", "rm -rf node_modules", false],
  ["rm 単一ファイル", "Bash", "rm tmp.txt", false],
  ["rm -rf /tmp/<特定>", "Bash", "rm -rf /tmp/kbar-scratch", false],

  // ---- ツール横断 / 例外 ----
  ["PowerShell経由の git reset --hard", "PowerShell", "git reset --hard HEAD", true],
  ["承認マーカー付き", "Bash", "git reset --hard HEAD #APPROVED-BY-USER", false],
  ["対象外ツール(Read)", "Read", "git reset --hard HEAD", false],
];

let pass = 0;
const failures = [];

for (const [label, tool, command, shouldBlock] of CASES) {
  const payload = JSON.stringify({ tool_name: tool, tool_input: { command } });
  let out = "";
  try {
    out = execFileSync("node", [GUARD], { input: payload, encoding: "utf8" });
  } catch (e) {
    out = String(e.stdout || "");
  }
  const blocked = out.includes('"deny"');
  if (blocked === shouldBlock) {
    pass++;
  } else {
    failures.push(
      `  ${shouldBlock ? "ブロック漏れ" : "誤検知"}: ${label}\n    → ${command}`
    );
  }
}

console.log(`guard 回帰テスト: ${pass}/${CASES.length} 件 pass`);
if (failures.length) {
  console.log("\n失敗:");
  console.log(failures.join("\n"));
  process.exit(1);
}
console.log("すべて期待通り。");
