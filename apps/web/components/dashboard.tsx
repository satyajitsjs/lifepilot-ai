"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity as ActivityIcon, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, CalendarDays, Check,
  CheckCheck, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, CircleCheck, Clock3,
  Command, Compass, Download, FolderKanban, Heart, Home, Layers3, LayoutDashboard,
  ListTodo, Loader2, LogOut, Mail, Menu, MessageCircle, MoreHorizontal, Plus, Search,
  Send, Settings2, ShieldCheck, Sparkles, Star, Users, WandSparkles, X, Zap,
  type LucideIcon,
} from "lucide-react";
import { VoiceInputButton, ReadAloudButton } from "@/components/voice-controls";
import {
  API, request, shortDate, timeOf,
  type Activity, type Bootstrap, type CalendarEvent, type Circle, type Notification,
  type Person, type Proposal, type Task,
} from "@/lib/api";

type View = "overview" | "assistant" | "tasks" | "circles" | "calendar" | "activity" | "settings";
type ModalType = "task" | "event" | "reminder" | "message" | "circle" | "invite" | null;
const demoSuggestions = [
  "Assign Rahul the backend API task by Friday and remind him tomorrow",
  "Schedule a design review meeting with Priya on Tuesday at 3 PM",
  "Send Priya a message about the project updates",
];
const nav: { view: View; label: string; icon: LucideIcon }[] = [
  { view: "overview", label: "Overview", icon: LayoutDashboard },
  { view: "assistant", label: "AI Assistant", icon: WandSparkles },
  { view: "tasks", label: "My Tasks", icon: ListTodo },
  { view: "circles", label: "My Circles", icon: Users },
  { view: "calendar", label: "Calendar", icon: CalendarDays },
  { view: "activity", label: "Activity", icon: ActivityIcon },
];
const firstName = (name?: string) => (name || "there").split(" ")[0];
const initials = (p?: Person) => p?.avatar || "?";
function Avatar({ person, size = "md", title }: { person?: Person; size?: "sm" | "md" | "lg"; title?: string }) {
  return <span className={`avatar avatar-${size} avatar-${person?.color || "indigo"}`} title={title || person?.name}>{initials(person)}</span>;
}
function IconPill({ children, color = "violet" }: { children: ReactNode; color?: string }) {
  return <span className={`icon-pill pill-${color}`}>{children}</span>;
}
function StatusPill({ value }: { value: Task["status"] }) {
  const names = { todo: "To do", in_progress: "In progress", done: "Completed" };
  return <span className={`status-pill status-${value}`}><i className="status-dot" />{names[value]}</span>;
}
function SectionHeading({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return <div className="section-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>;
}

export default function Dashboard() {
  const [token, setToken] = useState<string | null>(null);
  const [data, setData] = useState<Bootstrap | null>(null);
  const [view, setView] = useState<View>("overview");
  const [circleId, setCircleId] = useState("studio");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [activeProposal, setActiveProposal] = useState<Proposal | null>(null);
  const [modal, setModal] = useState<ModalType>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | Task["status"]>("all");

  const notice = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 4000);
  }, []);

  const reload = useCallback(async (key: string) => {
    const next = await request<Bootstrap>("/api/bootstrap", key);
    setData(next);
    setCircleId(previous => next.circles.some(c => c.id === previous) ? previous : (next.circles[0]?.id || "studio"));
  }, []);

  const login = useCallback(async (userId: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await request<{ token: string; user: Person }>("/api/auth/demo", null, {
        method: "POST", body: JSON.stringify({ user_id: userId }),
      });
      localStorage.setItem("lifepilot-demo-token", result.token);
      localStorage.setItem("lifepilot-demo-user", userId);
      setToken(result.token);
      await reload(result.token);
      setProfileOpen(false);
      setActiveProposal(null);
      notice(`Signed in as ${firstName(result.user.name)}`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); setLoading(false); }
  }, [notice, reload]);

  useEffect(() => {
    const saved = localStorage.getItem("lifepilot-demo-token");
    if (saved) {
      setToken(saved);
      reload(saved).catch(() => login(localStorage.getItem("lifepilot-demo-user") || "alex")).finally(() => setLoading(false));
    } else { login("alex").finally(() => setLoading(false)); }
  }, [login, reload]);

  const circle = data?.circles.find(c => c.id === circleId);
  const tasks = useMemo(() => (data?.tasks || []).filter(t => t.circle_id === circleId), [data?.tasks, circleId]);
  const events = useMemo(() => (data?.events || []).filter(e => e.circle_id === circleId), [data?.events, circleId]);
  const activity = useMemo(() => (data?.activity || []).filter(a => a.circle_id === circleId), [data?.activity, circleId]);
  const unread = (data?.notifications || []).filter(n => !n.read_at).length;
  const done = tasks.filter(t => t.status === "done").length;
  const pending = tasks.filter(t => t.status !== "done").length;
  const progress = tasks.length ? Math.round(done / tasks.length * 100) : 0;
  const team = data?.members || [];
  const greeting = new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening";

  async function createPlan(raw?: string) {
    const text = (raw || prompt).trim();
    if (!text || !token || busy) return;
    setBusy(true); setError(null);
    try {
      const proposal = await request<Proposal>("/api/assistant/plan", token, {
        method: "POST", body: JSON.stringify({ circle_id: circleId, prompt: text }),
      });
      setActiveProposal({ ...proposal, outcomes: [] });
      setPrompt("");
      await reload(token);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function decideProposal(approved: boolean) {
    if (!activeProposal || !token || busy) return;
    setBusy(true); setError(null);
    try {
      const result = await request<{ status: string; executed?: number; total?: number; outcomes?: Proposal["outcomes"] }>(
        `/api/proposals/${activeProposal.id}/${approved ? "approve" : "reject"}`, token, { method: "POST" },
      );
      setActiveProposal({ ...activeProposal, status: result.status, outcomes: result.outcomes || [] });
      await reload(token);
      notice(!approved ? "Plan rejected. Nothing was executed." : `${result.executed || 0}/${result.total || 0} actions completed`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function changeStatus(task: Task) {
    if (!token) return;
    const next = task.status === "todo" ? "in_progress" : task.status === "in_progress" ? "done" : "todo";
    try {
      await request(`/api/tasks/${task.id}`, token, { method: "PATCH", body: JSON.stringify({ status: next }) });
      await reload(token);
      notice(`Moved to ${next.replace("_", " ")}`);
    } catch (e) { setError((e as Error).message); }
  }

  async function markNotification(n: Notification) {
    if (!token || n.read_at) return;
    try {
      await request(`/api/notifications/${n.id}/read`, token, { method: "POST" });
      await reload(token);
    } catch (e) { setError((e as Error).message); }
  }

  function chooseView(next: View) {
    setView(next); setSidebarOpen(false); setError(null);
  }

  if (loading || !data) {
    return <div className="loading-screen"><div className="brand-logo"><Sparkles size={23}/></div><Loader2 className="spin"/><span>Warming up your workspace...</span>{error && <span className="error-text">{error}</span>}</div>;
  }

  const welcome = <div className="page-intro"><div><div className="eyebrow"><span className="eyebrow-dot" />YOUR WORKSPACE, IN SYNC</div><h1>{greeting}, {firstName(data.user.name)} <span className="wave">✳</span></h1><p>Here&apos;s what&apos;s happening in your circle today.</p></div><div className="intro-date"><CalendarDays size={17} /><span>{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</span></div></div>;

  return <div className="app-shell">
    {sidebarOpen && <button aria-label="Close sidebar" className="mobile-backdrop" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-logo"><Sparkles size={21} strokeWidth={2.4}/></div><div><strong>life<span>pilot</span></strong><small>CIRCLES</small></div><button className="sidebar-mobile-close" onClick={() => setSidebarOpen(false)}><X size={19}/></button></div>
      <div className="workspace-selector"><div className="workspace-visual"><Layers3 size={19}/></div><div className="workspace-text"><small>YOUR WORKSPACE</small><strong>{circle?.name || "My Circle"}</strong></div><ChevronDown size={16}/><select aria-label="Choose your circle" value={circleId} onChange={e => setCircleId(e.target.value)}>{data.circles.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
      <div className="nav-section-label">WORKSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">{nav.map(item => <button key={item.view} className={`nav-item ${view === item.view ? "nav-active" : ""}`} onClick={() => chooseView(item.view)}><item.icon size={19} strokeWidth={view === item.view ? 2.2 : 1.9}/><span>{item.label}</span>{item.view === "assistant" && <span className="nav-ai-badge">AI</span>}{item.view === "tasks" && <span className="nav-count">{pending}</span>}</button>)}</nav>
      <div className="nav-section-label sidebar-bottom-label">PREFERENCES</div>
      <nav className="side-nav"><button className={`nav-item ${view === "settings" ? "nav-active" : ""}`} onClick={() => chooseView("settings")}><Settings2 size={19}/><span>Settings</span></button></nav>
      <div className="sidebar-spacer"/>
      <div className="sidebar-user"><Avatar person={data.user} size="md"/><div><strong>{data.user.name}</strong><small>Demo workspace</small></div><button aria-label="Switch user" onClick={() => setProfileOpen(!profileOpen)}><MoreHorizontal size={21}/></button></div>
    </aside>

    <div className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="hamburger" aria-label="Open sidebar" onClick={() => setSidebarOpen(true)}><Menu size={21}/></button><span className="breadcrumb-brand">Workspace</span><ChevronRight size={15} className="muted-icon"/><span className="breadcrumb-current">{nav.find(x => x.view === view)?.label || "Settings"}</span></div><div className="topbar-right"><span className="live-indicator"><i/> All systems ready</span><div className="topbar-divider"/><button aria-label="Notifications" className="top-icon" onClick={() => setNotificationsOpen(!notificationsOpen)}><Bell size={19}/>{unread>0 && <span className="notification-dot"/>}</button><button className="profile-trigger" onClick={() => setProfileOpen(!profileOpen)}><Avatar person={data.user} size="sm"/><ChevronDown size={15}/></button></div></header>

      {notificationsOpen && <div className="floating-panel notification-panel"><div className="pop-head"><strong>Notifications</strong><span>{unread} unread</span><button onClick={() => setNotificationsOpen(false)}><X size={16}/></button></div>{data.notifications.length ? data.notifications.slice(0,8).map(n => <button key={n.id} className={`notification-row ${!n.read_at ? "new-notification" : ""}`} onClick={() => markNotification(n)}><span className="notice-icon"><Bell size={17}/></span><span><strong>{n.title}</strong><small>{n.body}</small></span>{!n.read_at && <i/>}</button>) : <p className="empty-text">Nothing new. You&apos;re all caught up!</p>}</div>}
      {profileOpen && <div className="floating-panel profile-panel"><div className="pop-head"><strong>Switch demo persona</strong><button onClick={() => setProfileOpen(false)}><X size={16}/></button></div>{data.members.map(p => <button className="profile-option" key={p.id} onClick={() => login(p.id)}><Avatar person={p} size="sm"/><span>{p.name}</span>{data.user.id === p.id && <Check size={16}/>}</button>)}<div className="profile-note">Demo identities only · Production needs OAuth</div></div>}

      <main className="page-content">
        {view === "overview" && <>
          {welcome}
          <div className="overview-grid"><section className="hero-card"><div className="hero-inner"><div className="hero-eyebrow"><Sparkles size={14}/> YOUR AI, YOUR ADVANTAGE</div><h2>Big plans.<br/><em>Beautifully done.</em></h2><p>Turn one idea into real action. Plan together, delegate smarter, and let the little things take care of themselves.</p><button className="hero-cta" onClick={() => chooseView("assistant")}>Ask LifePilot <ArrowUpRight size={17}/></button><div className="hero-decoration"><span className="hero-ring ring-one"/><span className="hero-ring ring-two"/><div className="hero-floating floater-one"><CalendarDays size={22}/></div><div className="hero-floating floater-two"><CheckCheck size={24}/></div><div className="hero-floating floater-three"><Star size={23} fill="currentColor"/></div><div className="hero-illustration"><Sparkles size={61}/></div></div></div></section>
          <section className="focus-card"><div className="focus-head"><span className="focus-icon"><Zap size={18}/></span><span>Your daily focus</span><MoreHorizontal size={20}/></div><div className="focus-meter" style={{"--percent":`${progress}%`} as React.CSSProperties}><div><strong>{progress}%</strong><small>complete</small></div></div><h3>You&apos;re making progress!</h3><p>{done} of {tasks.length} tasks done in this circle.</p><button onClick={() => chooseView("tasks")}>View all tasks <ArrowRight size={16}/></button></section></div>
          <div className="stat-grid"><StatCard icon={ListTodo} iconColor="indigo" title="Active tasks" value={pending} meta="Across your circle" trend="Let's get it done"/><StatCard icon={CheckCircle2} iconColor="mint" title="Completed" value={done} meta="Milestones reached" trend="Keep it going"/><StatCard icon={Users} iconColor="coral" title="Team members" value={team.length} meta="Making it happen" trend="Better together"/><StatCard icon={CalendarDays} iconColor="gold" title="Upcoming events" value={events.length} meta="On your calendar" trend="Stay in the loop"/></div>
          <div className="content-grid"><section className="surface-card task-overview"><SectionHeading title="Today&apos;s priorities" subtitle="The work that moves things forward" action={<button className="text-link" onClick={() => chooseView("tasks")}>View all <ArrowRight size={16}/></button>}/><div className="priority-list">{tasks.filter(t => t.status !== "done").slice(0,4).map(task => <TaskRow key={task.id} task={task} team={team} onStatus={() => changeStatus(task)}/>)}{!pending && <EmptyState icon={CheckCheck} title="You are all caught up" description="Give your AI assistant a new goal to plan."/>}</div><button className="subtle-action" onClick={() => setModal("task")}><Plus size={16}/> Add a task</button></section>
          <section className="surface-card upcoming-card"><SectionHeading title="Coming up" subtitle="Keep your people in sync" action={<button className="icon-button" onClick={() => chooseView("calendar")} aria-label="Open calendar"><ArrowUpRight size={19}/></button>}/><div className="event-list">{events.slice(0,3).map(e => <EventRow key={e.id} event={e}/>)}{!events.length && <EmptyState icon={CalendarDays} title="Calendar is clear" description="Schedule a new event with your assistant."/>}</div><div className="upcoming-footer"><div className="avatar-stack">{team.slice(0,4).map(member => <Avatar key={member.id} person={member} size="sm"/>)}</div><span>Better days, shared together</span></div></section></div>
          <div className="content-grid lower-grid"><section className="surface-card activity-card"><SectionHeading title="Recent activity" subtitle="A little timeline of everything happening" action={<button className="text-link" onClick={() => chooseView("activity")}>All activity <ArrowRight size={16}/></button>}/><ActivityList items={activity.slice(0,4)}/></section><section className="surface-card assistant-teaser"><div className="teaser-top"><span className="teaser-spark"><Sparkles size={22}/></span><span className="tiny-label">MADE FOR YOUR MOMENTS</span></div><h2>Less busywork.<br/><span>More living.</span></h2><p>"Assign Rahul the API task and remind him tomorrow" — one sentence is all it takes.</p><button onClick={() => chooseView("assistant")}>Let&apos;s make it happen <ArrowRight size={18}/></button><div className="teaser-shape"/></section></div>
        </>}

        {view === "assistant" && <><PageTop eyebrow="YOUR PERSONAL ACTION PARTNER" title="Meet your AI assistant" description="Describe what you need. Review every action before anything runs."/><div className="assistant-layout"><section className="assistant-primary"><div className="assistant-welcome"><div className="assistant-hero-icon"><WandSparkles size={26}/></div><div className="assistant-status"><span className="spark-mark">✦</span> LIFE IS BETTER WITH A LITTLE HELP</div><h2>What can we make<br/><em>happen today?</em></h2><p>Assign tasks, plan meetings, send updates, and set reminders — all through one conversation.</p></div><div className="suggestion-grid">{demoSuggestions.map((s,i) => <button key={s} onClick={() => setPrompt(s)}><IconPill color={["violet","coral","mint"][i]}>{[<ListTodo key="a" size={17}/>,<CalendarDays key="b" size={17}/>,<Mail key="c" size={17}/>][i]}</IconPill><span>{s}</span><ArrowUpRight size={16}/></button>)}</div><div className="prompt-box"><textarea aria-label="Describe an action for LifePilot" placeholder="Try: Assign Rahul the API task by Friday, and remind him tomorrow..." value={prompt} onChange={e => setPrompt(e.target.value)} onKeyDown={e => {if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();createPlan();}}} rows={3}/><div className="prompt-bottom"><span><ShieldCheck size={16}/> You&apos;re always in control</span><div className="prompt-actions"><VoiceInputButton onTranscript={text => setPrompt(previous => [previous.trim(), text].filter(Boolean).join(" "))}/><button className="prompt-submit" onClick={() => createPlan()} disabled={!prompt.trim()||busy}>{busy?<Loader2 size={18} className="spin"/>:<Send size={18}/>} Generate plan</button></div></div><p className="voice-privacy-hint">Speak in English or Hindi. Your browser handles speech recognition; review the text before generating a plan.</p></div><div className="assistant-disclaimer"><ShieldCheck size={15}/> Your assistant always asks for approval before executing AI-generated actions.</div></section><aside className="assistant-side"><div className="surface-card light-guide"><div className="guide-icon"><Compass size={21}/></div><h3>Here&apos;s how it works</h3><div className="guide-steps"><div><b>01</b><span><strong>Tell us your goal</strong><small>Just write it naturally.</small></span></div><div><b>02</b><span><strong>Review the plan</strong><small>See every proposed action.</small></span></div><div><b>03</b><span><strong>Make it happen</strong><small>Approve and track results.</small></span></div></div></div><div className="surface-card recent-plans"><h3>Recent plans</h3>{data.proposals.slice(0,4).map(p => <button key={p.id} onClick={() => setActiveProposal(p)}><span className={`plan-state plan-${p.status}`}><Check size={15}/></span><span><strong>{p.prompt}</strong><small>{p.status.replace("_"," ")} · {p.actions.length} actions</small></span><ChevronRight size={17}/></button>)}{!data.proposals.length && <p className="empty-muted">Your first action plan will appear here.</p>}</div></aside></div></>}

        {view === "tasks" && <><PageTop eyebrow="THE WORK THAT MATTERS" title="Tasks, without the chaos" description="Give everyone clarity. Celebrate every little win." action={<button className="primary-action" onClick={() => setModal("task")}><Plus size={18}/> New task</button>}/><div className="tasks-toolbar"><div className="task-filter-tabs">{(["all","todo","in_progress","done"] as const).map(v=><button key={v} className={filter===v?"selected":""} onClick={()=>setFilter(v)}>{({all:"All tasks",todo:"To do",in_progress:"In progress",done:"Completed"})[v]} <span>{v==="all"?tasks.length:tasks.filter(t=>t.status===v).length}</span></button>)}</div><label className="task-search"><Search size={17}/><input placeholder="Search tasks..." value={search} onChange={e=>setSearch(e.target.value)}/></label></div><div className="task-board">{(["todo","in_progress","done"] as const).map(status => <section className="kanban-col" key={status}><div className="kanban-heading"><span className={`kanban-dot dot-${status}`}/><h3>{({todo:"To do",in_progress:"In progress",done:"Completed"})[status]}</h3><span>{tasks.filter(t=>t.status===status).length}</span><MoreHorizontal size={18}/></div>{tasks.filter(t=>t.status===status&&(filter==="all"||filter===status)&&t.title.toLowerCase().includes(search.toLowerCase())).map(t=><KanbanTask key={t.id} task={t} team={team} onStatus={()=>changeStatus(t)}/>)}<button className="kanban-add" onClick={()=>setModal("task")}><Plus size={16}/> Add task</button></section>)}</div><p className="board-note"><ShieldCheck size={15}/> Task status changes are saved immediately. AI-generated assignments still require approval first.</p></>}

        {view === "circles" && <><PageTop eyebrow="PEOPLE MAKE IT POSSIBLE" title="Together is better" description="Shared spaces for the people you do life and work with." action={<button className="primary-action" onClick={()=>setModal("circle")}><Plus size={18}/> Create circle</button>}/><div className="circles-grid">{data.circles.map(c => <button key={c.id} className={`circle-card ${circleId===c.id?"circle-selected":""}`} onClick={()=>setCircleId(c.id)}><span className={`circle-big-icon circle-icon-${c.color}`}>{c.icon==="home"?<Home size={24}/>:<Layers3 size={24}/>}</span><span className="circle-card-title">{c.name}</span><span className="circle-card-desc">{c.description}</span><span className="circle-card-bottom"><span>{c.membership_role} · {data.tasks.filter(t=>t.circle_id===c.id).length} tasks</span><ArrowUpRight size={18}/></span></button>)}</div><section className="surface-card members-card"><SectionHeading title="People in your world" subtitle="The humans behind your best ideas" action={<button className="text-link" onClick={()=>setModal("invite")}><Plus size={16}/> Invite member</button>}/><div className="members-grid">{team.map(p=><div key={p.id} className="member-card"><Avatar person={p} size="lg"/><strong>{p.name}</strong><small>{p.email}</small><span className="member-chip">{p.id===data.user.id?"You":"Circle member"}</span></div>)}</div></section></>}

        {view === "calendar" && <><PageTop eyebrow="NEVER MISS A MOMENT" title="Your shared calendar" description="A clear view of everything you&apos;ve planned together." action={<button className="primary-action" onClick={()=>setModal("event")}><Plus size={18}/> New event</button>}/><div className="calendar-page-grid"><section className="surface-card calendar-main"><div className="calendar-header"><div><h3>{new Date().toLocaleDateString("en-US",{month:"long",year:"numeric"})}</h3><p>All your upcoming moments</p></div><span className="calendar-count">{events.length} events</span></div><div className="calendar-event-list">{events.map(e=><div key={e.id} className="calendar-event-card"><div className="event-date-badge"><strong>{new Date(e.starts_at).toLocaleDateString("en-US",{day:"2-digit"})}</strong><span>{new Date(e.starts_at).toLocaleDateString("en-US",{month:"short"})}</span></div><div><h3>{e.title}</h3><p><Clock3 size={14}/>{timeOf(e.starts_at)} – {timeOf(e.ends_at)} · {e.attendees.length} people</p></div><a className="icon-button" href={`${API}/api/events/${e.id}/ics?`} onClick={event=>{event.preventDefault();if(token)fetch(`${API}/api/events/${e.id}/ics`,{headers:{Authorization:`Bearer ${token}`}}).then(r=>{if(!r.ok)throw new Error("Export failed");return r.blob();}).then(blob=>{const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`lifepilot-${e.id.slice(0,8)}.ics`;a.click();URL.revokeObjectURL(url);}).catch(err=>setError(err.message));}} title="Download calendar file"><Download size={18}/></a></div>)}{!events.length&&<EmptyState icon={CalendarDays} title="No events yet" description="Create an event or ask your assistant to schedule one."/>}</div></section><section className="surface-card reminder-side"><div className="reminder-top"><IconPill color="gold"><Bell size={19}/></IconPill><h3>Your reminders</h3><button className="icon-button" onClick={()=>setModal("reminder")}><Plus size={18}/></button></div>{data.reminders.filter(r=>!r.completed).map(r=><div className="reminder-entry" key={r.id}><span className="reminder-bullet"/><div><strong>{r.title}</strong><small>{shortDate(r.due_at)} · {timeOf(r.due_at)}</small></div></div>)}{!data.reminders.some(r=>!r.completed)&&<p className="empty-muted">All clear. No reminders scheduled.</p>}</section></div></>}

        {view === "activity" && <><PageTop eyebrow="EVERY STEP COUNTS" title="Your activity timeline" description="A transparent record of what was planned, approved, and completed."/><section className="surface-card full-activity"><ActivityList items={activity}/>{!activity.length&&<EmptyState icon={ActivityIcon} title="No activity yet" description="Your shared actions will appear here."/>}</section></>}

        {view === "settings" && <><PageTop eyebrow="MADE YOUR WAY" title="Workspace settings" description="Manage your demo identity and integrations."/><section className="surface-card settings-main"><SectionHeading title="Connections & capabilities" subtitle="A clear picture of what's actually connected"/><div className="connections-grid">{Object.entries(data.connections).map(([name,value])=><div key={name} className="connection-row"><IconPill color={name==="ai"?"violet":name==="mcp"?"mint":"gold"}>{name==="ai"?<Sparkles size={18}/>:name==="mcp"?<Zap size={18}/>:name==="calendar"?<CalendarDays size={18}/>:<Mail size={18}/>}</IconPill><span><strong>{name.toUpperCase()}</strong><small>{value}</small></span><span className={`connection-tag ${value.includes("not connected")?"offline":""}`}>{value.includes("not connected")?"Not connected":"Available"}</span></div>)}</div><div className="settings-notice"><ShieldCheck size={20}/><span><strong>Demo authentication is enabled.</strong> Production needs real OAuth/OIDC and a protected public MCP endpoint. Unconfigured external services are never represented as successful sends.</span></div></section></>}
      </main>
    </div>

    {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={()=>setError(null)} aria-label="Dismiss error"><X size={17}/></button></div>}
    {toast && <div className="toast"><CheckCircle2 size={18}/>{toast}</div>}
    {activeProposal && <ProposalModal proposal={activeProposal} busy={busy} team={team} onClose={()=>setActiveProposal(null)} onDecide={decideProposal}/>}
    {modal && token && <CreateModal type={modal} circleId={circleId} currentUser={data.user} team={team} token={token} onClose={()=>setModal(null)} onCreated={async()=>{setModal(null);await reload(token);notice("Created successfully!");}} onError={setError}/>}
  </div>;
}

function PageTop({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-top"><div><div className="eyebrow"><span className="eyebrow-dot"/>{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}
function StatCard({ icon: Icon, iconColor, title, value, meta, trend }: { icon: LucideIcon; iconColor: string; title: string; value: number; meta: string; trend: string }) {
  return <div className="stat-card"><div className="stat-card-top"><IconPill color={iconColor}><Icon size={19}/></IconPill><ArrowUpRight size={17} className="stat-arrow"/></div><small>{title}</small><div className="stat-number">{String(value).padStart(2,"0")}</div><div className="stat-card-footer"><span>{meta}</span><span>{trend}</span></div></div>;
}
function TaskRow({ task, team, onStatus }: { task: Task; team: Person[]; onStatus: () => void }) {
  return <div className="task-list-row"><button aria-label={`Advance status for ${task.title}`} className={`task-check ${task.status==="done"?"checked":""}`} onClick={onStatus}>{task.status==="done"&&<Check size={14}/>}</button><div className="task-row-main"><strong>{task.title}</strong><div className="task-row-meta"><span className={`priority-text priority-${task.priority}`}><i/>{task.priority} priority</span><span>·</span><span>{shortDate(task.due_at)}</span></div></div><Avatar size="sm" person={team.find(p=>p.id===task.assignee_id)}/><button aria-label="Move task status" className="chevron-task" onClick={onStatus}><ChevronRight size={17}/></button></div>;
}
function KanbanTask({ task, team, onStatus }: { task: Task; team: Person[]; onStatus: () => void }) {
  return <div className="kanban-task"><div className="kanban-card-top"><span className={`priority-chip priority-${task.priority}`}>{task.priority}</span><button onClick={onStatus} title="Move to next status"><MoreHorizontal size={19}/></button></div><h4>{task.title}</h4><p>{task.description || "Part of your shared action plan"}</p><div className="kanban-card-footer"><span><CalendarDays size={14}/>{shortDate(task.due_at)}</span><Avatar person={team.find(p=>p.id===task.assignee_id)} size="sm"/></div><button className="kanban-status-action" onClick={onStatus}>{task.status==="done"?"Reopen task":task.status==="todo"?"Start working":"Mark complete"} <ArrowRight size={14}/></button></div>;
}
function EventRow({ event }: { event: CalendarEvent }) {
  const d=new Date(event.starts_at);
  return <div className="event-row"><div className="event-month-day"><strong>{d.getDate()}</strong><span>{d.toLocaleDateString("en-US",{month:"short"})}</span></div><div><strong>{event.title}</strong><p><Clock3 size={14}/>{timeOf(event.starts_at)} · {event.attendees.length} attendees</p></div><ChevronRight size={18}/></div>;
}
function ActivityList({ items }: { items: Activity[] }) {
  return <div className="activity-list">{items.map((a,i)=><div className="activity-item" key={a.id}><div className="activity-rail"><Avatar person={{id:"",name:a.actor_name,avatar:a.actor_avatar,color:a.actor_color}} size="sm"/>{i!==items.length-1&&<span/>}</div><div className="activity-body"><div><strong>{a.actor_name}</strong> <span>{a.message}</span></div><small>{new Date(a.created_at).toLocaleDateString("en-US",{month:"short",day:"numeric"})} · {timeOf(a.created_at)}</small></div><span className={`activity-type activity-${a.kind}`}>{a.kind}</span></div>)}</div>;
}
function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return <div className="empty-state"><Icon size={30}/><strong>{title}</strong><p>{description}</p></div>;
}
function ProposalModal({ proposal, busy, team, onClose, onDecide }: { proposal: Proposal; busy: boolean; team: Person[]; onClose: () => void; onDecide: (approved:boolean)=>void }) {
  const pending=proposal.status==="pending";
  const icons: Record<string, LucideIcon>={assign_task:ListTodo,create_event:CalendarDays,create_reminder:Bell,send_message:Mail};
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="approval-modal" role="dialog" aria-modal="true" aria-label="Review AI action plan"><div className="modal-heading"><div className="approval-title-icon"><Sparkles size={23}/></div><div><span className="tiny-label">LIFEPILOT AI · ACTION PREVIEW</span><h2>{pending?"One last look, then magic.":"Your action results"}</h2></div><ReadAloudButton text={`${proposal.summary}. ${proposal.actions.map(action => action.label).join(". ")}. ${pending ? "Please approve or reject the proposed actions. Nothing has been executed." : "Current status: " + proposal.status}.`}/><button className="close-modal" onClick={onClose} aria-label="Close"><X size={21}/></button></div><div className="proposal-summary"><strong>Your request</strong><p>{proposal.prompt}</p></div><p className="approval-intro">{proposal.summary}</p><div className="proposed-actions">{proposal.actions.map((a,i)=>{const Icon=icons[a.type]||Zap;const recipient=team.find(t=>t.id===(a.args.assignee_id||a.args.user_id));const outcome=proposal.outcomes?.[i];return <div className="proposal-action" key={i}><IconPill color={["violet","coral","gold","mint"][i%4]}><Icon size={20}/></IconPill><div><strong>{a.label}</strong><small>{a.type.replaceAll("_"," ")}{recipient?` · ${recipient.name}`:""}</small><span className="action-description">{String(a.args.title||a.args.body||"").slice(0,150)}</span>{outcome&&!outcome.ok&&<span className="action-error">{outcome.error}</span>}</div><span className={`proposal-action-state ${outcome ? outcome.ok?"success":"failure":"waiting"}`}>{outcome?outcome.ok?<Check size={17}/>:<X size={17}/>:String(i+1).padStart(2,"0")}</span></div>;})}</div><div className="approval-safety"><ShieldCheck size={18}/><p>{pending?"Nothing has been executed yet. Only approved actions will run.":`Final status: ${proposal.status}. Actual tool results shown above.`}</p></div><div className="approval-footer">{pending?<><button className="reject-button" onClick={()=>onDecide(false)} disabled={busy}>{busy?<Loader2 className="spin" size={17}/>:<X size={17}/>} Reject plan</button><button className="approve-button" onClick={()=>onDecide(true)} disabled={busy}>{busy?<Loader2 className="spin" size={17}/>:<Check size={18}/>} Approve {proposal.actions.length} actions</button></>:<button className="approve-button" onClick={onClose}>Done <Check size={18}/></button>}</div><div className="modal-footnote">{proposal.mode==="demo-rule-based"?"DEMO PLANNER — deterministic actions; set NVIDIA_API_KEY for model-generated plans.":"NVIDIA NEMOTRON — model-generated proposal, validated before execution."}</div></div></div>;
}
function CreateModal({ type, circleId, currentUser, team, token, onClose, onCreated, onError }: { type: Exclude<ModalType,null>; circleId: string; currentUser: Person; team: Person[]; token: string; onClose:()=>void; onCreated:()=>void; onError:(value:string)=>void }) {
  const [title,setTitle]=useState("");
  const [recipient,setRecipient]=useState(type==="invite" ? (team.find(p=>p.id!==currentUser.id)?.id || currentUser.id) : currentUser.id);
  const [date,setDate]=useState("");
  const [time,setTime]=useState("15:00");
  const [priority,setPriority]=useState("medium");
  const [submitting,setSubmitting]=useState(false);
  const captions={task:"Create a shared task",event:"Schedule a circle event",reminder:"Set a helpful reminder",message:"Send an in-app message",circle:"Create a new circle",invite:"Invite a team member"};
  const endpoints={task:"/api/tasks",event:"/api/events",reminder:"/api/reminders",message:"/api/messages",circle:"/api/circles",invite:`/api/circles/${circleId}/members`};
  async function submit(){
    setSubmitting(true);
    try {
      let payload:Record<string,unknown>={circle_id:circleId};
      const iso=date?new Date(`${date}T${time}:00`).toISOString():new Date(Date.now()+86400000).toISOString();
      if(type==="task")payload={...payload,title,assignee_id:recipient,priority,due_at:date||null};
      if(type==="event")payload={...payload,title,starts_at:iso,ends_at:new Date(new Date(iso).getTime()+3600000).toISOString(),attendees:[currentUser.id,recipient]};
      if(type==="reminder")payload={...payload,title,user_id:recipient,due_at:iso};
      if(type==="message")payload={...payload,user_id:recipient,body:title};
      if(type==="circle")payload={name:title,description:"A place to get things done together",icon:"layers",member_ids:[]};
      if(type==="invite")payload={user_id:recipient};
      await request(endpoints[type],token,{method:"POST",body:JSON.stringify(payload)});
      await onCreated();
    }catch(e){onError((e as Error).message);}finally{setSubmitting(false);}
  }
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="simple-modal" role="dialog" aria-modal="true" aria-label={captions[type]}><div className="modal-heading"><div className="approval-title-icon"><Plus size={22}/></div><div><span className="tiny-label">MANUAL ACTION</span><h2>{captions[type]}</h2></div><button className="close-modal" onClick={onClose}><X size={21}/></button></div>{type!=="invite"&&<label className="field-label">{type==="message"?"Your message":type==="event"?"Event title":type==="reminder"?"Reminder":type==="circle"?"Circle name":"Task name"}<textarea rows={type==="message"?4:2} placeholder={type==="message"?"A thoughtful update...":"What needs to get done?"} value={title} onChange={e=>setTitle(e.target.value)}/></label>}{type!=="circle"&&<label className="field-label">{type==="message"?"Send to":type==="event"?"Invite":type==="reminder"?"Remind":type==="invite"?"Invite user":"Assign to"}<select value={recipient} onChange={e=>setRecipient(e.target.value)}>{team.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}{!["message","circle","invite"].includes(type)&&<div className="field-pair"><label className="field-label">{type==="task"?"Due date":"Date"}<input type="date" value={date} onChange={e=>setDate(e.target.value)}/></label>{type!=="task"&&<label className="field-label">Time<input type="time" value={time} onChange={e=>setTime(e.target.value)}/></label>}</div>}{type==="task"&&<label className="field-label">Priority<select value={priority} onChange={e=>setPriority(e.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>}<div className="approval-footer"><button className="reject-button" onClick={onClose}>Cancel</button><button className="approve-button" disabled={submitting||(type!=="invite"&&title.trim().length<2)} onClick={submit}>{submitting?<Loader2 size={17} className="spin"/>:<Check size={17}/>} {type==="invite"?"Send invite":`Create ${type}`}</button></div><p className="modal-footnote">This is a direct manual action. AI-generated actions always go through approval.</p></div></div>;
}
