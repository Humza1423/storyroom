import { ImportController } from "./features/library/imports/controller";
import { ImportPanel } from "./features/library/imports/ImportPanel";
import { footageSummary } from "./features/library/imports/presentation";
import { ProcessingPanel } from "./components/ProcessingPanel";
import { Player } from "./features/preview/Player";
import { moveSelection } from "./features/board/changes";
import { StorySection } from "./features/board/StorySection";
import { ClipRow } from "./features/board/ClipRow";
import { MomentCard } from "./features/library/MomentCard";
import { VisualCandidateCard } from "./features/library/VisualCandidateCard";
import React, {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  closestCenter,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
  sortableKeyboardCoordinates,
} from "@dnd-kit/sortable";
import {
  Film,
  Plus,
  Search,
  Upload,
  ArrowUpRight,
  Play,
  X,
  Sparkles,
  Undo2,
  ChevronRight,
  Circle,
  Check,
  Loader2,
  FolderOpen,
  Settings2,
  Scissors,
  HelpCircle,
} from "lucide-react";

import type {
  Asset,
  Moment,
  SearchResult,
  VisualSearchResponse,
  Selection,
  Section,
  Project,
  Status,
  VisualCandidate,
  VisualIndexEstimate,
} from "./types";
import { api } from "./lib/api";
import { timecode } from "./lib/timecode";
const id = () => crypto.randomUUID();

export default function App() {
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]),
    [pid, setPid] = useState(localStorage.getItem("storyroom.project") || "");
  const [project, setProject] = useState<Project | null>(null),
    [status, setStatus] = useState<Status | null>(null);
  const [connection, setConnection] = useState<
    "loading" | "connected" | "disconnected"
  >("loading");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const [query, setQuery] = useState(""),
    [results, setResults] = useState<SearchResult[] | null>(null),
    [searchWarning, setSearchWarning] = useState(""),
    [visualSearchBusy, setVisualSearchBusy] = useState(false),
    [visualPage, setVisualPage] = useState<number | null>(null),
    [visualHasMore, setVisualHasMore] = useState(false),
    [visualPagingBusy, setVisualPagingBusy] = useState(false),
    [visualPagingError, setVisualPagingError] = useState(""),
    [searchMode, setSearchMode] = useState<
      "keyword" | "description" | "visual"
    >("keyword");
  const [activeSection, setActiveSection] = useState(""),
    [selected, setSelected] = useState<Selection | null>(null),
    [preview, setPreview] = useState<
      Moment | Selection | VisualCandidate | null
    >(null);
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
    [visualEstimate, setVisualEstimate] = useState<VisualIndexEstimate | null>(
      null,
    ),
    [showJobs, setShowJobs] = useState(false),
    [showGuide, setShowGuide] = useState(false),
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
  const activePid = useRef(pid);
  activePid.current = pid;
  const boardEpoch = useRef(0);
  const searchEpoch = useRef(0);
  const [imports] = useState(
    () =>
      new ImportController({
        request: api,
        refresh: async (destination) => {
          const refreshed = await api<Project>(`/projects/${destination}`);
          // Import completion is about media, not a replacement for board/draft state.
          if (activePid.current === destination)
            setProject((current) =>
              current?.id === destination
                ? {
                    ...current,
                    assets: refreshed.assets,
                    moments: refreshed.moments,
                    jobs: refreshed.jobs,
                  }
                : current,
            );
          return refreshed.assets;
        },
      }),
  );
  const importState = useSyncExternalStore(
    imports.subscribe,
    imports.getSnapshot,
  );
  useEffect(() => () => imports.dispose(), [imports]);

  async function refresh() {
    const [ps, st] = await Promise.all([
      api<{ id: string; name: string }[]>("/projects"),
      api<Status>("/status"),
    ]);
    setProjects(ps);
    setStatus(st);
    setConnection("connected");
    if (pid && !ps.some((p) => p.id === pid)) {
      localStorage.removeItem("storyroom.project");
      setPid(ps[0]?.id || "");
      setProject(null);
      setError("");
      return;
    }
    if (pid) {
      const p = await api<Project>("/projects/" + pid);
      if (activePid.current === pid) setProject(p);
    }
  }
  async function task(
    fn: () => Promise<void>,
    stillRelevant: () => boolean = () => true,
  ) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      if (stillRelevant()) setError((e as Error).message);
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
        setConnection("connected");
        if (pid && !ps.some((p) => p.id === pid)) {
          localStorage.removeItem("storyroom.project");
          setPid(ps[0]?.id || "");
          setProject(null);
          setError("");
          return;
        }
        if (pid) {
          const epoch = boardEpoch.current;
          const p = await api<Project>("/projects/" + pid);
          if (!stopped && !saving.current && epoch === boardEpoch.current)
            setProject(p);
        }
      } catch (e) {
        if (!stopped) setConnection("disconnected");
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
    let stopped = false;
    setProject(null);
    setResults(null);
    setSearchWarning("");
    searchEpoch.current += 1;
    setVisualPage(null);
    setVisualHasMore(false);
    setVisualSearchBusy(false);
    setVisualPagingBusy(false);
    setVisualPagingError("");
    setPreview(null);
    setSelected(null);
    setActiveSection("");
    setSequenceIndex(null);
    if (pid) {
      localStorage.setItem("storyroom.project", pid);
      api<Project>("/projects/" + pid)
        .then((p) => {
          if (stopped) return;
          setProject(p);
          setBrief(p.brief);
          setGroup(p.id);
        })
        .catch((e) => {
          if (!stopped) setError(e.message);
        });
    }
    return () => {
      stopped = true;
    };
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
  const readyAssets = project?.assets.filter((a) => a.status === "ready") || [];
  const visibleResults: SearchResult[] =
    results ?? (searchMode === "visual" ? [] : (project?.moments ?? []));
  const visualReadyAssets = readyAssets.filter(
    (a) => a.provenance.cloud_analysis,
  );
  const demoOnlyFootage =
    readyAssets.length > 0 &&
    readyAssets.every((a) =>
      a.provenance.license?.toLowerCase().includes("demo/workflow only"),
    );
  const activeVisualJobs =
    project?.jobs.filter(
      (j) =>
        j.kind === "visual_index" && ["queued", "running"].includes(j.status),
    ) ?? [];
  const latestVisualJob = project?.jobs.find((j) => j.kind === "visual_index");
  const duration =
    clips.reduce((n, c) => n + c.end_frame - c.start_frame, 0) / 30;
  const nextStep = !readyAssets.length
    ? "Import a clip to begin."
    : !board.length
      ? "Search your footage, then create a Storybin to collect moments."
      : !clips.length
        ? "Preview a moment and add it to the selected Storybin."
        : "Play your assembly, adjust cuts, then render or export.";
  async function checkMoreVisualMoments() {
    if (
      searchMode !== "visual" ||
      visualPage === null ||
      visualPage >= 7 ||
      !visualHasMore ||
      visualPagingBusy ||
      visualSearchBusy
    )
      return;
    const requestEpoch = searchEpoch.current;
    const submittedPid = pid;
    const nextPage = visualPage + 1;
    const submittedQuery = query;
    setVisualPagingBusy(true);
    setVisualPagingError("");
    try {
      const response = await api<VisualSearchResponse>(
        `/projects/${submittedPid}/search`,
        "POST",
        { query: submittedQuery, mode: "visual", page: nextPage },
        120000,
      );
      if (
        searchEpoch.current !== requestEpoch ||
        activePid.current !== submittedPid
      )
        return;
      setResults((current) => {
        const existing = (current ?? []).filter(
          (result): result is VisualCandidate =>
            "kind" in result && result.kind === "visual",
        );
        const ids = new Set(existing.map((candidate) => candidate.id));
        const ranges = new Set(
          existing.map(
            (candidate) =>
              `${candidate.asset_id}:${candidate.start_frame}:${candidate.end_frame}`,
          ),
        );
        const added = response.results.filter((candidate) => {
          const range = `${candidate.asset_id}:${candidate.start_frame}:${candidate.end_frame}`;
          if (ids.has(candidate.id) || ranges.has(range)) return false;
          ids.add(candidate.id);
          ranges.add(range);
          return true;
        });
        return [...existing, ...added];
      });
      setVisualPage(response.page);
      setVisualHasMore(response.has_more && response.page < 7);
      setSearchWarning(response.warning ?? "");
    } catch (error) {
      if (
        searchEpoch.current === requestEpoch &&
        activePid.current === submittedPid
      )
        setVisualPagingError((error as Error).message);
    } finally {
      if (
        searchEpoch.current === requestEpoch &&
        activePid.current === submittedPid
      )
        setVisualPagingBusy(false);
    }
  }
  function jumpTo(id: string) {
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function revealPlayer() {
    if (window.matchMedia("(max-width: 850px)").matches)
      requestAnimationFrame(() => jumpTo("player"));
  }
  async function saveBoard(next: Section[]) {
    if (!project || saving.current) return;
    saving.current = true;
    boardEpoch.current++;
    try {
      const r = await api<{ revision: number }>(
        `/projects/${pid}/board`,
        "PUT",
        { revision: project.revision, sections: next },
      );
      if (activePid.current !== pid) return;
      // Imports can finish while this save is pending. Apply only the fields
      // this request owns to the latest project, preserving newer media/jobs.
      setProject((current) =>
        current?.id === pid
          ? { ...current, board: next, revision: r.revision }
          : current,
      );
      setNotice("All changes saved");
    } catch (e) {
      await refresh();
      throw e;
    } finally {
      saving.current = false;
      boardEpoch.current++;
    }
  }
  function add(moment: Moment | VisualCandidate, sectionId = active?.id) {
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
        moment_id: "kind" in moment ? null : moment.id,
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
    revealPlayer();
  }
  function playMoment(m: Moment | VisualCandidate) {
    setPreview(m);
    setSelected(null);
    setSequenceIndex(null);
    revealPlayer();
  }
  function advance() {
    if (sequenceIndex === null) {
      video.current?.pause();
      return;
    }
    const next = sequenceIndex + 1;
    if (next >= clips.length) {
      video.current?.pause();
      setSequenceIndex(null);
      setPreview(null);
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
  async function estimateVisualIndex() {
    if (!visualReadyAssets.length) return;
    const estimate = await api<VisualIndexEstimate>(
      `/projects/${pid}/visual-index-estimate`,
      "POST",
      { asset_ids: visualReadyAssets.map((a) => a.id) },
    );
    setVisualEstimate(estimate);
  }
  async function startVisualIndex() {
    if (!visualEstimate || !visualReadyAssets.length) return;
    await api<{ job_ids: string[] }>(`/projects/${pid}/visual-index`, "POST", {
      asset_ids: visualReadyAssets.map((a) => a.id),
    });
    setVisualEstimate(null);
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
    const visualCandidate = e.active.data.current?.visualCandidate as
      VisualCandidate | undefined;
    const target = String(e.over.id);
    const targetSection = target.startsWith("section:")
      ? target.slice(8)
      : board.find((s) => s.selections.some((c) => c.id === target))?.id;
    if (!targetSection) return;
    if (moment) {
      add(moment, targetSection);
      return;
    }
    if (visualCandidate) {
      add(visualCandidate, targetSection);
      return;
    }
    task(async () => {
      const next = moveSelection(
        board,
        String(e.active.id),
        targetSection,
        target,
      );
      await saveBoard(next);
    });
  }
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
              <small>/ ${status?.limit ?? 45}</small>
            </strong>
            <progress max={status?.limit ?? 45} value={status?.spend || 0} />
          </div>
        </div>
      </aside>
      <main>
        <div
          role="status"
          aria-label="Connection"
          className="connection-status"
        >
          {connection === "loading" ? (
            "Connecting to local server…"
          ) : connection === "connected" ? (
            "Connected to local server"
          ) : (
            <>
              Server disconnected. Your open project and draft text are kept
              here. Check the launcher, then retry.
              <button
                className="secondary"
                onClick={() =>
                  task(async () => {
                    try {
                      await refresh();
                    } catch (e) {
                      setConnection("disconnected");
                      throw e;
                    }
                  })
                }
              >
                Reconnect
              </button>
            </>
          )}
        </div>
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
                <span className="eyebrow">LOCAL EDITING WORKSPACE</span>
                <h1>{project.name}</h1>
                <p>{nextStep}</p>
              </div>
              <div className="project-actions">
                <span className="save-status">
                  <Check size={13} />
                  {connection !== "connected"
                    ? connection === "loading"
                      ? "Connecting…"
                      : "Disconnected"
                    : busy
                      ? "Working…"
                      : notice || "Saved locally"}
                </span>
                <button
                  className="secondary"
                  onClick={() => setShowGuide(true)}
                >
                  <HelpCircle size={15} /> How to use
                </button>
                <button
                  className="secondary"
                  onClick={() => setShowJobs(!showJobs)}
                >
                  {activeJobs.length ? (
                    <Loader2 className="spin" size={14} />
                  ) : (
                    <Circle size={12} />
                  )}{" "}
                  Activity{" "}
                  {activeJobs.length > 0 && (
                    <span className="badge">{activeJobs.length}</span>
                  )}
                </button>
              </div>
            </div>
            <nav className="workflow-nav" aria-label="Workspace steps">
              {[
                ["footage", "1", "Footage"],
                ["find-moments", "2", "Find moments"],
                ["storybins", "3", "Storybins"],
                ["player", "4", "Player"],
              ].map(([target, number, label]) => (
                <button key={target} onClick={() => jumpTo(target)}>
                  <span>{number}</span>
                  {label}
                </button>
              ))}
            </nav>
            <details className="brief-details">
              <summary>
                Creative brief{" "}
                <span>Optional · plan your story or ask for suggestions</span>
              </summary>
              <div className="brief-bar">
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
                  Story suggestions are unavailable on this server. Manual
                  editing and visual search still work independently.
                </div>
              )}
            </details>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={onDragEnd}
            >
              <div className={"workspace " + (busy ? "working" : "")}>
                <section className="library" id="footage">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        1. Footage <span>{project.assets.length} clips</span>
                      </h2>
                      <p>Import clips. Originals are never changed.</p>
                    </div>
                    <button
                      className="secondary import-button"
                      onClick={() => fileInput.current?.click()}
                      aria-label="Import footage"
                      disabled={importState.busy}
                    >
                      <Plus size={15} /> Import
                    </button>
                  </div>
                  <input
                    ref={fileInput}
                    type="file"
                    accept="video/mp4"
                    disabled={importState.busy}
                    multiple
                    hidden
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []);
                      void imports.start(project.id, project.name, files);
                      e.target.value = "";
                    }}
                  />
                  <p
                    className="footage-summary"
                    role="status"
                    aria-label="Footage summary"
                  >
                    {footageSummary(project.assets)}
                  </p>
                  <ImportPanel
                    controller={imports}
                    projectId={project.id}
                    assets={project.assets}
                  />
                  {!!project.assets.length && (
                    <div className="asset-list">
                      <strong>Clips & permissions</strong>
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
                            title="Source and cloud-analysis permission"
                            aria-label={"Permissions for " + a.name}
                          >
                            <Settings2 size={15} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="search-heading" id="find-moments">
                    <h2>2. Find moments</h2>
                    <p>
                      Search a filename or label, or search what is visible in
                      indexed video.
                    </p>
                  </div>
                  <form
                    className="search-bar"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (
                        searchMode === "visual" &&
                        (!status?.visual_ai_ready || !visualReadyAssets.length)
                      )
                        return;
                      const requestEpoch = ++searchEpoch.current;
                      const submittedQuery = query;
                      const submittedMode = searchMode;
                      const submittedPid = pid;
                      task(
                        async () => {
                          setSearchWarning("");
                          setResults(null);
                          setVisualPage(null);
                          setVisualHasMore(false);
                          setVisualPagingError("");
                          if (submittedMode === "visual") {
                            setVisualSearchBusy(true);
                            try {
                              const response = await api<VisualSearchResponse>(
                                `/projects/${submittedPid}/search`,
                                "POST",
                                {
                                  query: submittedQuery,
                                  mode: submittedMode,
                                  page: 0,
                                },
                                120000,
                              );
                              if (
                                searchEpoch.current === requestEpoch &&
                                activePid.current === submittedPid
                              ) {
                                setResults(response.results);
                                setSearchWarning(response.warning ?? "");
                                setVisualPage(response.page);
                                setVisualHasMore(
                                  response.has_more && response.page < 7,
                                );
                              }
                            } finally {
                              if (
                                searchEpoch.current === requestEpoch &&
                                activePid.current === submittedPid
                              )
                                setVisualSearchBusy(false);
                            }
                          } else {
                            const found = await api<SearchResult[]>(
                              `/projects/${submittedPid}/search`,
                              "POST",
                              { query: submittedQuery, mode: submittedMode },
                            );
                            if (
                              searchEpoch.current === requestEpoch &&
                              activePid.current === submittedPid
                            )
                              setResults(found);
                          }
                        },
                        () =>
                          searchEpoch.current === requestEpoch &&
                          activePid.current === submittedPid,
                      );
                    }}
                  >
                    <Search size={15} />
                    <input
                      aria-label="Search footage"
                      placeholder={
                        searchMode === "visual"
                          ? "e.g. jumping jacks"
                          : "Search footage…"
                      }
                      value={query}
                      onChange={(e) => {
                        searchEpoch.current += 1;
                        setQuery(e.target.value);
                        setResults(null);
                        setSearchWarning("");
                        setVisualPage(null);
                        setVisualHasMore(false);
                        setVisualSearchBusy(false);
                        setVisualPagingBusy(false);
                        setVisualPagingError("");
                      }}
                    />
                    <button
                      type="submit"
                      className="icon"
                      aria-label="Search"
                      disabled={
                        busy ||
                        !query.trim() ||
                        (searchMode === "description" && !status?.ai_ready) ||
                        (searchMode === "visual" &&
                          (!status?.visual_ai_ready ||
                            !visualReadyAssets.length))
                      }
                    >
                      <ChevronRight size={16} />
                    </button>
                  </form>
                  <div className="library-tools">
                    <label>
                      Search mode
                      <select
                        aria-label="Search mode"
                        value={searchMode}
                        onChange={(e) => {
                          searchEpoch.current += 1;
                          setSearchMode(e.target.value as typeof searchMode);
                          setResults(null);
                          setSearchWarning("");
                          setVisualPage(null);
                          setVisualHasMore(false);
                          setVisualSearchBusy(false);
                          setVisualPagingBusy(false);
                          setVisualPagingError("");
                        }}
                      >
                        <option value="keyword">Keyword</option>
                        <option
                          value="description"
                          disabled={!status?.ai_ready}
                        >
                          Description AI
                        </option>
                        <option
                          value="visual"
                          disabled={!status?.visual_ai_ready}
                        >
                          Visual AI
                        </option>
                      </select>
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
                  <p className="search-explainer">
                    {searchMode === "visual"
                      ? "Visual AI compares your words with the video itself. Indexing is required once per clip. Results are approximate—watch before adding."
                      : searchMode === "description"
                        ? "Description AI searches AI-written clip descriptions, not the video directly."
                        : "Keyword searches filenames and saved descriptions. It does not inspect the video."}
                  </p>
                  {searchMode === "visual" && !visualReadyAssets.length && (
                    <p className="search-explainer" role="status">
                      {demoOnlyFootage
                        ? "This project's clips are marked demo-only, so Visual AI cannot index them. Open or import footage you have permission to send for cloud analysis."
                        : "No clips are approved for Visual AI yet. Open a clip's permissions in Footage, record its source, and allow cloud analysis before indexing."}
                    </p>
                  )}
                  {searchMode === "visual" && (
                    <div className="visual-index-box">
                      <strong>Search what is visible in the video</strong>
                      <p>
                        Index only prepared clips that have cloud-analysis
                        permission recorded.
                        {status?.embedding_model
                          ? ` Model: ${status.embedding_model}.`
                          : ""}
                      </p>
                      <button
                        className="secondary wide"
                        disabled={
                          !status?.visual_ai_ready ||
                          (status?.embedding_tier === "unpaid" &&
                            !status.unpaid_terms_acknowledged) ||
                          !visualReadyAssets.length ||
                          busy ||
                          activeVisualJobs.length > 0
                        }
                        onClick={() => task(estimateVisualIndex)}
                      >
                        <Sparkles size={13} />
                        {activeVisualJobs.length
                          ? "Visual indexing in progress"
                          : "Estimate & index permitted clips"}
                      </button>
                      {!visualReadyAssets.length && (
                        <small>
                          Choose source and cloud-analysis permission for a
                          ready clip using its settings button in Footage above.
                        </small>
                      )}
                      {!status?.visual_ai_ready && (
                        <small>
                          Visual search is not configured on this local
                          Storyroom server yet.
                        </small>
                      )}
                      {status?.embedding_tier === "unpaid" && (
                        <small className="privacy-note">
                          Google’s unpaid Gemini service may use submitted video
                          to improve Google products, and human reviewers may
                          process it. Do not send sensitive, confidential, or
                          personal footage. Indexing is never automatic; only
                          the clips with cloud-analysis permission above are
                          sent.
                        </small>
                      )}
                      {status?.embedding_tier === "unpaid" &&
                        !status.unpaid_terms_acknowledged && (
                          <small>
                            The local server requires unpaid-service terms to be
                            acknowledged before indexing can start.
                          </small>
                        )}
                      {latestVisualJob && (
                        <div className="visual-progress" role="status">
                          <span>
                            {latestVisualJob.status === "running" ||
                            latestVisualJob.status === "queued"
                              ? "Indexing"
                              : "Last indexing job"}
                            : {latestVisualJob.message}
                          </span>
                          {activeVisualJobs.length > 0 && (
                            <progress
                              max={1}
                              value={latestVisualJob.progress}
                            />
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  {!project.assets.length && (
                    <button
                      className="import-zone"
                      onClick={() => fileInput.current?.click()}
                    >
                      <Upload size={25} />
                      <strong>Bring your footage in</strong>
                      <span>
                        SDR H.264 MP4 · up to 4K
                        <br />
                        30 clips · 15 minutes · 2 GB
                      </span>
                    </button>
                  )}
                  {results && (
                    <p className="result-count" role="status">
                      {results.length}{" "}
                      {results.length === 1 ? "result" : "results"} for “{query}
                      ”
                    </p>
                  )}
                  {visualSearchBusy && (
                    <p className="search-explainer" role="status">
                      Checking the top visual candidates against the footage…
                    </p>
                  )}
                  {visualPagingBusy && (
                    <p className="search-explainer" role="status">
                      Checking more visual moments…
                    </p>
                  )}
                  {searchWarning && (
                    <p className="search-explainer" role="alert">
                      {searchWarning}
                    </p>
                  )}
                  {visualPagingError && (
                    <p className="search-explainer" role="alert">
                      Could not check more moments: {visualPagingError}. Your
                      earlier matches are still available; try again.
                    </p>
                  )}
                  {active && (
                    <p className="add-target">
                      Add buttons place moments in:{" "}
                      <strong>{active.title}</strong>. Click another Storybin to
                      change the target.
                    </p>
                  )}
                  <div className="moments">
                    {visibleResults.map((result) =>
                      "kind" in result && result.kind === "visual" ? (
                        <VisualCandidateCard
                          key={result.id}
                          candidate={result}
                          asset={assetMap[result.asset_id]}
                          onPreview={() => playMoment(result)}
                          onAdd={() => add(result)}
                        />
                      ) : (
                        <MomentCard
                          key={result.id}
                          moment={result as Moment}
                          asset={assetMap[result.asset_id]}
                          onPreview={() => playMoment(result as Moment)}
                          onAdd={() => add(result as Moment)}
                          onLabel={() => {
                            setLabel(result as Moment);
                            setLabelReason("");
                          }}
                        />
                      ),
                    )}
                  </div>
                  {searchMode === "visual" &&
                    results !== null &&
                    visualHasMore && (
                      <button
                        type="button"
                        className="secondary wide"
                        onClick={checkMoreVisualMoments}
                        disabled={visualPagingBusy || visualSearchBusy || busy}
                        aria-label="Check more moments"
                      >
                        {visualPagingBusy
                          ? "Checking more moments…"
                          : "Check more moments"}
                      </button>
                    )}
                  {results?.length === 0 && !searchWarning && (
                    <div className="empty-small">
                      {searchMode === "visual"
                        ? visualHasMore
                          ? "No confirmed matches in the moments checked so far. Check more moments, or try a different description."
                          : "No confident visual matches. Try a different description or index more footage. Storyroom hides clips it cannot verify."
                        : "No matching moments. Try different words, add a description, or analyze your footage."}
                    </div>
                  )}
                </section>
                <section className="board-panel" id="storybins">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        3. Storybins{" "}
                        <span>
                          {board.length}{" "}
                          {board.length === 1 ? "section" : "sections"}
                        </span>
                      </h2>
                      <p>Choose a bin, add moments, then drag to reorder.</p>
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
                        <h3>No Storybins yet</h3>
                        <p>
                          Add a section such as “Warm-up” or “Best attempt.”
                          Then add moments from your footage.
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
                        revealPlayer();
                      }}
                    >
                      <Play size={14} /> Play assembly
                    </button>
                  </footer>
                </section>
                <aside className="inspector" id="player">
                  <div className="panel-heading">
                    <h2>
                      {sequenceIndex !== null
                        ? "Assembly playback"
                        : "4. Player"}
                    </h2>
                    <span className="subtle">
                      {sequenceIndex !== null
                        ? `Clip ${sequenceIndex + 1} of ${clips.length}`
                        : preview
                          ? timecode(preview.start_frame)
                          : "—"}
                    </span>
                  </div>
                  <Player
                    preview={preview}
                    video={video}
                    advance={advance}
                    assembly={sequenceIndex !== null}
                  />
                  <p className="player-help">
                    Play Assembly shows only the selected ranges, one after
                    another. Render preview creates a cut MP4.
                  </p>
                  <div className="handoff-actions">
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
                  {preview && (
                    <div className="preview-info">
                      <strong>{assetMap[preview.asset_id]?.name}</strong>
                      <p>
                        {"description" in preview
                          ? preview.description
                          : "kind" in preview
                            ? "Visual match candidate · range is approximate and can be trimmed after adding."
                            : preview.note || "Selected for your story"}
                      </p>
                      <span className="range">
                        {timecode(preview.start_frame)} —{" "}
                        {timecode(preview.end_frame)}
                      </span>
                      {!selected &&
                        ("description" in preview || "kind" in preview) && (
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
              <ProcessingPanel
                jobs={project.jobs}
                onClose={() => setShowJobs(false)}
                onAction={(id, action) =>
                  task(async () => {
                    await api(`/jobs/${id}/${action}`, "POST");
                    await refresh();
                  })
                }
              />
            )}
          </>
        )}
      </main>
      {showGuide && (
        <div className="modal-backdrop" onClick={() => setShowGuide(false)}>
          <div
            className="modal guide-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="guide-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="icon guide-close"
              aria-label="Close guide"
              onClick={() => setShowGuide(false)}
            >
              <X size={18} />
            </button>
            <span className="eyebrow">QUICK START</span>
            <h2 id="guide-title">How to use Storyroom</h2>
            <ol>
              <li>
                <strong>Import footage.</strong> Select MP4 clips. Storyroom
                makes editing and playback copies without changing your
                originals.
              </li>
              <li>
                <strong>Find a moment.</strong> Keyword looks at names and saved
                labels. Visual AI looks at video after you give cloud permission
                and explicitly index it. Click any result to watch its suggested
                range.
              </li>
              <li>
                <strong>Build Storybins.</strong> Add a section, click it to
                choose where new moments go, then use “Add to section.” Click a
                clip in a bin to trim its in/out frames. Changes save
                automatically.
              </li>
              <li>
                <strong>Check and export.</strong> Play Assembly plays your
                chosen ranges in order. Render preview makes a cut MP4. Export
                to Resolve creates an editable XML timeline.
              </li>
            </ol>
            <p>
              <strong>Activity</strong> shows background work such as importing,
              indexing, rendering, and export. Visual AI results are candidates:
              watch and trim them; boundaries are not guaranteed exact.
            </p>
            <button className="primary" onClick={() => setShowGuide(false)}>
              Start editing
            </button>
          </div>
        </div>
      )}
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
      {visualEstimate !== null && (
        <div className="modal-backdrop">
          <div className="modal">
            <span className="eyebrow">VISUAL VIDEO INDEX</span>
            <h2>Index permitted footage?</h2>
            <p>
              Storyroom will send proxy-video samples to Google Gemini to create
              searchable visual vectors. Audio is not indexed. Only{" "}
              {visualReadyAssets.length} ready clip
              {visualReadyAssets.length === 1 ? "" : "s"} with cloud-analysis
              permission will be sent.
            </p>
            <div className="estimate">
              ${visualEstimate.estimated_usd.toFixed(3)}
              <small>
                {visualEstimate.segment_count} segments (
                {visualEstimate.missing_segment_count} new) ·{" "}
                {visualEstimate.frame_count} new sampled frames ·{" "}
                {visualEstimate.indexed_count} already indexed
              </small>
            </div>
            <p>
              {visualEstimate.tier === "unpaid"
                ? "Google unpaid-service tier: estimated API price is $0; quotas still apply."
                : "Paid tier estimate; provider billing remains authoritative."}{" "}
              {visualEstimate.quota_note}
            </p>
            {visualEstimate.tier === "unpaid" && (
              <p className="privacy-note">
                Google may use unpaid-service data to improve its products, and
                human reviewers may process it. Do not send sensitive,
                confidential, or personal footage. This indexing action is
                explicit; it will not start automatically.
              </p>
            )}
            <div className="modal-actions">
              <button
                className="secondary"
                onClick={() => setVisualEstimate(null)}
              >
                Cancel
              </button>
              <button
                className="primary"
                disabled={
                  busy ||
                  (visualEstimate.tier === "unpaid" &&
                    !status?.unpaid_terms_acknowledged)
                }
                onClick={() => task(startVisualIndex)}
              >
                Index {visualEstimate.missing_segment_count} new segments
              </button>
            </div>
          </div>
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
