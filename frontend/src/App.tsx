import { useState, useEffect, useRef } from "react";
import type {
  AgentConfigInput,
  AgentState,
  ChatMessage,
  AgentEvent,
} from "../types";
import { mockCreateAgent, mockSubscribe } from "./mockBackend";

interface LocalState {
  agent?: AgentState;
  messages: ChatMessage[];
  creating: boolean;
  brief: string;
  error?: string;
}

export function App() {
  const [state, setState] = useState<LocalState>({
    messages: [],
    creating: false,
    brief: "",
  });
  const eventSubRef = useRef<() => void>();

  useEffect(
    () => () => {
      eventSubRef.current?.();
    },
    []
  );

  const onCreate = async () => {
    if (!state.brief.trim()) return;
    setState((s) => ({ ...s, creating: true, error: undefined }));
    try {
      const res = await mockCreateAgent({
        brief: state.brief,
      } as AgentConfigInput);
      setState((s) => ({
        ...s,
        agent: res.state,
        messages: res.initialMessages ?? [],
        creating: false,
      }));
      // subscribe to events
      eventSubRef.current = mockSubscribe(
        res.state.agentId,
        (evt: AgentEvent) => {
          setState((s) => handleEvent(s, evt));
        }
      );
    } catch (e: any) {
      setState((s) => ({
        ...s,
        creating: false,
        error: e?.message || "Failed to create agent",
      }));
    }
  };

  if (!state.agent) {
    return (
      <div className="app-container">
        <h1>BDI Agent Prototype</h1>
        <p>
          Enter a brief describing what you want the agent to pursue. It will
          extract desires & intentions (mocked).
        </p>
        <textarea
          value={state.brief}
          onChange={(e) => setState((s) => ({ ...s, brief: e.target.value }))}
          placeholder="Example: Analyze recent repository commits and prepare a concise summary presentation."
          rows={8}
        />
        <div className="actions">
          <button
            onClick={onCreate}
            disabled={state.creating || !state.brief.trim()}
          >
            Create & Start
          </button>
        </div>
        {state.creating && <p>Creating agent...</p>}
        {state.error && <p className="error">{state.error}</p>}
      </div>
    );
  }

  return (
    <div className="app-container">
      <header className="agent-header">
        <h1>Agent #{state.agent.agentId}</h1>
        <div className="status-line">
          <span className={`status-pill status-${state.agent.status}`}>
            {state.agent.status}
          </span>
          <span>Cycles: {state.agent.cycleCount}</span>
          {state.agent.activeIntentionId && (
            <span>
              Active intention:{" "}
              {shorten(
                state.agent.intentions.find(
                  (i) => i.id === state.agent!.activeIntentionId
                )?.text || ""
              )}
            </span>
          )}
        </div>
      </header>
      <main className="layout">
        <div className="left-col">
          <section className="panel chat">
            <h2>Chat</h2>
            <div className="messages">
              {state.messages.map((m) => (
                <div key={m.id} className={`msg sender-${m.sender}`}>
                  <span className="sender">{m.sender}</span>
                  <span className="content">{m.content}</span>
                </div>
              ))}
            </div>
            <ChatInput
              onSend={(content) =>
                setState((s) => ({
                  ...s,
                  messages: [...s.messages, createUserMessage(content)],
                }))
              }
            />
          </section>
        </div>
        <div className="right-col">
          <section className="panel desires">
            <h2>Desires</h2>
            <ul>
              {state.agent.desires.map((d) => (
                <li key={d.id} className={`desire desire-${d.status}`}>
                  {d.text} <em>({d.status.replace("_", " ")})</em>
                </li>
              ))}
            </ul>
          </section>
          <section className="panel intentions">
            <h2>Intentions</h2>
            <ul>
              {state.agent.intentions.map((it) => (
                <li key={it.id} className={it.active ? "active" : ""}>
                  {it.text}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </main>
    </div>
  );
}

function createUserMessage(content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    at: new Date().toISOString(),
    sender: "user",
    content,
  };
}

function handleEvent(prev: LocalState, evt: AgentEvent): LocalState {
  if (!prev.agent) return prev;
  switch (evt.type) {
    case "cycle.started":
      return { ...prev, agent: { ...prev.agent, cycleCount: evt.cycle } };
    case "cycle.completed":
      return {
        ...prev,
        agent: { ...prev.agent, cycleCount: evt.cycle, lastProgressAt: evt.at },
      };
    case "desire.updated": {
      const desires = prev.agent.desires.map((d) =>
        d.id === evt.desire.id ? evt.desire : d
      );
      return { ...prev, agent: { ...prev.agent, desires } };
    }
    case "intention.updated": {
      const intentions = prev.agent.intentions.map((i) =>
        i.id === evt.intention.id ? evt.intention : i
      );
      return {
        ...prev,
        agent: {
          ...prev.agent,
          intentions,
          activeIntentionId: evt.intention.active
            ? evt.intention.id
            : prev.agent.activeIntentionId,
        },
      };
    }
    case "chat.message":
      return { ...prev, messages: [...prev.messages, evt.message] };
    case "agent.status":
      return { ...prev, agent: { ...prev.agent, ...evt.state } };
    case "error":
      return {
        ...prev,
        messages: [
          ...prev.messages,
          {
            id: crypto.randomUUID(),
            at: evt.at,
            sender: "error",
            content: evt.error,
          },
        ],
      };
    default:
      return prev;
  }
}

function shorten(text: string, max = 60) {
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + "…";
}

function ChatInput({ onSend }: { onSend: (content: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <form
      className="chat-input"
      onSubmit={(e) => {
        e.preventDefault();
        if (!value.trim()) return;
        onSend(value.trim());
        setValue("");
      }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Type a command or message…"
        aria-label="Chat input"
      />
      <button type="submit">Send</button>
    </form>
  );
}
