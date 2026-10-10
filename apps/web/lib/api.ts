export type Person = { id: string; name: string; email?: string; avatar: string; color: string };
export type Circle = { id: string; name: string; description: string; icon: string; color: string; membership_role: string };
export type Task = { id: string; circle_id: string; title: string; description?: string; assignee_id: string; assignee_name: string; assignee_avatar: string; assignee_color: string; status: "todo" | "in_progress" | "done"; priority: "low" | "medium" | "high"; due_at?: string | null; created_at: string };
export type CalendarEvent = { id: string; circle_id: string; title: string; starts_at: string; ends_at: string; location: string; attendees: string[] };
export type Reminder = { id: string; circle_id: string; user_id: string; title: string; due_at: string; completed: number };
export type Notification = { id: string; title: string; body: string; read_at: string | null; created_at: string };
export type Activity = { id: string; actor_name: string; actor_avatar: string; actor_color: string; kind: string; message: string; circle_id: string; created_at: string };
export type ActionType = "assign_task" | "create_event" | "create_reminder" | "send_message";
export type ProposedAction = { type: ActionType; label: string; args: Record<string, unknown> };
export type Outcome = { action: string; label: string; ok: boolean; error?: string; result?: Record<string, unknown> };
export type Proposal = { id: string; prompt: string; circle_id: string; summary: string; actions: ProposedAction[]; outcomes: Outcome[]; status: string; mode: string; created_at?: string };
export type Bootstrap = { user: Person; demo: boolean; circles: Circle[]; members: Person[]; tasks: Task[]; events: CalendarEvent[]; reminders: Reminder[]; notifications: Notification[]; activity: Activity[]; proposals: Proposal[]; connections: Record<string, string> };

// Default to same-origin proxy; optional override for direct browser API access.
export const API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

export async function request<T>(path: string, token: string | null, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json(); detail = typeof body.detail === "string" ? body.detail : detail; } catch { /* ignore invalid JSON */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function shortDate(iso?: string | null) {
  if (!iso) return "No due date";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
export function timeOf(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}
