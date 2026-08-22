#!/usr/bin/env node
/**
 * PostToolUse hook: 編集したファイルに対して軽量チェック＋関連テストを実行する。
 *
 * 設定は同ディレクトリの checks.json（プロジェクトごとに生成）。
 * 成功時は無出力。失敗時のみ Claude に additionalContext として結果を返す。
 */
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKIP_DIRS = ["node_modules", ".git", ".next", "__pycache__", ".venv", ".venv32", "dist", "build"];

function readStdin() {
  try {
    return readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

function toPosix(p) {
  return p.replace(/\\/g, "/");
}

function walk(dir, out = [], depth = 0) {
  if (depth > 6 || !existsSync(dir)) return out;
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const e of entries) {
    if (SKIP_DIRS.includes(e)) continue;
    const full = path.join(dir, e);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(full, out, depth + 1);
    else out.push(full);
  }
  return out;
}

const MAX_OUTPUT = 1500; // Claude のコンテキストを汚さないための上限

function run(cmd, cwd, timeoutSec) {
  try {
    execSync(cmd, {
      cwd,
      stdio: "pipe",
      timeout: timeoutSec * 1000,
      encoding: "utf8",
      // Windows の cp932 による文字化け・クラッシュを避ける
      env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
    });
    return null;
  } catch (err) {
    const out = String((err.stdout || "") + (err.stderr || "")).trim();
    const text = out || String(err.message || "unknown error");
    if (text.length <= MAX_OUTPUT) return text;
    // 末尾（サマリが出る側）を優先して残す
    return "…(前略)\n" + text.slice(-MAX_OUTPUT);
  }
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) return;

  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    return;
  }

  const filePath = input && input.tool_input && input.tool_input.file_path;
  if (!filePath) return;

  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();
  const cfgPath = path.join(HERE, "checks.json");
  if (!existsSync(cfgPath)) return;

  let cfg;
  try {
    cfg = JSON.parse(readFileSync(cfgPath, "utf8"));
  } catch {
    return;
  }

  const rel = toPosix(path.relative(projectDir, filePath));
  if (rel.startsWith("..") || path.isAbsolute(rel)) return; // プロジェクト外は対象外

  const base = path.basename(rel).replace(/\.[^.]+$/, "");
  const problems = [];

  for (const rule of cfg.rules || []) {
    if (!new RegExp(rule.match).test(rel)) continue;
    if (rule.exclude && new RegExp(rule.exclude).test(rel)) continue;

    const cwd = path.join(projectDir, rule.cwd || ".");
    if (!existsSync(cwd)) continue;

    const absFile = path.resolve(projectDir, rel);
    const fileForCmd = toPosix(path.relative(cwd, absFile));
    const quoted = JSON.stringify(fileForCmd);

    for (const tpl of rule.commands || []) {
      const cmd = tpl.split("{file}").join(quoted).split("{base}").join(base);
      const failure = run(cmd, cwd, rule.timeout || 120);
      if (failure) {
        problems.push("[FAIL] (" + (rule.cwd || ".") + ") " + cmd + "\n" + failure.slice(-MAX_OUTPUT));
      }
    }

    // 関連テスト
    const rt = rule.relatedTest;
    if (!rt) continue;

    let target = null;
    if (rt.selfPattern && new RegExp(rt.selfPattern).test(rel)) {
      target = fileForCmd; // 編集したのがテストファイル本体
    } else {
      const testRoot = path.join(cwd, rt.dir || "tests");
      if (existsSync(testRoot)) {
        const wanted = (rt.namePattern || "test_{base}").split("{base}").join(base);
        const hit = walk(testRoot).find(
          (f) => path.basename(f).replace(/\.[^.]+$/, "") === wanted
        );
        if (hit) target = toPosix(path.relative(cwd, hit));
      }
    }

    if (target) {
      const cmd = rt.command.split("{test}").join(JSON.stringify(target));
      const failure = run(cmd, cwd, rt.timeout || 180);
      if (failure) {
        problems.push("[FAIL] 関連テスト (" + (rule.cwd || ".") + ") " + cmd + "\n" + failure.slice(-MAX_OUTPUT));
      }
    }
  }

  if (problems.length) {
    const msg = [
      "自動チェックが失敗しました（編集ファイル: " + rel + "）。次に進む前に修正してください。",
      "この失敗は隠さず、最終報告に含めること。",
    ]
      .concat(problems)
      .join("\n\n");
    process.stdout.write(
      JSON.stringify({
        additionalContext: msg,
        systemMessage: "⚠ 自動チェック失敗: " + rel,
      })
    );
  }
}

try {
  main();
} catch {
  /* hook は決して開発を止めない */
}
