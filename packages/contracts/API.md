# Frontend ↔ FastAPI contract

Backend explorer: `GET http://127.0.0.1:8000/docs`.

Demo auth: `POST /api/auth/demo` `{"user_id":"alex"}` → signed token. All other API calls require `Authorization: Bearer <token>`.

| Method | Endpoint | Result |
|---|---|---|
| GET | `/api/bootstrap` | user, circles, members, tasks, events, reminders, proposals, activity, connections |
| POST | `/api/assistant/plan` | validated proposal, actions, generation mode |
| POST | `/api/proposals/{id}/approve` | actual MCP execution, per-action outcomes |
| POST | `/api/proposals/{id}/reject` | reject without side effects |
| POST | `/api/circles` | Create a new private circle and invite existing demo users |
| POST | `/api/circles/{id}/members` | Circle owner adds a registered member |
| POST | `/api/tasks` | manually create task, authorized by caller |
| PATCH | `/api/tasks/{id}` | change task status |
| POST | `/api/events` | add in-app calendar event |
| GET | `/api/events/{id}/ics` | calendar ICS download |
| POST | `/api/reminders` | schedule reminder |
| POST | `/api/messages` | persisted in-app message + optional SMTP/Slack |
| POST | `/api/reminders/check` | manually trigger due reminder processing for testing |
| POST | `/api/notifications/{id}/read` | mark owned notification read |

**Approval sequence:** `plan` writes only a *proposal*; approval endpoint is a separate server-enforced transition. `status` is one of `pending`, `rejected`, `executing`, `executed`, `partial`, `failed`. Partial failures return per-action results without false success claims.
