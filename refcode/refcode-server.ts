/**
 * refcode-server — remote-first, multi-user storage for the refcode corpus AND
 * the mechanisms knowledge base, in ONE Bun/TS service.
 *
 * Design (remote is the single source of truth; local disk stays small):
 *
 *   refcode corpus
 *     - POST /projects/<slug>/push : receive derived data (project row +
 *       symbol rows + body-window rows) as newline-delimited JSON; the server
 *       upserts them and rebuilds THAT project's trigram FTS in one
 *       transaction. Idempotent per project: re-push overwrites last-write-wins.
 *     - GET /projects/<slug>/manifest : (sha, symbol_count, window_count,
 *       file_count) so a client can VERIFY sync before deleting local data.
 *     - GET /projects : list indexed projects (+ counts).
 *     - GET /query?text=&k=&project= : symbol arm + docs arm + body BM25.
 *     - GET /def?name=&project= : exact symbol lookup.
 *     The remote rebuilds FTS from pushed window TEXT, so clients never send
 *     the 15GB index — only the derived text+symbols (~1.3GB gzipped).
 *
 *   mechanisms knowledge base (reuses mechanisms-server logic)
 *     - GET /recommend?scene=&k=, GET /mechanisms, GET /mechanisms/<id>,
 *       GET /scenes, POST /ingest, POST /scene
 *
 * Concurrency / multi-user:
 *   - SQLite WAL: multi-reader + single-writer; busy_timeout for contention.
 *   - Each project push is ONE transaction (DELETE project rows + batch INSERT
 *     + FTS rebuild via INSERT SELECT) so concurrent pushes of the same slug
 *     serialize cleanly (last-write-wins by transaction ordering).
 *   - All projects are shared globally (slug is the unique key); each pushed
 *     row carries an optional owner for future tenant isolation.
 *
 * Run:  bun refcode-server.ts [--port 8788] [--corpus-db <path>]
 *                                  [--mech-db <path>]
 */
import { Database } from "bun:sqlite";
import { Buffer } from "node:buffer";
import { gunzipSync } from "node:zlib";

const argv = process.argv.slice(2);
const PORT = Number(process.env.REFCODE_PORT ?? argv[argv.indexOf("--port") + 1] ?? 8788);
const home = Bun.env.HOME || Bun.env.USERPROFILE || ".";
const CORPUS_DB =
  process.env.REFCODE_DB ??
  argv[argv.indexOf("--corpus-db") + 1] ??
  home + "/.refcode/remote/refcode.db";
const MECH_DB =
  process.env.MECH_DB ??
  argv[argv.indexOf("--mech-db") + 1] ??
  home + "/.refcode/mechanisms.db";

// --------------------------------------------------------------------------- #
// Corpus schema — mirrors refcode.py's SCHEMA so the remote store is a superset
// (same ref_projects / ref_symbols / ref_body_fts), plus a push_log for sync
// verification and an owner column for future tenant isolation.
// --------------------------------------------------------------------------- #
const CORPUS_SCHEMA = `
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS ref_projects (
  slug             TEXT PRIMARY KEY,
  url              TEXT,
  sha              TEXT,
  licence          TEXT,
  use_policy       TEXT,
  domain           TEXT,
  languages        TEXT,
  ask_for          TEXT,
  dependency_names TEXT,
  status           TEXT DEFAULT 'live',
  quality_grade    TEXT,
  local_path       TEXT,
  bytes            INTEGER,
  files            INTEGER,
  symbols          INTEGER,
  windows          INTEGER,
  indexed_at       TEXT,
  refreshed_at     TEXT,
  owner            TEXT
);

CREATE TABLE IF NOT EXISTS ref_symbols (
  project        TEXT NOT NULL,
  node_id        TEXT NOT NULL,
  kind           TEXT,
  name           TEXT,
  qualified_name TEXT,
  file_path      TEXT,
  language       TEXT,
  start_line     INTEGER,
  end_line       INTEGER,
  signature      TEXT,
  docstring      TEXT,
  owner          TEXT,
  PRIMARY KEY (project, node_id)
);
CREATE INDEX IF NOT EXISTS idx_refsym_name ON ref_symbols(name);
CREATE INDEX IF NOT EXISTS idx_refsym_proj ON ref_symbols(project);
CREATE INDEX IF NOT EXISTS idx_refsym_qual ON ref_symbols(qualified_name);

CREATE VIRTUAL TABLE IF NOT EXISTS ref_body_fts USING fts5(
  project   UNINDEXED,
  file_path,
  language  UNINDEXED,
  win       UNINDEXED,
  line0     UNINDEXED,
  body,
  owner     UNINDEXED,
  tokenize = 'trigram'
);

CREATE TABLE IF NOT EXISTS ref_docs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  slug      TEXT,
  kind      TEXT,
  title     TEXT,
  body      TEXT,
  created_at TEXT,
  owner     TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS ref_docs_fts USING fts5(
  id        UNINDEXED,
  slug      UNINDEXED,
  kind      UNINDEXED,
  title,
  body,
  owner     UNINDEXED,
  tokenize = 'trigram'
);

-- Sync ledger: lets a client verify a push landed before deleting local data.
CREATE TABLE IF NOT EXISTS push_log (
  project       TEXT PRIMARY KEY,
  sha           TEXT,
  symbols       INTEGER,
  windows       INTEGER,
  files         INTEGER,
  owner         TEXT,
  pushed_at     TEXT,
  by_client     TEXT
);
`;

// --------------------------------------------------------------------------- #
// Mechanisms schema (mirrors mechanisms.py) — for the /recommend etc endpoints.
// --------------------------------------------------------------------------- //
const MECH_SCHEMA = `
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS mechanisms (
  id TEXT PRIMARY KEY, name TEXT, domain TEXT, domain_name TEXT,
  definition TEXT, scenes TEXT, pros TEXT, cons TEXT, maturity REAL
);
CREATE TABLE IF NOT EXISTS implementations (
  mechanism_id TEXT, slug TEXT, module TEXT, sym TEXT NOT NULL DEFAULT '',
  line INTEGER, impl_note TEXT, refcode_db TEXT,
  UNIQUE(mechanism_id, slug, module, sym)
);
CREATE TABLE IF NOT EXISTS project_instances (
  mechanism_id TEXT, project_name TEXT, domain TEXT,
  why_worth TEXT, analysis_path TEXT, source_type TEXT,
  UNIQUE(mechanism_id, project_name)
);
CREATE TABLE IF NOT EXISTS scenes (
  id TEXT PRIMARY KEY, description TEXT, domain TEXT, keywords TEXT
);
`;

// --------------------------------------------------------------------------- //
// Ranking (mirrors mechanisms.py: _STOP/_SYNONYMS/_norm_cjk/_score_mechanism)
// --------------------------------------------------------------------------- //
const STOP = new Set([
  "agent", "agents", "llm", "ai", "智能体", "多", "的", "间", "做", "进行",
  "使用", "基于", "一个", "方法", "可以", "如何", "怎么", "两个", "之间",
  "这个", "这些", "那么", "还有", "以及",
]);
const SYNONYMS: Record<string, string> = {
  "通讯": "通信", "通信": "通信", "通讯机制": "通信",
  "上下文": "语境", "语境": "语境",
  "记忆": "记忆", "回忆": "记忆",
  "工具": "工具", "调用": "调用",
  "推理": "推理", "思考": "推理",
  "协作": "协作", "合作": "协作", "协同": "协作",
  "安全": "安全", "凭证": "认证",
};
const CJK_STOP = new Set(["智能", "优化", "实现", "能力", "多智", "两个"]);

function normCjk(words: Set<string>): Set<string> {
  return new Set([...words].map((w) => SYNONYMS[w] ?? w));
}
function tokenize(text: string): Set<string> {
  const out = new Set<string>();
  for (const t of text.toLowerCase().match(/[a-zA-Z0-9]+/g) ?? []) {
    if (t.length >= 2 && !STOP.has(t)) out.add(t);
  }
  return out;
}
function cjkWords(text: string): Set<string> {
  const out = new Set<string>();
  for (const run of text.match(/[\u4e00-\u9fff]{2,}/g) ?? []) {
    for (let i = 0; i < run.length - 1; i++) {
      const w = run.slice(i, i + 2);
      if (!STOP.has(w) && !CJK_STOP.has(w)) out.add(w);
    }
  }
  return out;
}
interface MechRow {
  id: string; name: string; domain: string; domain_name: string;
  definition: string; scenes: string; maturity: number;
}
function scoreMechanism(m: MechRow, sceneText: string): number {
  const sceneAscii = tokenize(sceneText);
  const sceneCjk = normCjk(cjkWords(sceneText));
  const mechAscii = tokenize(`${m.name} ${m.definition} ${m.scenes}`);
  const mechCjk = normCjk(cjkWords(`${m.name} ${m.definition} ${m.scenes}`));
  const interA = [...sceneAscii].filter((t) => mechAscii.has(t)).length;
  const unionA = new Set([...sceneAscii, ...mechAscii]).size;
  const interC = [...sceneCjk].filter((t) => mechCjk.has(t)).length;
  const unionC = new Set([...sceneCjk, ...mechCjk]).size;
  const fitA = unionA > 0 ? interA / unionA : 0;
  const fitC = unionC > 0 ? interC / unionC : 0;
  const hasCjk = sceneCjk.size > 0;
  const fit = hasCjk ? fitC * 0.65 + fitA * 0.35 : fitA;
  if (fit <= 0) return 0;
  const maturity = Number(m.maturity ?? 0);
  return Math.round((fit * 0.85 + maturity * 0.15) * 10000) / 10000;
}

// --------------------------------------------------------------------------- //
// DB setup
// --------------------------------------------------------------------------- //
const corpus = new Database(CORPUS_DB);
corpus.exec("PRAGMA journal_mode=WAL");
corpus.exec("PRAGMA busy_timeout=10000");
corpus.exec("PRAGMA foreign_keys=ON");
corpus.exec(CORPUS_SCHEMA);

let mech: Database | null = null;
try {
  mech = new Database(MECH_DB);
  mech.exec("PRAGMA journal_mode=WAL");
  mech.exec("PRAGMA busy_timeout=10000");
  mech.exec(MECH_SCHEMA);
} catch (e) {
  console.warn(`mechanisms db unavailable (${MECH_DB}): ${String(e)}; /recommend etc disabled`);
  mech = null;
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
function now(): string {
  return new Date().toISOString();
}

// --------------------------------------------------------------------------- //
// Corpus: project push (the core write path)
// --------------------------------------------------------------------------- //
// Body is newline-delimited JSON. Line kinds (first field "t"):
//   {t:"project", slug,url,sha,licence,use_policy,domain,languages,ask_for,
//            dependency_names,bytes,files,symbols,windows}
//   {t:"symbol", project,node_id,kind,name,qualified_name,file_path,language,
//              start_line,end_line,signature,docstring}
//   {t:"window", project,file_path,language,win,line0,body}
//   {t:"end",    project,sha,symbols,windows,files,client}
async function pushProject(req: Request, slug: string, owner: string): Promise<Response> {
  const u = new URL(req.url);
  const client = u.searchParams.get("client") ?? "unknown";
  try {
    const body = req.body;
    if (!body) return json({ error: "empty body" }, 400);

    // Read the body stream fully, then run ONE transaction that wipes the
    // project's prior rows and inserts the pushed derived data (symbols +
    // window text), so a crash mid-push leaves the project untouched. The
    // trigram FTS is rebuilt from the pushed window text by the INSERT.
    const reader = (req.body as ReadableStream<Uint8Array>).getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      total += value.byteLength;
      if (total > 4 * 1024 * 1024 * 1024) {
        await reader.cancel();
        return json({ error: "body too large (>4GB); push in per-project batches" }, 413);
      }
    }
    const encoding = req.headers.get("content-encoding") ?? "";
    const rawBytes = Buffer.concat(chunks);
    let text: string;
    if (encoding.includes("gzip")) {
      text = gunzipSync(rawBytes).toString("utf-8");
    } else {
      text = new TextDecoder().decode(rawBytes);
    }

    const stats = txFromText(slug, owner, client, text);
    return json({ ok: true, slug, ...stats }, 201);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
}

// Executes the push transaction from a decoded text body.
function txFromText(
  slug: string, owner: string, client: string, text: string,
): { nsym: number; nwin: number; nfiles: number; sha: string; windows?: number } {
  const insSym = corpus.query(
    `INSERT OR REPLACE INTO ref_symbols
       (project,node_id,kind,name,qualified_name,file_path,language,
        start_line,end_line,signature,docstring,owner)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`,
  );
  const insWin = corpus.query(
    `INSERT INTO ref_body_fts
       (project,file_path,language,win,line0,body,owner)
     VALUES (?,?,?,?,?,?,?)`,
  );
  const insProj = corpus.query(
    `INSERT OR REPLACE INTO ref_projects
       (slug,url,sha,licence,use_policy,domain,languages,ask_for,
        dependency_names,status,local_path,bytes,files,symbols,windows,
        indexed_at,owner)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
  );
  const insLog = corpus.query(
    `INSERT OR REPLACE INTO push_log
       (project,sha,symbols,windows,files,owner,pushed_at,by_client)
     VALUES (?,?,?,?,?,?,?,?)`,
  );

  const tx = corpus.transaction(() => {
    corpus.query("DELETE FROM ref_symbols WHERE project=?").run(slug);
    corpus.query("DELETE FROM ref_body_fts WHERE project=?").run(slug);
    corpus.query("DELETE FROM ref_projects WHERE slug=?").run(slug);

    let proj: Record<string, unknown> | null = null;
    let nsym = 0, nwin = 0, nfiles = 0, sha = "";
    for (const line of text.split("\n")) {
      const t = line.trim();
      if (!t) continue;
      let rec: Record<string, unknown>;
      try {
        rec = JSON.parse(t);
      } catch {
        continue; // tolerate a malformed line; skip it
      }
      switch (rec.t) {
        case "project":
          proj = rec;
          insProj.run(
            rec.slug ?? slug, rec.url ?? "", rec.sha ?? "", rec.licence ?? "",
            rec.use_policy ?? "", rec.domain ?? "", rec.languages ?? "",
            rec.ask_for ?? "", rec.dependency_names ?? "", "live", "",
            rec.bytes ?? 0, rec.files ?? 0, rec.symbols ?? 0, rec.windows ?? 0,
            now(), owner,
          );
          break;
        case "symbol":
          insSym.run(
            rec.project ?? slug, rec.node_id, rec.kind ?? "", rec.name ?? "",
            rec.qualified_name ?? "", rec.file_path ?? "", rec.language ?? "",
            rec.start_line ?? 0, rec.end_line ?? 0, rec.signature ?? "",
            rec.docstring ?? "", owner,
          );
          nsym++;
          break;
        case "window":
          insWin.run(
            rec.project ?? slug, rec.file_path ?? "", rec.language ?? "",
            rec.win ?? 0, rec.line0 ?? 0, rec.body ?? "", owner,
          );
          nwin++;
          break;
        case "end":
          sha = String(rec.sha ?? "");
          nfiles = Number(rec.files ?? 0);
          break;
      }
    }
    // Manifest stats: prefer the end-line counts; fall back to counted rows.
    const symCount = nsym > 0 ? nsym : (proj?.symbols as number) ?? 0;
    const winCount = nwin > 0 ? nwin : (proj?.windows as number) ?? 0;
    const fileCount = nfiles > 0 ? nfiles : (proj?.files as number) ?? 0;
    insLog.run(slug, sha, symCount, winCount, fileCount, owner, now(), client);
    return { nsym, nwin, nfiles, sha, windows: winCount };
  });
  return tx();
}

// GET /projects/<slug>/manifest — verify a push landed before local cleanup.
// Reports ACTUAL counted rows (not the client-declared symbols/windows in
// ref_projects) so a client can truly verify sync before deleting local data.
function projectManifest(slug: string): Response {
  const p = corpus.query(
    "SELECT slug,url,sha,domain,status,files,symbols,windows,indexed_at FROM ref_projects WHERE slug=?",
  ).get(slug) as Record<string, unknown> | null;
  if (!p) return json({ error: `project '${slug}' not found` }, 404);
  const actual = corpus.query(
    `SELECT
       (SELECT COUNT(*) FROM ref_symbols s WHERE s.project=?) AS sym_actual,
       (SELECT COUNT(*) FROM ref_body_fts w WHERE w.project=?) AS win_actual`,
  ).get(slug, slug) as { sym_actual: number; win_actual: number };
  const log = corpus.query(
    "SELECT sha,symbols,windows,files,pushed_at,by_client FROM push_log WHERE project=?",
  ).get(slug) as Record<string, unknown> | null;
  return json({
    project: { ...p, symbols: actual.sym_actual, windows: actual.win_actual },
    last_push: log,
  });
}

function listProjects(): Response {
  const rows = corpus.query(
    `SELECT p.slug,p.domain,p.languages,p.files,p.symbols,p.windows,p.indexed_at,
            (SELECT COUNT(*) FROM ref_symbols s WHERE s.project=p.slug) AS sym_actual
     FROM ref_projects p ORDER BY p.slug`,
  ).all();
  return json(rows);
}

// --------------------------------------------------------------------------- //
// Corpus: query (symbol arm + docs arm + body BM25) — mirrors cmd_query
// --------------------------------------------------------------------------- //
function queryText(text: string): string {
  const toks = text.match(/[A-Za-z0-9_]+/g) ?? [];
  const ascii = toks.slice(0, 24).map((t) => `"${t}"`).join(" OR ");
  const cjk = (text.match(/[\u4e00-\u9fff]+/g) ?? []).slice(0, 24)
    .map((c) => `"${c}"`).join(" ");
  return [ascii, cjk].filter(Boolean).join(" OR ");
}

function doQuery(u: URL): Response {
  const q = u.searchParams.get("text") ?? "";
  const k = Math.max(1, Math.min(50, Number(u.searchParams.get("k") ?? 10)));
  const projFilter = u.searchParams.get("project") ?? "";
  const hits: Array<Record<string, unknown>> = [];

  const firstTok = (q.match(/[A-Za-z0-9_]+/g) ?? [q])[0];
  if (firstTok) {
    const like = `%${firstTok}%`;
    let sql =
      "SELECT project,file_path,kind,name,signature,start_line,end_line FROM ref_symbols WHERE (name=? OR name LIKE ?) ";
    const params: unknown[] = [firstTok, like];
    if (projFilter) { sql += "AND project=? "; params.push(projFilter); }
    sql += "ORDER BY (name=?) DESC, length(name) LIMIT ?";
    params.push(firstTok, k);
    for (const r of corpus.query(sql).all(...params)) {
      hits.push({
        arm: "symbol", ...r, score: 1000.0,
      });
    }
  }

  // docs arm (design/mechanism level) — ranked above body hits
  const mq = queryText(q);
  if (mq) {
    try {
      let sql =
        "SELECT id,slug,kind,title,body,bm25(ref_docs_fts) AS s FROM ref_docs_fts WHERE ref_docs_fts MATCH ? ";
      const params: unknown[] = [mq];
      if (projFilter) { sql += "AND slug=? "; params.push(projFilter); }
      sql += "ORDER BY s LIMIT ?";
      params.push(k);
      for (const r of corpus.query(sql).all(...params)) {
        hits.push({
          arm: "doc", project: r.slug, file: "ref_docs", line: 0,
          kind: r.kind ?? "note", name: r.title ?? r.slug,
          snippet: (r.body as string).slice(0, 240).replace(/\n/g, " "),
          score: 100.0,
        });
      }
    } catch {
      /* docs FTS unavailable — skip */
    }
  }

  // body BM25 arm — only if not enough doc/symbol hits already
  const highHits = hits.filter((h) => h.arm !== "body").length;
  if (highHits < k && mq) {
    try {
      let sql =
        "SELECT project,file_path,language,win,line0,body,bm25(ref_body_fts) AS s FROM ref_body_fts WHERE ref_body_fts MATCH ? ";
      const params: unknown[] = [mq];
      if (projFilter) { sql += "AND project=? "; params.push(projFilter); }
      sql += "ORDER BY s LIMIT ?";
      params.push(k);
      for (const r of corpus.query(sql).all(...params)) {
        hits.push({
          arm: "body", ...r,
          snippet: (r.body as string).slice(0, 240).replace(/\n/g, " "),
        });
      }
    } catch {
      /* body FTS unavailable — skip */
    }
  }

  // sort: doc first, then symbol, then body (bm25 ascending)
  const rankOrder: Record<string, number> = { doc: 0, symbol: 1, body: 2 };
  hits.sort((a, b) => {
    const ra = rankOrder[a.arm as string] ?? 3;
    const rb = rankOrder[b.arm as string] ?? 3;
    if (ra !== rb) return ra - rb;
    return Number(a.score) - Number(b.score);
  });
  return json({ text: q, top: hits.slice(0, k) });
}

function doDef(u: URL): Response {
  const name = u.searchParams.get("name") ?? "";
  const projFilter = u.searchParams.get("project") ?? "";
  if (!name) return json({ error: "missing ?name=" }, 400);
  let sql =
    "SELECT project,file_path,kind,name,signature,start_line,end_line,docstring FROM ref_symbols WHERE name=? ";
  const params: unknown[] = [name];
  if (projFilter) { sql += "AND project=? "; params.push(projFilter); }
  sql += "ORDER BY project LIMIT 50";
  return json(dbAll(corpus, sql, params));
}

// --------------------------------------------------------------------------- //
// Mechanisms endpoints (mirror mechanisms-server.ts)
// --------------------------------------------------------------------------- //
function mechList(u: URL): Response {
  if (!mech) return json({ error: "mechanisms db unavailable" }, 503);
  const dom = u.searchParams.get("domain") ?? "";
  let sql =
    `SELECT m.id,m.name,m.domain,m.domain_name,m.maturity,
            (SELECT COUNT(*) FROM implementations i WHERE i.mechanism_id=m.id) AS impls,
            (SELECT COUNT(*) FROM project_instances p WHERE p.mechanism_id=m.id) AS projects
     FROM mechanisms m`;
  const params: unknown[] = [];
  if (dom) { sql += " WHERE m.domain=?"; params.push(dom); }
  return json(mech.query(sql).all(...params));
}
function mechShow(id: string): Response {
  if (!mech) return json({ error: "mechanisms db unavailable" }, 503);
  const m = mech.query("SELECT * FROM mechanisms WHERE id=? OR name=?").get(id, id);
  if (!m) return json({ error: `no mechanism '${id}'` }, 404);
  const impls = mech.query(
    "SELECT slug,module,sym,line,impl_note FROM implementations WHERE mechanism_id=? ORDER BY slug",
  ).all(id);
  const insts = mech.query(
    "SELECT project_name,why_worth,analysis_path FROM project_instances WHERE mechanism_id=? ORDER BY project_name",
  ).all(id);
  return json({ ...m, implementations: impls, real_world_projects: insts });
}
function mechRecommend(u: URL): Response {
  if (!mech) return json({ error: "mechanisms db unavailable" }, 503);
  const scene = u.searchParams.get("scene") ?? "";
  const k = Math.max(1, Math.min(50, Number(u.searchParams.get("k") ?? 10)));
  if (!scene.trim()) return json({ error: "missing ?scene=" }, 400);
  const rows = mech.query(
    "SELECT id,name,domain,domain_name,definition,scenes,maturity FROM mechanisms",
  ).all() as MechRow[];
  const scored: Array<{ score: number; m: MechRow; impls: number; projects: number }> = [];
  for (const m of rows) {
    const s = scoreMechanism(m, scene);
    if (s > 0) {
      const impls = (mech.query(
        "SELECT COUNT(*) c FROM implementations WHERE mechanism_id=?",
      ).get(m.id) as { c: number }).c;
      const projects = (mech.query(
        "SELECT COUNT(*) c FROM project_instances WHERE mechanism_id=?",
      ).get(m.id) as { c: number }).c;
      scored.push({ score: s, m, impls, projects });
    }
  }
  scored.sort((a, b) => b.score - a.score);
  return json({
    scene,
    top: scored.slice(0, k).map(({ score, m, impls, projects }) => ({
      score, id: m.id, name: m.name, domain: m.domain,
      domain_name: m.domain_name, maturity: m.maturity, impls, projects,
    })),
  });
}
function mechScenes(): Response {
  if (!mech) return json({ error: "mechanisms db unavailable" }, 503);
  return json(mech.query("SELECT * FROM scenes ORDER BY id").all());
}
async function mechIngest(req: Request): Promise<Response> {
  if (!mech) return json({ error: "mechanisms db unavailable" }, 503);
  try {
    const b = (await req.json()) as {
      project_name?: string; paradigm_id?: string; why_worth?: string;
      analysis_path?: string; source_type?: string;
    };
    if (!b.project_name?.trim() || !b.paradigm_id?.trim()) {
      return json({ error: "body needs project_name + paradigm_id" }, 400);
    }
    const tx = mech.transaction(() => {
      const mechs = mech.query("SELECT id FROM mechanisms WHERE domain=?").all(b.paradigm_id);
      let fused = 0;
      for (const m of mechs) {
        const res = mech.query(
          `INSERT INTO project_instances
             (mechanism_id,project_name,domain,why_worth,analysis_path,source_type)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(mechanism_id,project_name) DO UPDATE SET
             why_worth=excluded.why_worth, analysis_path=excluded.analysis_path,
             source_type=excluded.source_type`,
        ).run(m.id, b.project_name.trim(), b.paradigm_id, b.why_worth ?? "",
              b.analysis_path ?? "", b.source_type ?? "");
        fused += Number(res.changes);
      }
      return { fused, mechanisms: mechs.length };
    });
    const res = tx();
    return json({ ok: true, ...res, project_name: b.project_name.trim() }, 201);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
}
async function mechAddScene(req: Request): Promise<Response> {
  if (!mech) return json({ error: "mechanisms db unavailable" }, 503);
  try {
    const b = (await req.json()) as {
      id?: string; description?: string; domain?: string; keywords?: string;
    };
    if (!b.id?.trim() || !b.description?.trim()) {
      return json({ error: "body needs id + description" }, 400);
    }
    mech.query(
      "INSERT OR IGNORE INTO scenes (id,description,domain,keywords) VALUES (?,?,?,?)",
    ).run(b.id.trim(), b.description.trim(), b.domain ?? "", b.keywords ?? "");
    return json({ ok: true, id: b.id.trim() }, 201);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
}

// --------------------------------------------------------------------------- //
// Router
// --------------------------------------------------------------------------- //
const server = Bun.serve({
  port: PORT,
  hostname: process.env.REFCODE_HOSTNAME ?? "0.0.0.0",
  async fetch(req: Request): Promise<Response> {
    const u = new URL(req.url);
    const p = u.pathname;
    const owner = u.searchParams.get("owner") ?? "public";

    if (req.method === "GET" && p === "/health") {
      const mechCount = mech ? (mech.query("SELECT COUNT(*) c FROM mechanisms").get() as { c: number }).c : 0;
      return json({
        ok: true,
        corpus_db: CORPUS_DB,
        mechanisms_db: MECH_DB,
        projects: (corpus.query("SELECT COUNT(*) c FROM ref_projects").get() as { c: number }).c,
        mechanisms: mechCount,
      });
    }

    // corpus
    if (req.method === "POST" && p.startsWith("/projects/") && p.endsWith("/push")) {
      const slug = decodeURIComponent(p.slice("/projects/".length, p.length - "/push".length));
      if (slug) return pushProject(req, slug, owner);
    }
    if (req.method === "GET" && p.startsWith("/projects/") && p.endsWith("/manifest")) {
      const slug = decodeURIComponent(p.slice("/projects/".length, p.length - "/manifest".length));
      if (slug) return projectManifest(slug);
    }
    if (req.method === "GET" && p === "/projects") return listProjects();
    if (req.method === "GET" && p === "/query") return doQuery(u);
    if (req.method === "GET" && p === "/def") return doDef(u);

    // mechanisms
    if (req.method === "GET" && p === "/mechanisms") return mechList(u);
    if (req.method === "GET" && p === "/scenes") return mechScenes();
    if (req.method === "GET" && p === "/recommend") return mechRecommend(u);
    if (req.method === "GET" && p.startsWith("/mechanisms/")) {
      const id = decodeURIComponent(p.slice("/mechanisms/".length));
      if (id) return mechShow(id);
    }
    if (req.method === "POST" && p === "/ingest") return mechIngest(req);
    if (req.method === "POST" && p === "/scene") return mechAddScene(req);

    return json({
      error: "not found",
      routes: [
        "GET /health", "POST /projects/<slug>/push", "GET /projects/<slug>/manifest",
        "GET /projects", "GET /query?text=&k=&project=", "GET /def?name=&project=",
        "GET /mechanisms", "GET /mechanisms/<id>", "GET /recommend?scene=&k=",
        "GET /scenes", "POST /ingest", "POST /scene",
      ],
    }, 404);
  },
});

console.log(
  `refcode-server on http://localhost:${server.port}\n  corpus: ${CORPUS_DB}\n  mechanisms: ${MECH_DB}`,
);

function dbAll(db: Database, sql: string, params: unknown[]) {
  return db.query(sql).all(...params);
}