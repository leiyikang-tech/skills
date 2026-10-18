#!/usr/bin/env python3
"""refcode - extract, classify, register and query reference code across projects.

The mechanism is XERJ's "repo -> retrieval documents" pipeline reduced to its
portable core:

  extract   one source file -> one doc {language, symbols[], defs, body}
            (tree-sitter AST; per-language ``TAGS_QUERY`` where the grammar
            ships one, else a generic definition-node heuristic)
  chunk     file body -> line-aligned ~800-char windows (passage windows)
  classify  project -> {languages, domain, dependency_names}
  register  a project -> a pinned corpus row (url + 40-hex sha + licence)
  query     BM25 over body windows (FTS5) + exact symbol lookup, defs first
  route     a *target* repo's lockfiles -> which corpora answer it

Storage: one self-contained SQLite file (FTS5 for BM25). No server, no daemon.
Run ``refcode.venv`` python via the ``refcode`` launcher next to this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Schema (single source of truth; references/refcode.sql mirrors it)
# --------------------------------------------------------------------------- #
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- corpus registry: the shareable / pinnable / reviewable artifact
-- (= XERJ corpus.json equivalent). Contains NO source, only pointers.
CREATE TABLE IF NOT EXISTS ref_projects (
  slug             TEXT PRIMARY KEY,
  url              TEXT,
  sha              TEXT,              -- 40-hex pinned commit, NULL for local dirs
  licence          TEXT,
  use_policy       TEXT,              -- adapt-with-attribution | approach-only | mixed
  domain           TEXT,              -- classified domain (heuristic, see docs)
  languages        TEXT,              -- JSON array
  ask_for          TEXT,
  dependency_names TEXT,              -- JSON array of crate/npm/go/pypi names
  status           TEXT DEFAULT 'live',
  quality_grade    TEXT,
  local_path       TEXT,
  bytes            INTEGER,
  files            INTEGER,
  symbols          INTEGER,
  windows          INTEGER,
  indexed_at       TEXT,
  refreshed_at     TEXT
);

-- symbols across all projects: the "defs" arm (exact + prefix lookup)
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
  PRIMARY KEY (project, node_id)
);
CREATE INDEX IF NOT EXISTS idx_refsym_name  ON ref_symbols(name);
CREATE INDEX IF NOT EXISTS idx_refsym_proj  ON ref_symbols(project);
CREATE INDEX IF NOT EXISTS idx_refsym_qual  ON ref_symbols(qualified_name);

-- body windows: the "body" arm (FTS5 => BM25 for free)
CREATE VIRTUAL TABLE IF NOT EXISTS ref_body_fts USING fts5(
  project   UNINDEXED,
  file_path,
  language  UNINDEXED,
  win       UNINDEXED,
  line0     UNINDEXED,
  body,
  tokenize = 'unicode61'
);

-- docs about corpora / projects (mirrors analysis.db's analysis_docs shape)
CREATE TABLE IF NOT EXISTS ref_docs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  slug      TEXT,
  kind      TEXT,
  title     TEXT,
  body      TEXT,
  created_at TEXT
);
"""

# --------------------------------------------------------------------------- #
# Grammar registry:  language -> (module_name, getter_attr)
# getter_attr is called if present (``language`` or ``language_typescript``...)
# --------------------------------------------------------------------------- #
GRAMMARS: dict[str, tuple[str, str]] = {
    "python":     ("tree_sitter_python", "language"),
    "rust":       ("tree_sitter_rust", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx":        ("tree_sitter_typescript", "language_tsx"),
    "go":         ("tree_sitter_go", "language"),
    "java":       ("tree_sitter_java", "language"),
    "c":          ("tree_sitter_c", "language"),
    "cpp":        ("tree_sitter_cpp", "language"),
    "ruby":       ("tree_sitter_ruby", "language"),
    "php":        ("tree_sitter_php", "language_php"),
    "c_sharp":    ("tree_sitter_c_sharp", "language"),
    "bash":       ("tree_sitter_bash", "language"),
    "scala":      ("tree_sitter_scala", "language"),
    "haskell":    ("tree_sitter_haskell", "language"),
    "kotlin":     ("tree_sitter_kotlin", "language"),
    "swift":      ("tree_sitter_swift", "language"),
    "lua":        ("tree_sitter_lua", "language"),
    "elixir":     ("tree_sitter_elixir", "language"),
    "json":       ("tree_sitter_json", "language"),
    "yaml":       ("tree_sitter_yaml", "language"),
    "toml":       ("tree_sitter_toml", "language"),
    "html":       ("tree_sitter_html", "language"),
    "css":        ("tree_sitter_css", "language"),
    "sql":        ("tree_sitter_sql", "language"),
    "markdown":   ("tree_sitter_markdown", "language"),
}

EXT_TO_LANG = {
    ".py": "python", ".pyi": "python",
    ".rs": "rust",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".rb": "ruby", ".rake": "ruby",
    ".php": "php",
    ".cs": "c_sharp",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash",
    ".scala": "scala", ".sc": "scala",
    ".hs": "haskell", ".lhs": "haskell",
    ".kt": "kotlin", ".kts": "kotlin",
    ".swift": "swift",
    ".lua": "lua",
    ".ex": "elixir", ".exs": "elixir",
    ".json": "json", ".jsonc": "json",
    ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css",
    ".sql": "sql",
    ".md": "markdown", ".markdown": "markdown",
}
# languages whose files are data/markup, not code -> body-only (no symbol extraction)
DATA_LANGS = {"json", "yaml", "toml", "html", "css", "markdown"}

# fallback definition heuristic (used only when the grammar ships no TAGS_QUERY)
_DEF_HINTS = (
    "function", "method", "class", "struct", "enum", "interface", "trait",
    "impl", "module", "namespace", "package", "object", "protocol", "record",
    "type", "const", "static", "var", "macro", "def", "union", "annotation",
    "constructor", "property", "extension",
)
_KIND_MAP = (
    ("function", "function"), ("method", "method"), ("constructor", "constructor"),
    ("class", "class"), ("struct", "struct"), ("enum", "enum"),
    ("interface", "interface"), ("trait", "trait"), ("impl", "impl"),
    ("module", "module"), ("namespace", "module"), ("package", "module"),
    ("object", "object"), ("protocol", "protocol"), ("record", "record"),
    ("type_alias", "type"), ("type", "type"), ("const", "const"),
    ("static", "static"), ("var", "variable"), ("let", "variable"),
    ("macro", "macro"), ("def", "definition"), ("union", "union"),
    ("property", "property"), ("extension", "extension"),
)

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "target", "dist", "build", "out",
    "vendor", "third_party", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".tox", ".idea", ".vscode", "coverage",
    ".codegraph", ".next", ".nuxt", ".cache", "bazel-out", "Pods", "DerivedData",
}
SKIP_FILE_RE = re.compile(r"(\.min\.(js|css)$|\.map$|\.lock$|package-lock\.json$|"
                          r"Cargo\.lock$|yarn\.lock$|pnpm-lock\.yaml$|\.snap$|"
                          r"\.(png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot|pdf|zip|"
                          r"gz|tgz|bz2|xz|7z|so|dylib|dll|a|o|bin|exe|wasm|pyc|class)$)", re.I)
MAX_FILE_BYTES = 2 * 1024 * 1024      # XERJ CODE_CAP
WINDOW_CHARS = 800                    # XERJ passage window
WINDOW_OVERLAP = 80


# --------------------------------------------------------------------------- #
# tree-sitter extraction
# --------------------------------------------------------------------------- #
class Extractor:
    def __init__(self) -> None:
        self._mods: dict[str, tuple] = {}
        self._parsers: dict[str, object] = {}
        self._tagqueries: dict[str, object] = {}
        self.available = True
        try:
            from tree_sitter import Language, Parser, Query  # noqa: F401
        except Exception:
            self.available = False

    def _load(self, lang: str):
        if lang in self._mods:
            return self._mods[lang]
        mod_name, getter = GRAMMARS[lang]
        import importlib
        from tree_sitter import Language, Parser
        mod = importlib.import_module(mod_name)
        get = getattr(mod, getter, None)
        if get is None:
            for cand in dir(mod):
                if cand == getter or cand.startswith("language"):
                    get = getattr(mod, cand)
                    break
        language = Language(get())
        parser = Parser(language)
        self._mods[lang] = (mod, language, parser)
        self._parsers[lang] = parser
        if lang not in self._tagqueries:
            tq = getattr(mod, "TAGS_QUERY", None)
            if tq:
                try:
                    from tree_sitter import Query
                    self._tagqueries[lang] = Query(language, tq)
                except Exception:
                    self._tagqueries[lang] = None
            else:
                self._tagqueries[lang] = None
        return self._mods[lang]

    def detect(self, path: str | Path, head: bytes | None = None) -> str | None:
        p = Path(path)
        lang = EXT_TO_LANG.get(p.suffix.lower())
        if lang:
            return lang
        if p.name in ("Dockerfile", "Makefile", "CMakeLists.txt"):
            return "bash" if p.name != "CMakeLists.txt" else "bash"
        if head and head.startswith(b"#!"):
            first = head.split(b"\n", 1)[0].lower()
            for k, v in ((b"python", "python"), (b"bash", "bash"), (b"sh", "bash"),
                         (b"ruby", "ruby"), (b"node", "javascript"), (b"php", "php"),
                         (b"perl", "bash")):
                if k in first:
                    return v
        return None

    def symbols(self, text: str, lang: str) -> list[dict]:
        """Return [{name, kind, line, end_line, signature}] (1-based lines)."""
        if not self.available or lang in DATA_LANGS or lang not in GRAMMARS:
            return []
        try:
            mod, language, parser = self._load(lang)
        except Exception:
            return []
        src = text.encode("utf-8", "replace")
        tree = parser.parse(src)

        out: list[dict] = []
        seen: set[tuple[int, str]] = set()

        def emit(node, kind: str, name_node=None):
            nm = name_node
            if nm is None:
                nm = node.child_by_field_name("name")
            if nm is None:
                return
            try:
                name = bytes(nm.text).decode("utf-8", "replace")
            except Exception:
                return
            if not name or len(name) > 200:
                return
            key = (node.start_point[0], name)
            if key in seen:
                return
            seen.add(key)
            first = bytes(node.text).decode("utf-8", "replace").splitlines()
            sig = (first[0].strip() if first else "")[:200]
            out.append({
                "name": name,
                "kind": kind,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "signature": sig,
            })

        # 1) grammar-provided TAGS_QUERY (definitions + names, paired per match)
        tq = self._tagqueries.get(lang)
        if tq is not None:
            try:
                from tree_sitter import QueryCursor
                cur = QueryCursor(tq)
                for _pat, caps in cur.matches(tree.root_node):
                    names = caps.get("name") or []
                    for capname, nodes in caps.items():
                        if not capname.startswith("definition."):
                            continue
                        kind = capname.split(".", 1)[1].split(".")[0] or "definition"
                        for i, node in enumerate(nodes):
                            nn = names[i] if i < len(names) else None
                            emit(node, kind, nn)
                if out:
                    return out
            except Exception:
                pass

        # 2) generic fallback: named nodes whose type looks like a definition
        def walk(node):
            t = node.type
            if any(h in t for h in _DEF_HINTS) and node.child_by_field_name("name") is not None:
                kind = next((k for pat, k in _KIND_MAP if pat in t), "definition")
                emit(node, kind)
                return  # don't descend into a definition to avoid nested dupes
            for ch in node.children:
                walk(ch)

        try:
            walk(tree.root_node)
        except Exception:
            pass
        return out


# --------------------------------------------------------------------------- #
# chunking
# --------------------------------------------------------------------------- #
def windows(text: str) -> list[tuple[int, str]]:
    """Line-aligned ~WINDOW_CHARS windows -> [(line0, window_text)]."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    size = 0
    start = 1
    for i, ln in enumerate(text.splitlines(), 1):
        buf.append(ln)
        size += len(ln) + 1
        if size >= WINDOW_CHARS:
            out.append((start, "\n".join(buf)))
            buf, size, start = [], 0, i + 1
    if buf:
        out.append((start, "\n".join(buf)))
    return out


# --------------------------------------------------------------------------- #
# classify
# --------------------------------------------------------------------------- #
DOMAIN_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("search-engine", ("search", "lucene", "tantivy", "elasticsearch", "solr",
                       "bm25", "inverted", "clickhouse")),
    ("vector-db", ("qdrant", "hnsw", "faiss", "milvus", "usearch", "annoy",
                   "vector", "embedding", "pgvector", "lancedb")),
    ("database", ("sqlite", "rocksdb", "sled", "fjall", "redb", "leveldb",
                  "postgres", "storage", "wal", "lsm", "kv")),
    ("ml-ai", ("torch", "tensorflow", "transformers", "llm", "bert", "onnx",
               "langchain", "openai", "inference", "neural")),
    ("web-framework", ("axum", "actix", "express", "fastapi", "django", "flask",
                       "next", "react", "vue", "svelte", "http", "router")),
    ("networking", ("tokio", "grpc", "tonic", "kafka", "nats", "raft", "etcd",
                    "quic", "tcp", "socket", "consensus")),
    ("crypto", ("tls", "openssl", "rustls", "crypto", "aes", "ed25519", "ssl")),
    ("devtools", ("cli", "linter", "formatter", "compiler", "parser", "tree-sitter",
                  "build", "test", "benchmark")),
    ("observability", ("log", "trace", "metric", "opentelemetry", "prometheus")),
    ("data-format", ("json", "yaml", "protobuf", "avro", "parquet", "csv", "arrow")),
]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _lockfile_deps(root: Path) -> set[str]:
    """Same evidence the XERJ router uses (project dependency lockfiles)."""
    deps: set[str] = set()

    cl = root / "Cargo.lock"
    if cl.exists():
        for m in re.finditer(r"^name\s*=\s*\"([^\"]+)\"", cl.read_text(errors="replace"), re.M):
            deps.add(m.group(1))
    for pkg in ("package.json",):
        j = _read_json(root / pkg)
        if isinstance(j, dict):
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                if isinstance(j.get(key), dict):
                    deps.update(j[key].keys())
    gm = root / "go.mod"
    if gm.exists():
        for line in gm.read_text(errors="replace").splitlines():
            line = line.strip()
            if line.startswith(("require ", "\t")) and "/" in line:
                mod = line.replace("require ", "").split()[0]
                deps.add(mod)
                deps.add(mod.rsplit("/", 1)[-1])
    for req in ("requirements.txt",):
        p = root / req
        if p.exists():
            for line in p.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.add(re.split(r"[<>=!\[; ]", line, 1)[0])
    py = root / "pyproject.toml"
    if py.exists():
        txt = py.read_text(errors="replace")
        for m in re.finditer(r'^\s*["\']?([A-Za-z0-9_.\-]+)["\']?\s*(?:[<>=~!\[]|["\'])',
                             txt, re.M):
            deps.add(m.group(1))
        for m in re.finditer(r'^([A-Za-z0-9_.\-]+)\s*=', txt, re.M):
            deps.add(m.group(1))
    return {d for d in deps if d}


def classify_project(root: Path, extractor: Extractor) -> dict:
    langs: dict[str, int] = {}
    files = 0
    total = 0
    for fp in iter_files(root):
        files += 1
        try:
            total += fp.stat().st_size
        except OSError:
            pass
        lang = extractor.detect(fp, _head(fp))
        if lang:
            langs[lang] = langs.get(lang, 0) + 1
    deps = _lockfile_deps(root)
    hay = (root.name + " " + " ".join(sorted(langs, key=langs.get, reverse=True))
           + " " + " ".join(sorted(deps))).lower()
    domain, best = "general", 0
    for name, kws in DOMAIN_HINTS:
        score = sum(1 for k in kws if k in hay)
        if score > best:
            domain, best = name, score
    return {
        "languages": sorted(langs, key=langs.get, reverse=True),
        "lang_counts": langs,
        "domain": domain,
        "dependency_names": sorted(deps),
        "files": files,
        "bytes": total,
    }


# --------------------------------------------------------------------------- #
# file walking
# --------------------------------------------------------------------------- #
def _head(fp: Path, n: int = 8192) -> bytes:
    try:
        with open(fp, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _is_binary(head: bytes) -> bool:
    return b"\x00" in head


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
                       or d in (".github",)]
        for fn in filenames:
            if SKIP_FILE_RE.search(fn):
                continue
            fp = Path(dirpath) / fn
            try:
                if fp.is_symlink() or not fp.is_file():
                    continue
                if fp.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield fp


# --------------------------------------------------------------------------- #
# DB
# --------------------------------------------------------------------------- #
def default_db() -> Path:
    env = os.environ.get("REFCODE_DB")
    if env:
        return Path(env)
    return Path.home() / ".refcode" / "refcode.db"


def default_repo_cache() -> Path:
    return Path(os.environ.get("REFCODE_REPOS", str(Path.home() / ".refcode" / "repos")))


def open_db(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else default_db()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True)


def ensure_clone(url: str, slug: str, sha: str | None) -> Path:
    cache = default_repo_cache()
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / slug
    if (dest / ".git").exists():
        if sha:
            _git(["fetch", "--depth", "1", "origin", sha], cwd=dest)
            _git(["checkout", "--quiet", sha], cwd=dest)
        return dest
    r = _git(["clone", "--depth", "1", "--quiet", url, str(dest)])
    if r.returncode != 0:
        raise SystemExit(f"error: git clone failed for {url}\n{r.stderr.strip()}")
    if sha:
        _git(["fetch", "--depth", "1", "origin", sha], cwd=dest)
        _git(["checkout", "--quiet", sha], cwd=dest)
    return dest


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_index(args, conn: sqlite3.Connection) -> int:
    ex = Extractor()
    url = args.url
    if not url and args.path and re.match(r"^(https?://|git@|ssh://|git://)", args.path):
        url = args.path
    if url:
        args.url = url
        root = ensure_clone(url, args.slug, args.sha)
    else:
        root = Path(args.path).resolve()
    if not root.exists():
        print(f"error: path not found: {root}", file=sys.stderr)
        return 2

    info = classify_project(root, ex)
    # A curated row (from `corpus add`) outranks the heuristic classify().
    prev = conn.execute("SELECT domain,licence,ask_for FROM ref_projects WHERE slug=?",
                        (args.slug,)).fetchone()
    domain = (prev["domain"] if prev and prev["domain"] else info["domain"])
    licence = args.licence or (prev["licence"] if prev else None)
    ask_for = args.ask_for or (prev["ask_for"] if prev else None)
    conn.execute("DELETE FROM ref_symbols WHERE project=?", (args.slug,))
    conn.execute("DELETE FROM ref_body_fts WHERE project=?", (args.slug,))

    nsym = nwin = nfiles = 0
    sym_rows, win_rows = [], []
    for fp in iter_files(root):
        head = _head(fp)
        if _is_binary(head):
            continue
        lang = ex.detect(fp, head)
        if not lang:
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(fp.relative_to(root))
        nfiles += 1
        for i, (l0, win) in enumerate(windows(text)):
            win_rows.append((args.slug, rel, lang, i, l0, win))
            nwin += 1
        for s in ex.symbols(text, lang):
            qname = s["name"]
            sym_rows.append((
                args.slug, f"{rel}:{s['line']}:{s['name']}", s["kind"], s["name"],
                qname, rel, lang, s["line"], s["end_line"], s["signature"], None,
            ))
            nsym += 1
        if len(sym_rows) >= 5000:
            conn.executemany("INSERT OR REPLACE INTO ref_symbols VALUES"
                             " (?,?,?,?,?,?,?,?,?,?,?)", sym_rows)
            sym_rows.clear()
        if len(win_rows) >= 2000:
            conn.executemany("INSERT INTO ref_body_fts VALUES (?,?,?,?,?,?)", win_rows)
            win_rows.clear()
    if sym_rows:
        conn.executemany("INSERT OR REPLACE INTO ref_symbols VALUES"
                         " (?,?,?,?,?,?,?,?,?,?,?)", sym_rows)
    if win_rows:
        conn.executemany("INSERT INTO ref_body_fts VALUES (?,?,?,?,?,?)", win_rows)

    conn.execute(
        """INSERT INTO ref_projects
           (slug,url,sha,licence,domain,languages,ask_for,dependency_names,
            status,quality_grade,local_path,bytes,files,symbols,windows,indexed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(slug) DO UPDATE SET
             url=excluded.url, sha=excluded.sha, licence=excluded.licence,
             domain=excluded.domain, languages=excluded.languages,
             dependency_names=excluded.dependency_names, local_path=excluded.local_path,
             bytes=excluded.bytes, files=excluded.files, symbols=excluded.symbols,
             windows=excluded.windows, indexed_at=excluded.indexed_at""",
        (args.slug, args.url, args.sha, licence, domain,
         json.dumps(info["languages"]), ask_for,
         json.dumps(info["dependency_names"]), "live", None, str(root),
         info["bytes"], nfiles, nsym, nwin, _now()),
    )
    conn.commit()
    print(json.dumps({
        "slug": args.slug, "path": str(root), "domain": info["domain"],
        "languages": info["languages"][:8], "files": nfiles,
        "symbols": nsym, "windows": nwin,
    }, ensure_ascii=False))
    return 0


def _fts_query(text: str) -> str:
    toks = re.findall(r"[A-Za-z0-9_]+", text)
    if not toks:
        return ""
    # OR with ranking; quote to neutralise FTS operators
    return " OR ".join(f'"{t}"' for t in toks[:24])


def _snippet(body: str, toks: list[str], span: int = 240) -> str:
    low = body.lower()
    for t in toks:
        i = low.find(t.lower())
        if i >= 0:
            a = max(0, i - span // 3)
            return body[a:a + span].replace("\n", " ")
    return body[:span].replace("\n", " ")


def cmd_query(args, conn: sqlite3.Connection) -> int:
    q = args.text
    toks = re.findall(r"[A-Za-z0-9_]+", q) or [q]
    hits: list[dict] = []

    # symbol arm (defs first) - exact then prefix then FTS-on-name
    like = f"%{toks[0]}%"
    sym_sql = ("SELECT project,file_path,kind,name,signature,start_line,end_line "
               "FROM ref_symbols WHERE (name=? OR name LIKE ?) ")
    params: list = [toks[0], like]
    if args.project:
        sym_sql += "AND project=? "
        params.append(args.project)
    sym_sql += "ORDER BY (name=?) DESC, length(name) LIMIT ?"
    params += [toks[0], args.k]
    for r in conn.execute(sym_sql, params):
        hits.append({
            "arm": "symbol", "project": r["project"], "file": r["file_path"],
            "line": r["start_line"], "kind": r["kind"], "name": r["name"],
            "signature": r["signature"], "score": 1000.0,
        })

    # body arm (BM25)
    mq = _fts_query(q)
    if mq:
        body_sql = ("SELECT project,file_path,language,line0,body,"
                    " bm25(ref_body_fts) AS s FROM ref_body_fts "
                    "WHERE ref_body_fts MATCH ? ")
        bp: list = [mq]
        if args.project:
            body_sql += "AND project=? "
            bp.append(args.project)
        body_sql += "ORDER BY s LIMIT ?"
        bp.append(args.k)
        try:
            for r in conn.execute(body_sql, bp):
                hits.append({
                    "arm": "body", "project": r["project"], "file": r["file_path"],
                    "line": r["line0"], "language": r["language"],
                    "snippet": _snippet(r["body"], toks), "score": r["s"],
                })
        except sqlite3.OperationalError as e:
            print(f"warn: bad FTS query: {e}", file=sys.stderr)

    # de-dup by (project,file,line); symbol arm wins
    seen: set[tuple] = set()
    final: list[dict] = []
    for h in sorted(hits, key=lambda x: (-x["score"] if x["arm"] == "symbol" else x["score"])):
        k = (h["project"], h["file"], h["line"])
        if k in seen:
            continue
        seen.add(k)
        final.append(h)
        if len(final) >= args.k:
            break

    if args.json:
        print(json.dumps(final, ensure_ascii=False, indent=2))
        return 0 if final else 1
    if not final:
        print("(no hits)")
        return 1
    for h in final:
        if h["arm"] == "symbol":
            print(f"[{h['project']}] {h['file']}:{h['line']}  {h['kind']} {h['name']}")
            if h["signature"]:
                print(f"    {h['signature']}")
        else:
            print(f"[{h['project']}] {h['file']}:{h['line']}  ({h['language']})")
            print(f"    {h['snippet']}")
    return 0


def cmd_def(args, conn: sqlite3.Connection) -> int:
    sql = ("SELECT project,file_path,kind,name,signature,start_line,end_line "
           "FROM ref_symbols WHERE name=? ")
    p: list = [args.symbol]
    if args.project:
        sql += "AND project=? "
        p.append(args.project)
    sql += "ORDER BY project LIMIT ?"
    p.append(args.k)
    rows = list(conn.execute(sql, p))
    if not rows:
        sql2 = sql.replace("name=?", "name LIKE ?")
        p[0] = f"%{args.symbol}%"
        rows = list(conn.execute(sql2, p))
    if not rows:
        print(f"(no definition of {args.symbol})")
        return 1
    for r in rows:
        print(f"[{r['project']}] {r['file_path']}:{r['start_line']}  "
              f"{r['kind']} {r['name']}")
        if r["signature"]:
            print(f"    {r['signature']}")
    return 0


def cmd_corpus(args, conn: sqlite3.Connection) -> int:
    if args.action == "list":
        for r in conn.execute("SELECT slug,domain,licence,use_policy,languages,symbols,"
                              "files,indexed_at FROM ref_projects ORDER BY slug"):
            print(f"{r['slug']:22} {r['domain'] or '-':16} "
                  f"{r['licence'] or '-':28} {(r['use_policy'] or '-'):22} "
                  f"sym={r['symbols'] or 0}")
        return 0
    if args.action == "add":
        data = json.loads(Path(args.from_json).read_text())
        # accept XERJ corpus.json ({name,repos:[{url,sha,licence}]}) or flat rows
        rows = []
        if "repos" in data:
            for r in data["repos"]:
                rows.append({"slug": r.get("slug") or r["url"].rstrip("/").split("/")[-1],
                             "url": r["url"], "sha": r.get("sha"),
                             "licence": r.get("licence") or data.get("licence"),
                             "ask_for": data.get("ask_for")})
        elif isinstance(data, list):
            rows = data
        elif "projects" in data and isinstance(data["projects"], list):
            rows = data["projects"]
        else:
            rows = [data]
        for r in rows:
            conn.execute(
                """INSERT INTO ref_projects (slug,url,sha,licence,use_policy,domain,
                   languages,ask_for,dependency_names,status)
                   VALUES (?,?,?,?,?,?,NULL,?,?, 'candidate')
                   ON CONFLICT(slug) DO UPDATE SET
                     url=excluded.url,
                     sha=COALESCE(excluded.sha, ref_projects.sha),
                     licence=COALESCE(excluded.licence, ref_projects.licence),
                     use_policy=COALESCE(excluded.use_policy, ref_projects.use_policy),
                     ask_for=COALESCE(excluded.ask_for, ref_projects.ask_for),
                     domain=COALESCE(excluded.domain, ref_projects.domain),
                     dependency_names=CASE WHEN excluded.dependency_names NOT IN ('', '[]', 'null')
                                           THEN excluded.dependency_names
                                           ELSE ref_projects.dependency_names END""",
                (r["slug"], r.get("url"), r.get("sha"), r.get("licence"),
                 r.get("use"), r.get("domain"), r.get("ask_for"),
                 json.dumps(r.get("dependency_names") or [])))
            print(f"registered: {r['slug']}")
        conn.commit()
        return 0
    if args.action == "export":
        rows = [dict(r) for r in conn.execute(
            "SELECT slug,url,sha,licence,use_policy,domain,languages,ask_for,dependency_names "
            "FROM ref_projects ORDER BY slug")]
        for r in rows:
            for k in ("languages", "dependency_names"):
                if r.get(k):
                    try:
                        r[k] = json.loads(r[k])
                    except Exception:
                        pass
        print(json.dumps({"format": "refcode/corpus-v1", "projects": rows},
                         ensure_ascii=False, indent=2))
        return 0
    print("usage: refcode corpus {list|add|export}", file=sys.stderr)
    return 2


def cmd_route(args, conn: sqlite3.Connection) -> int:
    root = Path(args.repo).resolve()
    deps = _lockfile_deps(root)
    rows = list(conn.execute("SELECT slug,url,sha,licence,domain,dependency_names "
                             "FROM ref_projects"))
    scored = []
    for r in rows:
        names = set()
        try:
            names = set(json.loads(r["dependency_names"] or "[]"))
        except Exception:
            pass
        hit = deps & names
        if hit:
            scored.append((len(hit), r["slug"], sorted(hit)))
    scored.sort(reverse=True)
    if not scored:
        print(f"(no corpus matches deps of {root}; deps seen={len(deps)})")
        return 1
    for n, slug, hit in scored:
        print(f"{slug:24} hits={n}  via {', '.join(hit[:6])}")
    return 0


def cmd_refresh(args, conn: sqlite3.Connection) -> int:
    changed = 0
    for r in conn.execute("SELECT slug,url,sha FROM ref_projects WHERE url IS NOT NULL"):
        if not r["url"]:
            continue
        res = _git(["ls-remote", r["url"], "HEAD"])
        if res.returncode != 0:
            print(f"{r['slug']:24} unreachable")
            continue
        head = res.stdout.split()[0] if res.stdout.split() else ""
        stale = bool(head and r["sha"] and head != r["sha"])
        changed += stale
        print(f"{r['slug']:24} {'STALE' if stale else 'fresh':6} "
              f"pinned={(r['sha'] or '')[:10]} head={head[:10]}")
        if stale and not args.dry_run:
            conn.execute("UPDATE ref_projects SET refreshed_at=? WHERE slug=?",
                         (_now(), r["slug"]))
    conn.commit()
    if args.dry_run:
        print(f"({changed} stale; dry-run, nothing written)")
    return 0


def cmd_stats(args, conn: sqlite3.Connection) -> int:
    def one(sql):
        return conn.execute(sql).fetchone()[0]
    print(json.dumps({
        "db": str(args.db or default_db()),
        "projects": one("SELECT COUNT(*) FROM ref_projects"),
        "symbols": one("SELECT COUNT(*) FROM ref_symbols"),
        "windows": one("SELECT COUNT(*) FROM ref_body_fts"),
        "by_domain": {r[0]: r[1] for r in conn.execute(
            "SELECT domain, COUNT(*) FROM ref_projects GROUP BY domain")},
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_dump(args, conn: sqlite3.Connection) -> int:
    """Textual SQL dump - git-friendly artifact (manifest + rows)."""
    out = sys.stdout if not args.out else open(args.out, "w")
    for line in conn.iterdump():
        out.write(line + "\n")
    if args.out:
        out.close()
        print(f"wrote {args.out}")
    return 0


def cmd_verify(args, conn: sqlite3.Connection) -> int:
    """Verify every `[slug] path:line` peer-anchor in an artifact resolves in the DB.

    This is repo-map's cross-project counterpart to depth_check.py: a mechanism
    claim is only a fact if the cited peer symbol/line actually exists.
    """
    text = Path(args.artifact).read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"\[([A-Za-z0-9_.-]+)\]\s+([^\s:`()\[\]]+):(\d+)")
    ok = bad = 0
    for m in pat.finditer(text):
        slug, fp, ln = m.group(1), m.group(2).lstrip("./"), int(m.group(3))
        row = conn.execute(
            "SELECT 1 FROM ref_symbols WHERE project=? AND file_path=? "
            "AND start_line<=? AND end_line>=? LIMIT 1", (slug, fp, ln, ln)).fetchone()
        if not row:  # fall back to "file is indexed at all"
            row = conn.execute("SELECT 1 FROM ref_symbols WHERE project=? "
                               "AND file_path=? LIMIT 1", (slug, fp)).fetchone()
        if row:
            ok += 1
        else:
            bad += 1
            print(f"UNRESOLVED: [{slug}] {fp}:{ln}")
    print(f"{ok} peer-anchors resolved, {bad} unresolved "
          f"(artifact={args.artifact})")
    return 0 if bad == 0 else 1


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="refcode",
                                description="extract/classify/register/query reference code")
    p.add_argument("--db", default=None, help="SQLite path (default $REFCODE_DB or ~/.refcode/refcode.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index", help="extract+index a project into the shared DB")
    pi.add_argument("slug")
    pi.add_argument("path", nargs="?", default=None)
    pi.add_argument("--url", default=None)
    pi.add_argument("--sha", default=None)
    pi.add_argument("--licence", default=None)
    pi.add_argument("--ask-for", default=None)
    pi.set_defaults(func=cmd_index)

    pq = sub.add_parser("query", help="BM25 body + symbol-first retrieval")
    pq.add_argument("text")
    pq.add_argument("-k", type=int, default=5)
    pq.add_argument("--project", default=None)
    pq.add_argument("--json", action="store_true")
    pq.set_defaults(func=cmd_query)

    pd = sub.add_parser("def", help="exact symbol lookup")
    pd.add_argument("symbol")
    pd.add_argument("-k", type=int, default=10)
    pd.add_argument("--project", default=None)
    pd.set_defaults(func=cmd_def)

    pc = sub.add_parser("corpus", help="register/list/export corpora")
    pc.add_argument("action", choices=["list", "add", "export"])
    pc.add_argument("--from", dest="from_json", default=None)
    pc.set_defaults(func=cmd_corpus)

    pr = sub.add_parser("route", help="which corpora answer a target repo (via its lockfiles)")
    pr.add_argument("repo")
    pr.set_defaults(func=cmd_route)

    pf = sub.add_parser("refresh", help="git ls-remote re-pin check")
    pf.add_argument("--dry-run", action="store_true")
    pf.set_defaults(func=cmd_refresh)

    ps = sub.add_parser("stats", help="DB stats")
    ps.set_defaults(func=cmd_stats)

    pu = sub.add_parser("dump", help="SQL text dump (git-friendly)")
    pu.add_argument("--out", default=None)
    pu.set_defaults(func=cmd_dump)

    pv = sub.add_parser("verify", help="verify [slug] path:line peer-anchors in an artifact")
    pv.add_argument("artifact")
    pv.set_defaults(func=cmd_verify)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    conn = open_db(Path(args.db) if args.db else None)
    try:
        return args.func(args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
