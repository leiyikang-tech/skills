/**
 * mechanisms-server — HTTP service over the refcode mechanisms knowledge base.
 *
 * Exposes the mechanism DB (curated mechanisms + code anchors + fused real
 * projects + scenes) as a network service so any agent/process can:
 *   - query: GET /mechanisms, GET /mechanisms/<id>, GET /recommend, GET /scenes
 *   - ingest: POST /ingest  (submit an analyzed project to fuse into the DB)
 *   - add scene: POST /scene
 *
 * SQLite WAL gives multi-reader + single-writer concurrency; each ingest is a
 * transactional UPSERT keyed by UNIQUE(mechanism_id, project_name), so the
 * same analysis submitted by many workers dedupes idempotently. Distributed
 * ingest works because the write path never holds a long lock and retries on
 * SQLITE_BUSY via busy_timeout.
 *
 * Run:  bun mechanisms-server.ts [--db path] [--port 8787]
 * The ranking math mirrors mechanisms.py (`_score_mechanism`) so CLI and
 * service agree on recommend output.
 */
import { Database } from "bun:sqlite";

const argv = process.argv.slice(2);
const PORT = Number(process.env.MECH_PORT ?? argv[argv.indexOf("--port") + 1] ?? 8787);
const MECH_DB =
  process.env.MECH_DB ??
  // cross-platform: %USERPROFILE%\.refcode\mechanisms.db on Windows,
  // ~/.refcode/mechanisms.db elsewhere. Override with MECH_DB for any layout.
  (Bun.env.HOME || Bun.env.USERPROFILE || ".") + "/.refcode/mechanisms.db";

// --------------------------------------------------------------------------- #
// DB
// --------------------------------------------------------------------------- #
const db = new Database(MECH_DB);
db.exec("PRAGMA journal_mode=WAL");
db.exec("PRAGMA busy_timeout=5000");
db.exec("PRAGMA foreign_keys=ON");

// --------------------------------------------------------------------------- #
// Ranking (mirrors mechanisms.py: _STOP / _SYNONYMS / _norm_cjk / _tokenize /
//          _cjk_words / _score_mechanism)
// --------------------------------------------------------------------------- #
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
  id: string;
  name: string;
  domain: string;
  domain_name: string;
  definition: string;
  scenes: string;
  maturity: number;
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

// --------------------------------------------------------------------------- #
// Handlers
// --------------------------------------------------------------------------- #
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function listMechanisms(req: Request): Response {
  const u = new URL(req.url);
  const dom = u.searchParams.get("domain") ?? "";
  const rows = db.query(
    `SELECT m.id, m.name, m.domain, m.domain_name, m.maturity,
            (SELECT COUNT(*) FROM implementations i WHERE i.mechanism_id=m.id) AS impls,
            (SELECT COUNT(*) FROM project_instances p WHERE p.mechanism_id=m.id) AS projects
     FROM mechanisms m`,
  ).all() as Array<Record<string, unknown>>;
  const out = dom ? rows.filter((r) => r.domain === dom) : rows;
  return json(out);
}

function showMechanism(req: Request, id: string): Response {
  const m = db.query(
    "SELECT * FROM mechanisms WHERE id=? OR name=?",
  ).get(id, id) as MechRow | null;
  if (!m) return json({ error: `no mechanism '${id}'` }, 404);
  const impls = db.query(
    "SELECT slug,module,sym,line,impl_note FROM implementations WHERE mechanism_id=? ORDER BY slug",
  ).all(m.id);
  const insts = db.query(
    "SELECT project_name, why_worth, analysis_path FROM project_instances WHERE mechanism_id=? ORDER BY project_name",
  ).all(m.id);
  return json({ ...m, implementations: impls, real_world_projects: insts });
}

function recommend(req: Request): Response {
  const u = new URL(req.url);
  const scene = u.searchParams.get("scene") ?? "";
  const k = Math.max(1, Math.min(50, Number(u.searchParams.get("k") ?? 10)));
  if (!scene.trim()) return json({ error: "missing ?scene=" }, 400);
  const rows = db.query(
    "SELECT id,name,domain,domain_name,definition,scenes,maturity FROM mechanisms",
  ).all() as MechRow[];
  const scored: Array<{ score: number; m: MechRow; impls: number; projects: number }> = [];
  for (const m of rows) {
    const s = scoreMechanism(m, scene);
    if (s > 0) {
      const impls = (db.query(
        "SELECT COUNT(*) c FROM implementations WHERE mechanism_id=?",
      ).get(m.id) as { c: number }).c;
      const projects = (db.query(
        "SELECT COUNT(*) c FROM project_instances WHERE mechanism_id=?",
      ).get(m.id) as { c: number }).c;
      scored.push({ score: s, m, impls, projects });
    }
  }
  scored.sort((a, b) => b.score - a.score);
  return json({
    scene,
    top: scored.slice(0, k).map(({ score, m, impls, projects }) => ({
      score,
      id: m.id,
      name: m.name,
      domain: m.domain,
      domain_name: m.domain_name,
      maturity: m.maturity,
      impls,
      projects,
    })),
  });
}

function listScenes(): Response {
  return json(db.query("SELECT * FROM scenes ORDER BY id").all());
}

// POST /ingest — fuse one analyzed project into every mechanism in its domain.
// Transactional UPSERT keyed by UNIQUE(mechanism_id, project_name) -> idempotent.
function ingest(req: Request): Promise<Response> {
  try {
    return req.json().then((body) => {
      const b = body as {
        project_name: string;
        paradigm_id: string;
        why_worth?: string;
        analysis_path?: string;
        source_type?: string;
      };
      if (!b.project_name?.trim() || !b.paradigm_id?.trim()) {
        return json({ error: "body needs project_name + paradigm_id" }, 400);
      }
      const tx = db.transaction(() => {
        const mechs = db.query(
          "SELECT id FROM mechanisms WHERE domain=?",
        ).all(b.paradigm_id) as Array<{ id: string }>;
        let fused = 0;
        for (const m of mechs) {
          const res = db.query(
            `INSERT INTO project_instances
               (mechanism_id, project_name, domain, why_worth, analysis_path, source_type)
             VALUES (?,?,?,?,?,?)
             ON CONFLICT(mechanism_id, project_name) DO UPDATE SET
               why_worth=excluded.why_worth,
               analysis_path=excluded.analysis_path,
               source_type=excluded.source_type`,
          ).run(m.id, b.project_name.trim(), b.paradigm_id,
                b.why_worth ?? "", b.analysis_path ?? "", b.source_type ?? "");
          fused += Number(res.changes);
        }
        return { fused, mechanisms: mechs.length };
      });
      const res = tx();
      return json({ ok: true, ...res, project_name: b.project_name.trim() }, 201);
    });
  } catch (e) {
    return Promise.resolve(json({ error: String(e) }, 500));
  }
}

// POST /scene — add a curated scene (id, description, domain, keywords).
function addScene(req: Request): Promise<Response> {
  try {
    return req.json().then((body) => {
      const b = body as {
        id: string;
        description: string;
        domain?: string;
        keywords?: string;
      };
      if (!b.id?.trim() || !b.description?.trim()) {
        return json({ error: "body needs id + description" }, 400);
      }
      db.query(
        "INSERT OR IGNORE INTO scenes (id, description, domain, keywords) VALUES (?,?,?,?)",
      ).run(b.id.trim(), b.description.trim(), b.domain ?? "", b.keywords ?? "");
      return json({ ok: true, id: b.id.trim() }, 201);
    });
  } catch (e) {
    return Promise.resolve(json({ error: String(e) }, 500));
  }
}

// --------------------------------------------------------------------------- #
// Router
// --------------------------------------------------------------------------- #
const server = Bun.serve({
  port: PORT,
  async fetch(req: Request): Promise<Response> {
    const u = new URL(req.url);
    const p = u.pathname;

    if (req.method === "GET" && p === "/health") {
      return json({ ok: true, db: MECH_DB, mechanisms: (
        db.query("SELECT COUNT(*) c FROM mechanisms").get() as { c: number }
      ).c });
    }
    if (req.method === "GET" && p === "/mechanisms") return listMechanisms(req);
    if (req.method === "GET" && p === "/scenes") return listScenes();
    if (req.method === "GET" && p === "/recommend") return recommend(req);
    if (req.method === "GET" && p.startsWith("/mechanisms/")) {
      const id = decodeURIComponent(p.slice("/mechanisms/".length));
      if (id) return showMechanism(req, id);
    }
    if (req.method === "POST" && p === "/ingest") return ingest(req);
    if (req.method === "POST" && p === "/scene") return addScene(req);

    return json({ error: "not found", routes: ["/health", "/mechanisms", "/mechanisms/<id>", "/recommend?scene=&k=", "/scenes", "POST /ingest", "POST /scene"] }, 404);
  },
});

console.log(`mechanisms-server on http://localhost:${server.port} (db: ${MECH_DB})`);