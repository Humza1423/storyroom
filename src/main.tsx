import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  DragEndEvent,
  closestCenter,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  arrayMove,
  verticalListSortingStrategy,
  sortableKeyboardCoordinates,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Film,
  Plus,
  Search,
  Upload,
  ArrowUpRight,
  Play,
  GripVertical,
  X,
  Sparkles,
  Undo2,
  Download,
  ChevronRight,
  Circle,
  Check,
  Loader2,
  FolderOpen,
  Settings2,
  Scissors,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import "./style.css";

type Provenance = {
  source?: string;
  author?: string;
  license?: string;
  cloud_analysis?: boolean;
  training?: boolean;
  redistribution?: boolean;
};
type Asset = {
  id: string;
  name: string;
  frames: number;
  duration: number;
  status: string;
  error?: string;
  provenance: Provenance;
};
type Moment = {
  id: string;
  asset_id: string;
  start_frame: number;
  end_frame: number;
  description: string;
  source: string;
  uncertainty?: string;
  score?: number;
};
type Selection = {
  id: string;
  asset_id: string;
  moment_id: string | null;
  start_frame: number;
  end_frame: number;
  note: string;
};
type Section = {
  id: string;
  title: string;
  purpose: string;
  selections: Selection[];
};
type ProposalSection = {
  title: string;
  purpose: string;
  candidate_ids: string[];
};
type Job = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  message: string;
  result: null | {
    url?: string;
    sections?: ProposalSection[];
    candidate_ids?: string[];
    explanation?: string;
  };
};
type Project = {
  id: string;
  name: string;
  brief: string;
  revision: number;
  board: Section[];
  assets: Asset[];
  moments: Moment[];
  jobs: Job[];
};
type Status = {
  ai_ready: boolean;
  key_present: boolean;
  pricing_confirmed: boolean;
  model: string;
  spend: number;
  limit: number;
  ffmpeg: boolean;
};
const id = () => crypto.randomUUID();
const timecode = (f: number) =>
  `${Math.floor(f / 1800)
    .toString()
    .padStart(2, "0")}:${Math.floor((f / 30) % 60)
    .toString()
    .padStart(2, "0")}:${Math.round(f % 30)
    .toString()
    .padStart(2, "0")}`;
async function api<T>(url: string, method = "GET", body?: unknown): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch("/api" + url, {
    method,
    headers: {
      "X-Storyroom": "local",
      ...(!form && body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return response.json();
}

function MomentCard({
  moment,
  asset,
  onPreview,
  onAdd,
  onLabel,
}: {
  moment: Moment;
  asset?: Asset;
  onPreview: () => void;
  onAdd: () => void;
  onLabel: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: "moment:" + moment.id, data: { moment } });
  return (
    <article
      ref={setNodeRef}
      className={"moment-card " + (isDragging ? "dragging" : "")}
      style={{ transform: CSS.Translate.toString(transform) }}
    >
      <button
        className="thumbnail"
        onClick={onPreview}
        aria-label={"Preview " + moment.description}
      >
        <img src={`/api/assets/${moment.asset_id}/thumbnail`} alt="" />
        <span className="thumb-play">
          <Play size={14} />
        </span>
        <span className="duration">
          {((moment.end_frame - moment.start_frame) / 30).toFixed(1)}s
        </span>
      </button>
      <div className="moment-meta">
        <span className="source">
          {moment.source === "ai" ? "AI MOMENT" : "YOUR FOOTAGE"}
        </span>
        <button
          className="icon drag"
          {...listeners}
          {...attributes}
          aria-label="Drag moment"
        >
          <GripVertical size={15} />
        </button>
      </div>
      <button className="moment-title" onClick={onPreview}>
        {moment.description}
      </button>
      <p className="filename" title={asset?.name}>
        {asset?.name} · {timecode(moment.start_frame)}
      </p>
      {moment.uncertainty && (
        <p className="uncertainty">{moment.uncertainty}</p>
      )}
      <div className="card-actions">
        <button className="text-button" onClick={onAdd}>
          <Plus size={13} /> Add to section
        </button>
        <button
          className="icon"
          title="Label for training"
          aria-label="Label for training"
          onClick={onLabel}
        >
          <Settings2 size={13} />
        </button>
      </div>
    </article>
  );
}

function ClipRow({
  clip,
  asset,
  active,
  onSelect,
  onRemove,
  onMove,
}: {
  clip: Selection;
  asset?: Asset;
  active: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onMove: (n: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: clip.id, data: { selection: clip } });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={"clip-row " + (active ? "selected" : "")}
    >
      <button
        className="icon drag"
        {...attributes}
        {...listeners}
        aria-label="Reorder clip"
      >
        <GripVertical size={14} />
      </button>
      <button className="clip-main" onClick={onSelect}>
        <img src={`/api/assets/${clip.asset_id}/thumbnail`} alt="" />
        <span>
          <strong>{asset?.name}</strong>
          <small>
            {timecode(clip.start_frame)} → {timecode(clip.end_frame)}
          </small>
        </span>
      </button>
      <button
        className="icon tiny"
        onClick={() => onMove(-1)}
        aria-label="Move clip earlier"
      >
        <ArrowUp size={12} />
      </button>
      <button
        className="icon tiny"
        onClick={() => onMove(1)}
        aria-label="Move clip later"
      >
        <ArrowDown size={12} />
      </button>
      <button className="icon" onClick={onRemove} aria-label="Remove clip">
        <X size={13} />
      </button>
    </div>
  );
}

function StorySection({
  section,
  index,
  active,
  onActivate,
  onRename,
  onRemove,
  onMove,
  children,
}: {
  section: Section;
  index: number;
  active: boolean;
  onActivate: () => void;
  onRename: () => void;
  onRemove: () => void;
  onMove: (n: number) => void;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: "section:" + section.id });
  const duration =
    section.selections.reduce((n, c) => n + c.end_frame - c.start_frame, 0) /
    30;
  return (
    <section
      ref={setNodeRef}
      onClick={onActivate}
      className={
        "story-section " + (active ? "active " : "") + (isOver ? "over" : "")
      }
    >
      <header>
        <span className="section-number">
          {String(index + 1).padStart(2, "0")}
        </span>
        <button className="section-heading" onClick={onRename}>
          <strong>{section.title}</strong>
          <small>
            {section.purpose || "Define what this part of the story should do."}
          </small>
        </button>
        <span className="section-length">{duration.toFixed(1)}s</span>
        <button
          className="icon"
          onClick={(e) => {
            e.stopPropagation();
            onMove(-1);
          }}
          aria-label="Move section earlier"
        >
          <ArrowUp size={13} />
        </button>
        <button
          className="icon"
          onClick={(e) => {
            e.stopPropagation();
            onMove(1);
          }}
          aria-label="Move section later"
        >
          <ArrowDown size={13} />
        </button>
        <button
          className="icon"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label="Remove section"
        >
          <X size={14} />
        </button>
      </header>
      {children}
      {!section.selections.length && (
        <div className="section-drop">
          <Plus size={17} />
          <span>Drop a moment here, or add one from your footage</span>
        </div>
      )}
    </section>
  );
}

function App() {
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]),
    [pid, setPid] = useState(localStorage.getItem("storyroom.project") || "");
  const [project, setProject] = useState<Project | null>(null),
    [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const [query, setQuery] = useState(""),
    [results, setResults] = useState<Moment[] | null>(null),
    [semantic, setSemantic] = useState(false);
  const [activeSection, setActiveSection] = useState(""),
    [selected, setSelected] = useState<Selection | null>(null),
    [preview, setPreview] = useState<Moment | Selection | null>(null);
  const [trimStart, setTrimStart] = useState(0),
    [trimEnd, setTrimEnd] = useState(0),
    [note, setNote] = useState("");
  const [brief, setBrief] = useState(""),
    [newProject, setNewProject] = useState(false),
    [projectName, setProjectName] = useState("");
  const [sectionDialog, setSectionDialog] = useState<{
    id?: string;
    title: string;
    purpose: string;
  } | null>(null);
  const [provenance, setProvenance] = useState<Asset | null>(null),
    [label, setLabel] = useState<Moment | null>(null),
    [labelReason, setLabelReason] = useState(""),
    [rating, setRating] = useState(2),
    [group, setGroup] = useState("");
  const [analysisEstimate, setAnalysisEstimate] = useState<number | null>(null),
    [showJobs, setShowJobs] = useState(false),
    [sequenceIndex, setSequenceIndex] = useState<number | null>(null);
  const video = useRef<HTMLVideoElement>(null),
    fileInput = useRef<HTMLInputElement>(null),
    saving = useRef(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  async function refresh() {
    const [ps, st] = await Promise.all([
      api<{ id: string; name: string }[]>("/projects"),
      api<Status>("/status"),
    ]);
    setProjects(ps);
    setStatus(st);
    if (pid) {
      const p = await api<Project>("/projects/" + pid);
      setProject(p);
    }
  }
  async function task(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    let stopped = false;
    async function tick() {
      try {
        const [ps, st] = await Promise.all([
          api<{ id: string; name: string }[]>("/projects"),
          api<Status>("/status"),
        ]);
        if (stopped) return;
        setProjects(ps);
        setStatus(st);
        if (pid) {
          const p = await api<Project>("/projects/" + pid);
          if (!stopped && !saving.current) setProject(p);
        }
      } catch (e) {
        if (!stopped) setError((e as Error).message);
      }
    }
    tick();
    const timer = setInterval(tick, 2500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [pid]);
  useEffect(() => {
    setProject(null);
    setResults(null);
    setPreview(null);
    setSelected(null);
    setActiveSection("");
    setSequenceIndex(null);
    if (pid) {
      localStorage.setItem("storyroom.project", pid);
      api<Project>("/projects/" + pid)
        .then((p) => {
          setProject(p);
          setBrief(p.brief);
          setGroup(p.id);
        })
        .catch((e) => setError(e.message));
    }
  }, [pid]);
  const board = project?.board || [],
    clips = board.flatMap((s) => s.selections),
    assetMap = Object.fromEntries(
      (project?.assets || []).map((a) => [a.id, a]),
    );
  const active = board.find((s) => s.id === activeSection) || board[0];
  const activeJobs =
    project?.jobs.filter((j) => ["queued", "running"].includes(j.status)) || [];
  const latestProposal = project?.jobs.find(
    (j) => j.kind === "story" && j.status === "done" && j.result?.sections,
  );
  const visibleMoments = results ?? project?.moments ?? [];
  const duration =
    clips.reduce((n, c) => n + c.end_frame - c.start_frame, 0) / 30;
  async function saveBoard(next: Section[]) {
    if (!project || saving.current) return;
    saving.current = true;
    try {
      const r = await api<{ revision: number }>(
        `/projects/${pid}/board`,
        "PUT",
        { revision: project.revision, sections: next },
      );
      setProject({ ...project, board: next, revision: r.revision });
      setNotice("All changes saved");
    } catch (e) {
      await refresh();
      throw e;
    } finally {
      saving.current = false;
    }
  }
  function add(moment: Moment, sectionId = active?.id) {
    task(async () => {
      let next = structuredClone(board);
      if (!sectionId) {
        const s = {
          id: id(),
          title: "New section",
          purpose: "",
          selections: [],
        };
        next.push(s);
        sectionId = s.id;
        setActiveSection(s.id);
      }
      const section = next.find((s) => s.id === sectionId)!;
      section.selections.push({
        id: id(),
        asset_id: moment.asset_id,
        moment_id: moment.id,
        start_frame: moment.start_frame,
        end_frame: moment.end_frame,
        note: "",
      });
      await saveBoard(next);
    });
  }
  function selectClip(c: Selection) {
    setSelected(c);
    setPreview(c);
    setTrimStart(c.start_frame);
    setTrimEnd(c.end_frame);
    setNote(c.note);
    setSequenceIndex(null);
  }
  function playMoment(m: Moment) {
    setPreview(m);
    setSelected(null);
    setSequenceIndex(null);
  }
  useEffect(() => {
    if (!video.current || !preview) return;
    const v = video.current;
    const load = () => {
      v.currentTime = preview.start_frame / 30;
      if (sequenceIndex !== null) v.play().catch(() => {});
    };
    v.addEventListener("loadedmetadata", load, { once: true });
    if (v.readyState >= 1) load();
    return () => v.removeEventListener("loadedmetadata", load);
  }, [preview, sequenceIndex]);
  function advance() {
    if (sequenceIndex === null) {
      video.current?.pause();
      return;
    }
    const next = sequenceIndex + 1;
    if (next >= clips.length) {
      video.current?.pause();
      setSequenceIndex(null);
      return;
    }
    setSequenceIndex(next);
    setPreview(clips[next]);
  }
  async function startJob(kind: string) {
    await api(`/projects/${pid}/jobs/${kind}`, "POST", {
      query: kind === "rerank" ? active?.purpose || active?.title || "" : "",
    });
    setShowJobs(true);
    await refresh();
  }
  function moveClip(sid: string, cid: string, delta: number) {
    task(async () => {
      const next = structuredClone(board);
      const s = next.find((s) => s.id === sid)!;
      const i = s.selections.findIndex((c) => c.id === cid);
      if (i + delta < 0 || i + delta >= s.selections.length) return;
      s.selections = arrayMove(s.selections, i, i + delta);
      await saveBoard(next);
    });
  }
  function onDragEnd(e: DragEndEvent) {
    if (!e.over) return;
    const moment = e.active.data.current?.moment as Moment | undefined;
    const target = String(e.over.id);
    const targetSection = target.startsWith("section:")
      ? target.slice(8)
      : board.find((s) => s.selections.some((c) => c.id === target))?.id;
    if (!targetSection) return;
    if (moment) {
      add(moment, targetSection);
      return;
    }
    task(async () => {
      const next = structuredClone(board),
        from = next.find((s) => s.selections.some((c) => c.id === e.active.id)),
        to = next.find((s) => s.id === targetSection);
      if (!from || !to) return;
      const index = from.selections.findIndex((c) => c.id === e.active.id);
      const [clip] = from.selections.splice(index, 1);
      const insert = to.selections.findIndex((c) => c.id === target);
      to.selections.splice(insert < 0 ? to.selections.length : insert, 0, clip);
      await saveBoard(next);
    });
  }
  const readyAssets = project?.assets.filter((a) => a.status === "ready") || [];
  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-icon">
            <Film size={21} />
          </span>
          <span>
            storyroom<span className="brand-dot">.</span>
          </span>
        </div>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <button className="new-project" onClick={() => setNewProject(true)}>
          <Plus size={16} /> New project
        </button>
        <nav>
          {projects.map((p) => (
            <button
              className={"project-link " + (p.id === pid ? "current" : "")}
              key={p.id}
              aria-label={p.name}
              onClick={() => setPid(p.id)}
            >
              <FolderOpen size={16} />
              <span>{p.name}</span>
            </button>
          ))}
        </nav>
        <div className="rail-bottom">
          <div className="local-badge">
            <span /> Local workspace
          </div>
          <p>
            Your footage stays here.
            <br />
            Cloud analysis is optional.
          </p>
          <div className="budget">
            <span>AI development budget</span>
            <strong>
              ${status?.spend.toFixed(2) || "0.00"}{" "}
              <small>/ ${status?.limit || 45}</small>
            </strong>
            <progress max={status?.limit || 45} value={status?.spend || 0} />
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <span>{project?.name || "Get started"}</span>
          </div>
          <div className="header-right">
            <span className="save-status">
              <Check size={13} />
              {busy ? "Working…" : notice || "Saved locally"}
            </span>
            <button
              className="secondary"
              disabled={!clips.length || busy}
              onClick={() => task(() => startJob("render"))}
            >
              <Play size={14} /> Render preview
            </button>
            <button
              className="primary"
              disabled={!clips.length || busy}
              onClick={() => task(() => startJob("export"))}
            >
              Export to Resolve <ArrowUpRight size={15} />
            </button>
          </div>
        </header>
        {error && (
          <div role="alert" className="error-banner">
            {error}
            <button
              className="icon"
              onClick={() => setError("")}
              aria-label="Dismiss error"
            >
              <X size={15} />
            </button>
          </div>
        )}
        {!project ? (
          <div className="welcome">
            <span className="eyebrow">FROM FOOTAGE TO FIRST ASSEMBLY</span>
            <h1>
              Find the story
              <br />
              in your footage.
            </h1>
            <p>
              A little structure. Your creative decisions.
              <br />
              Bring in your clips, collect the moments that matter,
              <br />
              and take your assembly into the editing room.
            </p>
            <button className="primary" onClick={() => setNewProject(true)}>
              <Plus size={17} /> Create your first project
            </button>
            <div className="welcome-steps">
              <span>01 / Import</span>
              <span>02 / Explore</span>
              <span>03 / Assemble</span>
            </div>
          </div>
        ) : (
          <>
            <div className="project-heading">
              <div>
                <span className="eyebrow">TRAINING MONTAGE · 30 FPS</span>
                <h1>{project.name}</h1>
                <p>Make room for the moments that matter.</p>
              </div>
              <button
                className="secondary"
                onClick={() => setShowJobs(!showJobs)}
              >
                {activeJobs.length ? (
                  <Loader2 className="spin" size={14} />
                ) : (
                  <Circle size={12} />
                )}{" "}
                Processing{" "}
                {activeJobs.length > 0 && (
                  <span className="badge">{activeJobs.length}</span>
                )}
              </button>
            </div>
            <div className="brief-bar">
              <Sparkles size={18} />
              <textarea
                aria-label="Creative brief"
                placeholder="What's the story? e.g. A 45-second training reel about persistence, ending on the final attempt."
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
              />
              <button
                className="text-button"
                disabled={busy}
                onClick={() =>
                  task(async () => {
                    await api(`/projects/${pid}`, "PUT", {
                      name: project.name,
                      brief,
                    });
                    setNotice("Brief saved");
                    await refresh();
                  })
                }
              >
                Save brief
              </button>
              <button
                className="secondary"
                disabled={busy || !status?.ai_ready || !readyAssets.length}
                title={
                  !status?.ai_ready
                    ? "Configure Gemini in .env to enable cloud suggestions"
                    : ""
                }
                onClick={() =>
                  task(async () => {
                    await api(`/projects/${pid}`, "PUT", {
                      name: project.name,
                      brief,
                    });
                    await startJob("story");
                  })
                }
              >
                <Sparkles size={14} /> Suggest story
              </button>
            </div>
            {!status?.ai_ready && (
              <div className="ai-notice">
                Manual workspace is ready. To enable AI, add your Gemini key and
                confirm prices in <code>.env</code>. No cloud calls are made
                yet.
              </div>
            )}
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={onDragEnd}
            >
              <div className={"workspace " + (busy ? "working" : "")}>
                <section className="library">
                  <div className="panel-heading">
                    <h2>
                      Your footage <span>{project.assets.length}</span>
                    </h2>
                    <button
                      className="icon"
                      onClick={() => fileInput.current?.click()}
                      aria-label="Import footage"
                    >
                      <Plus size={18} />
                    </button>
                  </div>
                  <input
                    ref={fileInput}
                    type="file"
                    accept="video/mp4"
                    multiple
                    hidden
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      task(async () => {
                        for (const f of files) {
                          const data = new FormData();
                          data.append("file", f);
                          await api(`/projects/${pid}/import`, "POST", data);
                        }
                        setNotice("Footage imported; preparing media");
                        await refresh();
                      });
                      e.target.value = "";
                    }}
                  />
                  <form
                    className="search-bar"
                    onSubmit={(e) => {
                      e.preventDefault();
                      task(async () =>
                        setResults(
                          await api<Moment[]>(
                            `/projects/${pid}/search`,
                            "POST",
                            { query, semantic },
                          ),
                        ),
                      );
                    }}
                  >
                    <Search size={15} />
                    <input
                      aria-label="Search footage"
                      placeholder="Find a moment…"
                      value={query}
                      onChange={(e) => {
                        setQuery(e.target.value);
                        if (!e.target.value) setResults(null);
                      }}
                    />
                    <button type="submit" className="icon" aria-label="Search">
                      <ChevronRight size={16} />
                    </button>
                  </form>
                  <div className="library-tools">
                    <label>
                      <input
                        type="checkbox"
                        checked={semantic}
                        disabled={!status?.ai_ready}
                        onChange={(e) => setSemantic(e.target.checked)}
                      />{" "}
                      AI search
                    </label>
                    <button
                      className="text-button"
                      disabled={!readyAssets.length || !status?.ai_ready}
                      onClick={() =>
                        task(async () => {
                          const r = await api<{ estimated_usd: number }>(
                            `/projects/${pid}/analysis-estimate`,
                            "POST",
                            { asset_ids: readyAssets.map((a) => a.id) },
                          );
                          setAnalysisEstimate(r.estimated_usd);
                        })
                      }
                    >
                      <Sparkles size={12} /> Analyze
                    </button>
                  </div>
                  {!project.assets.length && (
                    <button
                      className="import-zone"
                      onClick={() => fileInput.current?.click()}
                    >
                      <Upload size={25} />
                      <strong>Bring your footage in</strong>
                      <span>
                        H.264 MP4 · up to 1080p
                        <br />
                        30 clips · 15 minutes · 2 GB
                      </span>
                    </button>
                  )}
                  <div className="moments">
                    {visibleMoments.map((m) => (
                      <MomentCard
                        key={m.id}
                        moment={m}
                        asset={assetMap[m.asset_id]}
                        onPreview={() => playMoment(m)}
                        onAdd={() => add(m)}
                        onLabel={() => {
                          setLabel(m);
                          setLabelReason("");
                        }}
                      />
                    ))}
                  </div>
                  {results?.length === 0 && (
                    <div className="empty-small">
                      No matching moments. Try different words, add a
                      description, or analyze your footage.
                    </div>
                  )}
                  <div className="asset-list">
                    {project.assets.map((a) => (
                      <div key={a.id}>
                        <span className={"asset-state " + a.status}>
                          {a.status === "ready" ? (
                            <Check size={12} />
                          ) : (
                            <Circle size={12} />
                          )}
                        </span>
                        <span title={a.error || a.name}>{a.name}</span>
                        <button
                          className="icon"
                          onClick={() => setProvenance(a)}
                          title="Source and permissions"
                          aria-label={"Permissions for " + a.name}
                        >
                          <Settings2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
                <section className="board-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        Story map <span>{board.length} sections</span>
                      </h2>
                      <p>Build the shape. Keep the freedom.</p>
                    </div>
                    <button
                      className="icon"
                      disabled={busy || project.revision === 0}
                      aria-label="Undo board change"
                      title="Undo last board change"
                      onClick={() =>
                        task(async () => {
                          await api(`/projects/${pid}/undo`, "POST", {
                            revision: project.revision,
                          });
                          await refresh();
                        })
                      }
                    >
                      <Undo2 size={17} />
                    </button>
                  </div>
                  <div className="story-board">
                    {board.map((s, i) => (
                      <StorySection
                        key={s.id}
                        section={s}
                        index={i}
                        active={active?.id === s.id}
                        onActivate={() => setActiveSection(s.id)}
                        onRename={() =>
                          setSectionDialog({
                            id: s.id,
                            title: s.title,
                            purpose: s.purpose,
                          })
                        }
                        onRemove={() =>
                          task(async () => {
                            await saveBoard(board.filter((b) => b.id !== s.id));
                          })
                        }
                        onMove={(delta) =>
                          task(async () => {
                            if (i + delta >= 0 && i + delta < board.length)
                              await saveBoard(arrayMove(board, i, i + delta));
                          })
                        }
                      >
                        <SortableContext
                          items={s.selections.map((c) => c.id)}
                          strategy={verticalListSortingStrategy}
                        >
                          {s.selections.map((c) => (
                            <ClipRow
                              key={c.id}
                              clip={c}
                              asset={assetMap[c.asset_id]}
                              active={selected?.id === c.id}
                              onSelect={() => selectClip(c)}
                              onRemove={() =>
                                task(() =>
                                  saveBoard(
                                    board.map((b) => ({
                                      ...b,
                                      selections: b.selections.filter(
                                        (x) => x.id !== c.id,
                                      ),
                                    })),
                                  ),
                                )
                              }
                              onMove={(delta) => moveClip(s.id, c.id, delta)}
                            />
                          ))}
                        </SortableContext>
                      </StorySection>
                    ))}
                    {!board.length && (
                      <div className="empty-board">
                        <div className="empty-board-art">
                          <span />
                          <span />
                          <span />
                        </div>
                        <h3>Every story starts somewhere.</h3>
                        <p>
                          Create a section for an idea, a feeling, or a moment.
                          <br />
                          Then pull in footage to make it yours.
                        </p>
                      </div>
                    )}
                    <button
                      className="add-section"
                      onClick={() =>
                        setSectionDialog({ title: "", purpose: "" })
                      }
                    >
                      <Plus size={16} /> Add story section
                    </button>
                  </div>
                  {latestProposal?.result?.sections && (
                    <div className="suggestions">
                      <div className="suggestion-heading">
                        <Sparkles size={15} />
                        <strong>Suggested structure</strong>
                        <span>Nothing changes until you choose.</span>
                      </div>
                      {latestProposal.result.sections.map((s, i) => (
                        <div className="suggestion" key={i}>
                          <strong>{s.title}</strong>
                          <p>{s.purpose}</p>
                          <small>
                            {s.candidate_ids.length} candidate moments
                          </small>
                          <button
                            className="text-button"
                            onClick={() =>
                              task(async () => {
                                const sid = id();
                                await saveBoard([
                                  ...board,
                                  {
                                    id: sid,
                                    title: s.title,
                                    purpose: s.purpose,
                                    selections: [],
                                  },
                                ]);
                                setActiveSection(sid);
                              })
                            }
                          >
                            <Plus size={12} /> Add empty section
                          </button>
                          <div className="candidate-list">
                            {s.candidate_ids.map((mid) => {
                              const m = project.moments.find(
                                (m) => m.id === mid,
                              );
                              return (
                                m && (
                                  <button
                                    key={mid}
                                    onClick={() => playMoment(m)}
                                  >
                                    {m.description}
                                    <Play size={12} />
                                  </button>
                                )
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <footer className="assembly-footer">
                    <span>
                      <Film size={14} /> {clips.length} clips{" "}
                      <span className="divider">/</span> {duration.toFixed(1)}{" "}
                      seconds
                    </span>
                    <button
                      className="text-button"
                      disabled={!clips.length}
                      onClick={() => {
                        setSequenceIndex(0);
                        setPreview(clips[0]);
                        setSelected(null);
                      }}
                    >
                      <Play size={14} /> Play assembly
                    </button>
                  </footer>
                </section>
                <aside className="inspector">
                  <div className="panel-heading">
                    <h2>
                      {sequenceIndex !== null ? "Assembly playback" : "Preview"}
                    </h2>
                    <span className="subtle">
                      {preview ? timecode(preview.start_frame) : "—"}
                    </span>
                  </div>
                  <div className="player">
                    {preview ? (
                      <video
                        ref={video}
                        key={preview.asset_id}
                        controls
                        preload="auto"
                        playsInline
                        src={`/api/assets/${preview.asset_id}/proxy`}
                        onTimeUpdate={() => {
                          if (
                            video.current &&
                            video.current.currentTime >= preview.end_frame / 30
                          )
                            advance();
                        }}
                        onEnded={advance}
                      />
                    ) : (
                      <div>
                        <Film size={32} />
                        <p>
                          Select a moment
                          <br />
                          to take a closer look.
                        </p>
                      </div>
                    )}
                  </div>
                  {preview && (
                    <div className="preview-info">
                      <strong>{assetMap[preview.asset_id]?.name}</strong>
                      <p>
                        {"description" in preview
                          ? preview.description
                          : preview.note || "Selected for your story"}
                      </p>
                      <span className="range">
                        {timecode(preview.start_frame)} —{" "}
                        {timecode(preview.end_frame)}
                      </span>
                      {!selected && "description" in preview && (
                        <button
                          className="secondary wide"
                          onClick={() => add(preview)}
                        >
                          <Plus size={14} /> Add to{" "}
                          {active?.title || "a new section"}
                        </button>
                      )}
                    </div>
                  )}
                  {selected && (
                    <div className="trim-panel">
                      <h3>
                        <Scissors size={14} /> Refine selection
                      </h3>
                      <div className="trim-fields">
                        <label>
                          In · frame
                          <input
                            type="number"
                            min="0"
                            value={trimStart}
                            onChange={(e) =>
                              setTrimStart(Number(e.target.value))
                            }
                          />
                        </label>
                        <label>
                          Out · frame
                          <input
                            type="number"
                            min="1"
                            value={trimEnd}
                            onChange={(e) => setTrimEnd(Number(e.target.value))}
                          />
                        </label>
                      </div>
                      <small>
                        30 frames = 1 second. Out point is exclusive.
                      </small>
                      <label>
                        Editor's note
                        <textarea
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          placeholder="Why this moment belongs…"
                        />
                      </label>
                      <button
                        className="secondary wide"
                        onClick={() =>
                          task(async () => {
                            const updated = {
                              ...selected,
                              start_frame: trimStart,
                              end_frame: trimEnd,
                              note,
                            };
                            await saveBoard(
                              board.map((s) => ({
                                ...s,
                                selections: s.selections.map((c) =>
                                  c.id === selected.id ? updated : c,
                                ),
                              })),
                            );
                            selectClip(updated);
                          })
                        }
                      >
                        Apply changes
                      </button>
                    </div>
                  )}
                  {preview && (
                    <button
                      className="text-button describe"
                      onClick={() => {
                        const description = window.prompt(
                          "Describe this moment so you can find it later:",
                        );
                        if (description)
                          task(async () => {
                            await api(
                              `/assets/${preview.asset_id}/moments`,
                              "POST",
                              {
                                start_frame: preview.start_frame,
                                end_frame: preview.end_frame,
                                description,
                              },
                            );
                            await refresh();
                          });
                      }}
                    >
                      + Save a searchable description
                    </button>
                  )}
                  <div className="inspector-note">
                    <span className="eyebrow">YOUR CREATIVE CALL</span>
                    <p>
                      Find possibilities here.
                      <br />
                      Finish the details in Resolve.
                    </p>
                    <small>
                      Export uses your 30 fps editing copies. Original footage
                      is never changed.
                    </small>
                  </div>
                </aside>
              </div>
            </DndContext>
            {showJobs && (
              <section className="jobs-panel">
                <div className="panel-heading">
                  <h2>Processing & exports</h2>
                  <button
                    className="icon"
                    onClick={() => setShowJobs(false)}
                    aria-label="Close processing"
                  >
                    <X size={16} />
                  </button>
                </div>
                {!project.jobs.length && <p>No work queued yet.</p>}
                {project.jobs.map((j) => (
                  <div className="job" key={j.id}>
                    <span className={"job-dot " + j.status} />
                    <div>
                      <strong>
                        {j.kind} <small>{j.status}</small>
                      </strong>
                      <p>{j.message}</p>
                      {j.status === "running" && (
                        <progress max={1} value={j.progress} />
                      )}
                    </div>
                    {["failed", "cancelled"].includes(j.status) && (
                      <button
                        className="secondary"
                        onClick={() =>
                          task(async () => {
                            await api(`/jobs/${j.id}/retry`, "POST");
                            await refresh();
                          })
                        }
                      >
                        Retry
                      </button>
                    )}
                    {["running", "queued"].includes(j.status) && (
                      <button
                        className="text-button"
                        onClick={() =>
                          task(async () => {
                            await api(`/jobs/${j.id}/cancel`, "POST");
                            await refresh();
                          })
                        }
                      >
                        Cancel
                      </button>
                    )}
                    {j.result?.url && (
                      <a className="secondary" href={j.result.url}>
                        <Download size={13} />{" "}
                        {j.kind === "export" ? "Resolve XML" : "Preview MP4"}
                      </a>
                    )}
                    {j.kind === "export" && j.status === "done" && (
                      <a
                        className="text-button"
                        href={`/api/jobs/${j.id}/download?format=json`}
                      >
                        Story notes
                      </a>
                    )}
                  </div>
                ))}
              </section>
            )}
          </>
        )}
      </main>
      {newProject && (
        <div className="modal-backdrop">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              task(async () => {
                const p = await api<{ id: string }>("/projects", "POST", {
                  name: projectName,
                  brief: "",
                });
                setPid(p.id);
                setNewProject(false);
                setProjectName("");
                await refresh();
              });
            }}
          >
            <span className="eyebrow">A NEW STORY</span>
            <h2>Name your project</h2>
            <label>
              Project name
              <input
                autoFocus
                required
                maxLength={100}
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="Saturday training session"
              />
            </label>
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setNewProject(false)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy}>
                Create project <ArrowUpRight size={14} />
              </button>
            </div>
          </form>
        </div>
      )}
      {sectionDialog && (
        <div className="modal-backdrop">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              task(async () => {
                const d = sectionDialog;
                await saveBoard(
                  d.id
                    ? board.map((s) =>
                        s.id === d.id
                          ? { ...s, title: d.title, purpose: d.purpose }
                          : s,
                      )
                    : [
                        ...board,
                        {
                          id: id(),
                          title: d.title,
                          purpose: d.purpose,
                          selections: [],
                        },
                      ],
                );
                setSectionDialog(null);
              });
            }}
          >
            <h2>
              {sectionDialog.id ? "Shape this section" : "Add a story section"}
            </h2>
            <label>
              Section title
              <input
                autoFocus
                required
                maxLength={120}
                value={sectionDialog.title}
                onChange={(e) =>
                  setSectionDialog({ ...sectionDialog, title: e.target.value })
                }
                placeholder="Show the work"
              />
            </label>
            <label>
              What should it contribute?
              <textarea
                maxLength={1000}
                value={sectionDialog.purpose}
                onChange={(e) =>
                  setSectionDialog({
                    ...sectionDialog,
                    purpose: e.target.value,
                  })
                }
                placeholder="Build a sense of progression through repeated attempts."
              />
            </label>
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setSectionDialog(null)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy}>
                Save section
              </button>
            </div>
          </form>
        </div>
      )}
      {provenance && (
        <div className="modal-backdrop">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              task(async () => {
                await api(
                  `/assets/${provenance.id}/provenance`,
                  "PUT",
                  provenance.provenance,
                );
                setProvenance(null);
                await refresh();
              });
            }}
          >
            <h2>Source & permissions</h2>
            <p>{provenance.name}</p>
            {(["source", "author", "license"] as const).map((key) => (
              <label key={key}>
                {key}
                <input
                  value={provenance.provenance[key] || ""}
                  onChange={(e) =>
                    setProvenance({
                      ...provenance,
                      provenance: {
                        ...provenance.provenance,
                        [key]: e.target.value,
                      },
                    })
                  }
                />
              </label>
            ))}
            {(["cloud_analysis", "training", "redistribution"] as const).map(
              (key) => (
                <label className="check-label" key={key}>
                  <input
                    type="checkbox"
                    checked={!!provenance.provenance[key]}
                    onChange={(e) =>
                      setProvenance({
                        ...provenance,
                        provenance: {
                          ...provenance.provenance,
                          [key]: e.target.checked,
                        },
                      })
                    }
                  />
                  {
                    {
                      cloud_analysis:
                        "I have permission to send this footage for cloud analysis",
                      training:
                        "I have permission to use this footage for model training",
                      redistribution:
                        "I have permission to redistribute this footage",
                    }[key]
                  }
                </label>
              ),
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setProvenance(null)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy}>
                Save permissions
              </button>
            </div>
          </form>
        </div>
      )}
      {analysisEstimate !== null && (
        <div className="modal-backdrop">
          <div className="modal">
            <span className="eyebrow">OPTIONAL CLOUD ANALYSIS</span>
            <h2>Find moments in your footage</h2>
            <p>
              This sends reduced-resolution video to Google Gemini. All{" "}
              {readyAssets.length} prepared clips must have cloud-analysis
              permission recorded.
            </p>
            <div className="estimate">
              ${analysisEstimate.toFixed(3)}
              <small>estimated maximum before cache savings</small>
            </div>
            <p>
              Provider charges can differ. Requests stop at the local $
              {status?.limit} guardrail.
            </p>
            <div className="modal-actions">
              <button
                className="secondary"
                onClick={() => setAnalysisEstimate(null)}
              >
                Cancel
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  task(async () => {
                    await api(`/projects/${pid}/analyze`, "POST", {
                      asset_ids: readyAssets.map((a) => a.id),
                    });
                    setAnalysisEstimate(null);
                    setShowJobs(true);
                    await refresh();
                  })
                }
              >
                Analyze clips
              </button>
            </div>
          </div>
        </div>
      )}
      {label && (
        <div className="modal-backdrop">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              task(async () => {
                await api(`/projects/${pid}/feedback`, "POST", {
                  moment_id: label.id,
                  section:
                    active?.purpose || active?.title || "Training montage",
                  query,
                  rating,
                  reason: labelReason,
                  footage_group: group,
                });
                setLabel(null);
                setNotice("Training judgment saved");
              });
            }}
          >
            <h2>Teach the ranking system</h2>
            <p>{label.description}</p>
            <p>
              Relevance to:{" "}
              <strong>{active?.title || "Training montage"}</strong>
            </p>
            <label>
              Judgment
              <select
                value={rating}
                onChange={(e) => setRating(Number(e.target.value))}
              >
                <option value={2}>Strong fit</option>
                <option value={1}>Possible fit</option>
                <option value={0}>Not relevant</option>
              </select>
            </label>
            <label>
              Why?
              <textarea
                value={labelReason}
                onChange={(e) => setLabelReason(e.target.value)}
              />
            </label>
            <label>
              Footage group
              <input
                required
                value={group}
                onChange={(e) => setGroup(e.target.value)}
              />
            </label>
            <small>
              Keep clips from the same shoot in one group to prevent train/test
              leakage. Training permission is required.
            </small>
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setLabel(null)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy}>
                Save judgment
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
