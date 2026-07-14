#!/usr/bin/env python3
"""
srs_parser.py  —  Level-1 SRS Parser agent (deterministic)

Reads an IEEE-style Software Requirements Specification (.docx) and extracts the
three Level-1 artifacts consumed by the rest of the design pipeline:

    1. extracted_requirements   (functional / non-functional / performance /
                                 business rules / constraints / external
                                 interfaces / UI-token source)
    2. glossary                 (term -> definition)
    3. user_features            (roles / entities / features with flows + reqs)

The parser is deterministic: it keys off Word heading styles and the SRS's
tagged identifiers (REQ-n / NFR-n / BR-n). No LLM call is required, so it is
fast, free, and produces identical output every run. Requirement text is copied
verbatim; nothing is invented.

Folder convention (all relative to THIS script's location):
    design/
      srs_parser.py
      shared_resources/   <- put the SRS .docx here (auto-discovered)
      deliverables/       <- artifacts are written here

Location:
    A single folder holds the SRS *and* receives the deliverables. Its path is
    read from the SHARED_DIR environment variable (never hard-coded), and can be
    overridden per-run with --dir. SHARED_DIR may be set in the real environment
    or in a .env file (requires python-dotenv); real env vars win over .env.

Usage:
    # via .env (beside this script or in the run dir):
    #     SHARED_DIR=C:/Projects/SDLC/shared        (no quotes, single slashes)
    # or set it directly — PowerShell:  $env:SHARED_DIR = "C:\\Projects\\SDLC\\shared"
    python srs_parser.py                 # reads $SHARED_DIR/SRS.docx, writes artifacts there
    python srs_parser.py Other.docx      # override the filename inside $SHARED_DIR
    python srs_parser.py --dir ./shared  # override the location for this run
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn


# ---------------------------------------------------------------------------
# Location — one folder holds the SRS and receives the deliverables.
# Read from an environment variable (overridable with --dir); never hard-coded.
# ---------------------------------------------------------------------------
ENV_VAR = "SHARED_DIR"
DEFAULT_SRS = "SRS.docx"    # expected filename inside $SHARED_DIR


# ---------------------------------------------------------------------------
# Low-level docx helpers
# ---------------------------------------------------------------------------

def iter_blocks(doc: Document):
    """Yield paragraphs and tables in document order (python-docx keeps them
    in separate collections; we walk the body XML to interleave them)."""
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def heading_level(par: Paragraph) -> int | None:
    """Return 1/2/3/... if the paragraph is a Word heading, else None."""
    style = par.style.name if par.style else None
    if not style:
        return None
    m = re.match(r"Heading (\d+)", style)
    return int(m.group(1)) if m else None


def table_rows(tbl: Table):
    """Yield (first_cell, rest_joined) for each row, trimmed."""
    for row in tbl.rows:
        cells = [c.text.strip() for c in row.cells]
        # de-duplicate horizontally merged cells that repeat text
        deduped = []
        for c in cells:
            if not deduped or deduped[-1] != c:
                deduped.append(c)
        if not any(deduped):
            continue
        key = deduped[0]
        val = " ".join(x for x in deduped[1:] if x).strip()
        yield key, val


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    id: str
    name: str
    priority: str = ""
    description: str = ""
    flows: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    story: str = ""


REQ_RE = re.compile(r"^(REQ|NFR|BR)-(\d+)\s*[:.\)]?\s*(.*)$", re.IGNORECASE)
SECNUM_RE = re.compile(r"^(\d+(?:\.\d+)*)")
PRIORITY_RE = re.compile(r"Priority:\s*(High|Medium|Low)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class SRSParser:
    def __init__(self, path: str):
        self.doc = Document(path)

        # extracted requirements buckets
        self.functional: list[dict] = []
        self.non_functional: list[dict] = []
        self.performance: list[dict] = []
        self.business_rules: list[dict] = []
        self.constraints: list[str] = []
        self.tech_stack: list[dict] = []       # Section 7 Technology Stack (per subsection)
        self.external_interfaces: list[dict] = []
        self.ui_requirements: list[dict] = []   # source for Design Tokens (prose)
        self.ui_tokens: dict[str, list] = {}    # structured token tables (3.1.x)

        # glossary
        self.glossary: list[dict] = []

        # user features
        self.roles: list[dict] = []
        self.entities: list[str] = []
        self.features: dict[str, Feature] = {}

        # parsing state
        self.h1 = self.h2 = self.h3 = ""      # current heading titles
        self.h1_num = self.h2_num = self.h3_num = ""
        self._cur_req: dict | None = None      # for continuation lines
        self._cur_bucket: str | None = None    # which list _cur_req lives in

    # -- heading bookkeeping ------------------------------------------------
    def _set_heading(self, level: int, text: str):
        num = SECNUM_RE.match(text)
        num = num.group(1) if num else ""
        title = text[len(num):].lstrip(" .\t").strip()
        if level == 1:
            self.h1, self.h1_num = title, num
            self.h2 = self.h3 = self.h2_num = self.h3_num = ""
        elif level == 2:
            self.h2, self.h2_num = title, num
            self.h3 = self.h3_num = ""
            # register a feature when we enter section 4.x
            if self.h1_num == "4" and re.fullmatch(r"4\.\d+", num):
                self.features.setdefault(num, Feature(id=num, name=title))
        elif level >= 3:
            self.h3, self.h3_num = title, num
        self._cur_req = None  # headings end any open requirement

    # -- classification helpers --------------------------------------------
    @property
    def _cur_feature(self) -> Feature | None:
        if self.h1_num == "4" and self.h2_num:
            return self.features.get(self.h2_num)
        return None

    def _nfr_category(self) -> str:
        t = self.h2.lower()
        if "performance" in t:
            return "performance"
        if "safety" in t:
            return "safety"
        if "security" in t:
            return "security"
        if "quality" in t:
            return "software_quality"
        return "non_functional"

    # -- paragraph handling -------------------------------------------------
    def _handle_paragraph(self, par: Paragraph):
        lvl = heading_level(par)
        if lvl:
            self._set_heading(lvl, par.text.strip())
            return

        text = par.text.strip()
        if not text:
            return

        # tagged requirement / rule?
        m = REQ_RE.match(text)
        if m:
            kind, num, body = m.group(1).upper(), m.group(2), m.group(3).strip()
            rid = f"{kind}-{num}"
            rec = {"id": rid, "text": body}
            if kind == "REQ":
                feat = self._cur_feature
                rec["feature"] = feat.name if feat else ""
                self.functional.append(rec)
                if feat:
                    feat.requirements.append(rid)
                self._cur_req, self._cur_bucket = rec, "functional"
            elif kind == "NFR":
                cat = self._nfr_category()
                rec["category"] = cat
                if cat == "performance":
                    self.performance.append(rec)
                    self._cur_bucket = "performance"
                else:
                    self.non_functional.append(rec)
                    self._cur_bucket = "non_functional"
                self._cur_req = rec
            else:  # BR
                self.business_rules.append(rec)
                self._cur_req, self._cur_bucket = rec, "business_rules"
            return

        # continuation of a wrapped requirement line
        if self._cur_req is not None and self.h3_num.endswith(".3") is False:
            # only treat as continuation inside requirement-ish contexts
            pass
        if self._cur_req is not None and not text[0].isdigit():
            # append continuation text (rare; most reqs are single paragraphs)
            if self._looks_like_req_context():
                self._cur_req["text"] = (self._cur_req["text"] + " " + text).strip()
                return

        # section-specific prose
        self._handle_section_prose(par, text)

    def _looks_like_req_context(self) -> bool:
        return (
            self.h2.lower().endswith("functional requirements")
            or "functional requirements" in self.h3.lower()
            or "business rules" in self.h2.lower()
            or self.h1_num == "5"
        )

    def _handle_section_prose(self, par: Paragraph, text: str):
        # Section 7 Technology Stack -> tech_stack (prose + bullets, per subsection)
        if self.h1_num == "7":
            section = (f"{self.h2_num} {self.h2}".strip() if self.h2_num
                       else f"{self.h1_num} {self.h1}".strip())   # intro sits under "7"
            step = re.sub(r"^[\-\u2022\*\u2013]\s*", "", text).strip()
            if step:
                self.tech_stack.append({"section": section, "text": step})
            return

        # 2.5 Design and Implementation Constraints -> constraints list
        if self.h2_num == "2.5":
            self.constraints.append(text)
            return

        # 3.1.x  UI design / token requirements  -> source for Design Tokens
        if self.h2_num == "3.1":
            self.ui_requirements.append({"section": f"{self.h3_num} {self.h3}".strip(),
                                         "text": text})
            return

        # feature description / priority (4.x.1)
        feat = self._cur_feature
        if feat and self.h3_num.endswith(".1"):
            pr = PRIORITY_RE.search(text)
            if pr:
                feat.priority = pr.group(1).capitalize()
                text = PRIORITY_RE.sub("", text).strip(" .")
            if text:
                feat.description = (feat.description + " " + text).strip()
            return

        # feature stimulus/response (4.x.2) -> flows
        if feat and self.h3_num.endswith(".2"):
            step = re.sub(r"^[\-\u2022\*\u2013]\s*", "", text).strip()
            if step:
                feat.flows.append(step)
            return

        # Appendix B -> entity list
        if self.h1.lower().startswith("appendix b") or self.h1_num.lower() == "b":
            self._extract_entities(text)
            return

    def _extract_entities(self, text: str):
        m = re.search(r"principal entities\s*\(([^)]*)\)", text, re.IGNORECASE)
        if m:
            for e in m.group(1).split(","):
                e = e.strip()
                if e and e not in self.entities:
                    self.entities.append(e)

    # -- table handling -----------------------------------------------------
    @staticmethod
    def _table_records(tbl: Table) -> list[dict]:
        """Extract a table as header-keyed row dicts, preserving columns.
        Empty-header columns (e.g. a colour-swatch column) are skipped."""
        rows = tbl.rows
        if not rows:
            return []
        header = [c.text.strip() for c in rows[0].cells]
        records = []
        for r in rows[1:]:
            cells = [c.text.strip() for c in r.cells]
            rec = {}
            for h, v in zip(header, cells):
                if h:                                  # skip unnamed (swatch) column
                    rec[h.lower()] = v
            if any(rec.values()):
                records.append(rec)
        return records

    def _handle_table(self, tbl: Table):
        # 3.1.x  UI token tables (Colour / Typography / Spacing) -> design-token source
        if self.h3_num.startswith("3.1."):
            group = (self.h3.lower()
                     .replace(" tokens", "").replace(",", "")
                     .strip().replace(" ", "_"))            # e.g. "colour", "typography"
            self.ui_tokens[group] = self._table_records(tbl)
            return
        # Appendix A -> Glossary
        if self.h1.lower().startswith("appendix a") or "glossary" in self.h1.lower():
            for term, definition in table_rows(tbl):
                if term and definition and term.lower() not in ("term", "name"):
                    self.glossary.append({"term": term, "definition": definition})
            return
        # 2.3 User Classes -> roles
        if self.h2_num == "2.3":
            for role, desc in table_rows(tbl):
                if role and desc and role.lower() not in ("user class", "name"):
                    self.roles.append({"role": role, "description": desc})
            return
        # 3.3 Software Interfaces -> external interfaces (tech context)
        if self.h2_num == "3.3":
            for name, desc in table_rows(tbl):
                if name and desc and name.lower() != "name":
                    self.external_interfaces.append({"name": name, "description": desc})
            return

    # -- orchestration ------------------------------------------------------
    def parse(self):
        for block in iter_blocks(self.doc):
            if isinstance(block, Paragraph):
                self._handle_paragraph(block)
            elif isinstance(block, Table):
                self._handle_table(block)
        self._derive_stories()
        return self

    # role synonyms, ordered most-specific first (longer phrases win)
    ROLE_SYNS = [
        ("restaurant manager",   ["restaurant managers", "restaurant manager"]),
        ("platform administrator", ["administrators", "administrator", "admins", "admin"]),
        ("delivery agent",       ["delivery agents", "delivery agent", "couriers", "courier"]),
        ("customer",             ["customers", "customer"]),
        ("user",                 ["users of all four classes", "users", "user"]),
    ]

    def _canon_role(self, text: str):
        low = text.lower()
        for role, syns in self.ROLE_SYNS:
            for s in syns:
                if s in low:
                    return role
        return None

    def _fallback_role(self, f: Feature) -> str:
        n = (f.name + " " + f.description).lower()
        if "restaurant" in n or "partner" in n or "menu management" in n:
            return "restaurant manager"
        if "admin" in n or "platform management" in n:
            return "platform administrator"
        if "delivery" in n or "courier" in n or "agent" in n:
            return "delivery agent"
        return "customer"

    def _derive_stories(self):
        """Deterministically derive one clean story per feature.

        Actor + capability are parsed from the description's
        'Lets/Allows/Gives <actor> <capability>' structure (the SRS states the
        actor there, which is far more reliable than the feature name), with a
        keyword fallback when the description has no explicit subject. Pure
        string handling: reproducible, no LLM."""
        # actor synonyms as one alternation, longest first so they match greedily
        all_syns = sorted({s for _, ss in self.ROLE_SYNS for s in ss}, key=len, reverse=True)
        syn_role = {s: role for role, ss in self.ROLE_SYNS for s in ss}
        actor_re = re.compile(r"^(?:the\s+)?(?:" + "|".join(re.escape(s) for s in all_syns) + r")\s+",
                              re.IGNORECASE)
        lead_re = re.compile(r"^(allows|enables|lets|gives|provides)\s+(.*)$", re.IGNORECASE)

        def role_at_start(text: str):              # role sitting in the actor position
            low = text.lower()
            for s in all_syns:
                if low.startswith(s):
                    return syn_role[s]
            return None

        def person(text: str) -> str:               # 3rd -> 1st person tidy-up
            text = re.sub(r"\btheir\b", "my", text)
            text = re.sub(r"\bthem\b", "me", text)
            return text

        for f in self.features.values():
            desc = f.description.strip().rstrip(".")
            role = cap = prefix = None

            m = lead_re.match(desc)
            if m:
                verb, rest = m.group(1).lower(), desc[m.start(2):]
                role = role_at_start(rest)                  # actor is right after the verb
                if verb in ("allows", "enables"):           # "... X to <cap>"
                    idx = rest.lower().find(" to ")
                    if idx != -1:
                        cap, prefix = rest[idx + 4:], "I want to"
                elif verb == "lets":                        # "Lets <actor> <cap>"
                    cap, prefix = actor_re.sub("", rest), "I want to"
                elif verb in ("gives", "provides"):         # "Gives <actor> <noun>"
                    cap, prefix = actor_re.sub("", rest), "I want"

            if role is None:                                # no lead verb (Handles…, Coordinates…)
                role = self._canon_role(desc) or self._fallback_role(f)

            if cap:
                f.story = f"As a {role}, {prefix} {person(cap).strip()}."
            else:
                f.story = f"As a {role}, I want {f.name.lower()}."

    # -- output -------------------------------------------------------------
    def artifacts(self) -> dict:
        extracted = {
            "functional": self.functional,
            "non_functional": self.non_functional,
            "performance": self.performance,
            "business_rules": self.business_rules,
            "constraints": self.constraints,
            "external_interfaces": self.external_interfaces,
            "ui_token_source": self.ui_requirements,
            "ui_tokens": self.ui_tokens,
            "tech_stack": (
                self.tech_stack if self.tech_stack else
                [{"section": "", "text":
                    "Not specified in the SRS (no Technology Stack section). Decided in "
                    "Design; see constraints + external_interfaces for imposed constraints."}]
            ),
        }
        glossary = {"terms": self.glossary}
        user_features = {
            "roles": self.roles,
            "entities": self.entities,
            "features": [asdict(f) for f in self.features.values()],
        }
        return {
            "extracted_requirements": extracted,
            "glossary": glossary,
            "user_features": user_features,
        }

    def write(self, out_dir: str):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        arts = self.artifacts()
        for name, data in arts.items():
            (out / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_markdown(out, arts)
        return arts

    def _write_markdown(self, out: Path, arts: dict):
        er = arts["extracted_requirements"]
        lines = ["# Extracted Requirements\n"]
        lines.append(f"## Functional ({len(er['functional'])})")
        for r in er["functional"]:
            lines.append(f"- **{r['id']}** ({r.get('feature','')}): {r['text']}")
        lines.append(f"\n## Performance ({len(er['performance'])})")
        for r in er["performance"]:
            lines.append(f"- **{r['id']}**: {r['text']}")
        lines.append(f"\n## Non-Functional ({len(er['non_functional'])})")
        for r in er["non_functional"]:
            lines.append(f"- **{r['id']}** [{r.get('category','')}]: {r['text']}")
        lines.append(f"\n## Business Rules ({len(er['business_rules'])})")
        for r in er["business_rules"]:
            lines.append(f"- **{r['id']}**: {r['text']}")
        lines.append("\n## Constraints")
        for c in er["constraints"]:
            lines.append(f"- {c}")
        lines.append("\n## External Interfaces")
        for e in er["external_interfaces"]:
            lines.append(f"- **{e['name']}**: {e['description']}")
        lines.append("\n## UI Token Source (feeds Design Tokens)")
        for u in er["ui_token_source"]:
            lines.append(f"- **{u['section']}**: {u['text']}")
        if er.get("ui_tokens"):
            lines.append("\n## UI Tokens (structured, from 3.1 tables)")
            for group, rows in er["ui_tokens"].items():
                lines.append(f"\n### {group.replace('_',' ').title()} ({len(rows)})")
                for row in rows:
                    lines.append("- " + " · ".join(f"{k}: {v}" for k, v in row.items() if v))
        lines.append("\n## Tech Stack")
        if er["tech_stack"] and er["tech_stack"][0].get("section"):
            last = None
            for item in er["tech_stack"]:
                if item["section"] != last:
                    lines.append(f"\n### {item['section']}")
                    last = item["section"]
                lines.append(f"- {item['text']}")
        else:
            lines.append(er["tech_stack"][0]["text"])
        (out / "extracted_requirements.md").write_text("\n".join(lines), encoding="utf-8")

        g = arts["glossary"]["terms"]
        gl = ["# Glossary\n"] + [f"- **{t['term']}** — {t['definition']}" for t in g]
        (out / "glossary.md").write_text("\n".join(gl), encoding="utf-8")

        uf = arts["user_features"]
        ul = ["# User Features\n", "## Roles"]
        ul += [f"- **{r['role']}** — {r['description']}" for r in uf["roles"]]
        ul.append("\n## Entities")
        ul.append(", ".join(uf["entities"]))
        ul.append("\n## Features")
        for f in uf["features"]:
            ul.append(f"\n### {f['id']} {f['name']}  ·  Priority: {f['priority'] or 'n/a'}")
            ul.append(f"_{f['description']}_")
            ul.append(f"- **Story (derived):** {f['story']}")
            if f["flows"]:
                ul.append("- **Flow:**")
                ul += [f"    {i+1}. {s}" for i, s in enumerate(f["flows"])]
            if f["requirements"]:
                ul.append(f"- **Requirements:** {', '.join(f['requirements'])}")
        (out / "user_features.md").write_text("\n".join(ul), encoding="utf-8")


def load_dotenv_files() -> None:
    """Load a .env file if python-dotenv is installed (optional dependency).
    Looks beside this script and in the current directory. Real environment
    variables always take precedence (override=False)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # python-dotenv not installed -> use real environment variables only
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env", override=False)   # .env next to the script
    load_dotenv(override=False)                  # .env in the current dir, if any


def resolve_shared_dir(cli_dir: str | None) -> Path:
    """The one folder that holds the SRS and receives the deliverables.
    Priority: --dir  >  $SHARED_DIR. Never hard-coded."""
    raw = cli_dir or os.environ.get(ENV_VAR)
    if not raw:
        raise SystemExit(
            f"No location set. Set the {ENV_VAR} environment variable to the folder "
            f"that holds the SRS (deliverables are written there too), or pass --dir.\n"
            f'  PowerShell:  $env:{ENV_VAR} = "C:\\path\\to\\shared"\n'
            f"  bash/zsh:    export {ENV_VAR}=/path/to/shared"
        )
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise SystemExit(f"{ENV_VAR} location is not a directory: {path}")
    return path


def find_srs(shared: Path, arg: str | None) -> Path:
    """Locate the SRS. By default it's `SRS.docx` inside the shared folder;
    an explicit filename or path can override that."""
    name = arg or DEFAULT_SRS
    cand = Path(name)
    if cand.is_file():                       # explicit / absolute path
        return cand
    target = shared / name                   # by filename inside the shared folder
    if target.is_file():
        return target
    raise SystemExit(
        f"SRS not found: {target}"
        + (f"  (also tried '{name}' as a direct path)" if arg else
           f"\nPlace '{DEFAULT_SRS}' in {shared}, or pass a filename.")
    )


def main():
    load_dotenv_files()
    ap = argparse.ArgumentParser(description="Extract Level-1 artifacts from an SRS .docx")
    ap.add_argument("srs", nargs="?", default=None,
                    help=f"SRS filename or path (optional). "
                         f"Defaults to '{DEFAULT_SRS}' inside $" + ENV_VAR + ".")
    ap.add_argument("--dir", default=None,
                    help=f"shared location (SRS in, deliverables out). Overrides ${ENV_VAR}.")
    args = ap.parse_args()

    shared = resolve_shared_dir(args.dir)
    srs_path = find_srs(shared, args.srs)
    parser = SRSParser(str(srs_path)).parse()
    arts = parser.write(str(shared))             # deliverables go to the same folder

    er = arts["extracted_requirements"]
    uf = arts["user_features"]
    print(f"Parsed '{srs_path.name}' -> deliverables written to {shared}")
    print(f"  Extracted Requirements: {len(er['functional'])} functional · "
          f"{len(er['performance'])} performance · {len(er['non_functional'])} non-functional · "
          f"{len(er['business_rules'])} business rules · {len(er['constraints'])} constraints · "
          f"{len(er['external_interfaces'])} interfaces · {len(er['ui_token_source'])} UI-token items · "
          f"{len(er['tech_stack'])} tech-stack items")
    print(f"  Glossary:      {len(arts['glossary']['terms'])} terms")
    print(f"  User Features: {len(uf['roles'])} roles · {len(uf['entities'])} entities · "
          f"{len(uf['features'])} features")


if __name__ == "__main__":
    main()