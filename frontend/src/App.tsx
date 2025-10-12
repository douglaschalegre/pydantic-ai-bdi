import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type {
  AgentConfigInput,
  AgentState,
  ChatMessage,
  AgentEvent,
} from "../types";
import { mockCreateAgent, mockSubscribe, mockStopAgent } from "./mockBackend";
import { apiMode, realApi } from "./api";

interface LocalState {
  currentAgentId?: string;
  agents: Record<string, AgentState>; // latest snapshot per agent
  messagesByAgent: Record<string, ChatMessage[]>; // persistent chat logs per agent
  creating: boolean;
  brief: string;
  error?: string;
  agentList: {
    agent_id: string;
    status: string;
    cycle_count: number;
    created_at: string;
    brief: string;
  }[];
  loadingList: boolean;
}

export function App() {
  const [state, setState] = useState<LocalState>({
    currentAgentId: undefined,
    agents: {},
    messagesByAgent: {},
    creating: false,
    brief: "",
    agentList: [],
    loadingList: false,
  });
  const subscriptionsRef = useRef<Record<string, () => void>>({});

  // Cleanup all subscriptions on unmount
  useEffect(
    () => () => {
      Object.values(subscriptionsRef.current).forEach((u) => u());
    },
    []
  );

  const refreshList = useCallback(async () => {
    if (apiMode !== "real") return; // skip for mock
    setState((s) => ({ ...s, loadingList: true }));
    try {
      const list = await realApi.listAgentsReal();
      setState((s) => ({ ...s, agentList: list, loadingList: false }));
      // auto-subscribe to running agents so their chats continue updating in background
      list
        .filter((a) => a.status === "running")
        .forEach((a) => ensureSubscription(a.agent_id));
    } catch {
      setState((s) => ({ ...s, loadingList: false }));
    }
  }, []);

  useEffect(() => {
    if (!state.currentAgentId) {
      void refreshList();
    }
  }, [state.currentAgentId, refreshList]);

  const ensureSubscription = (agentId: string) => {
    if (subscriptionsRef.current[agentId]) return; // already subscribed
    if (apiMode === "real") {
      subscriptionsRef.current[agentId] = realApi.openEventStream(
        agentId,
        (evt: AgentEvent) => {
          setState((s) => handleEvent(s, agentId, evt));
        }
      );
    } else {
      subscriptionsRef.current[agentId] = mockSubscribe(
        agentId,
        (evt: AgentEvent) => {
          setState((s) => handleEvent(s, agentId, evt));
        }
      );
    }
  };

  const openExisting = async (agentId: string) => {
    try {
      const agentState = await realApi.loadAgentState(agentId);
      setState((s) => ({
        ...s,
        currentAgentId: agentId,
        agents: { ...s.agents, [agentId]: agentState },
        messagesByAgent: {
          ...s.messagesByAgent,
          [agentId]: s.messagesByAgent[agentId] || [],
        },
      }));
      ensureSubscription(agentId);
    } catch (e) {
      setState((s) => ({
        ...s,
        error: e instanceof Error ? e.message : String(e),
      }));
    }
  };

  const onCreate = async () => {
    if (!state.brief.trim()) return;
    setState((s) => ({ ...s, creating: true, error: undefined }));
    try {
      let res: { state: AgentState; initialMessages?: ChatMessage[] };
      if (apiMode === "real") {
        res = await realApi.createAgentReal({ brief: state.brief });
      } else {
        res = await mockCreateAgent({ brief: state.brief } as AgentConfigInput);
      }
      setState((s) => {
        const id = res.state.agentId;
        return {
          ...s,
          currentAgentId: id,
          agents: { ...s.agents, [id]: res.state },
          messagesByAgent: {
            ...s.messagesByAgent,
            [id]: res.initialMessages ?? [],
          },
          creating: false,
        };
      });
      ensureSubscription(res.state.agentId);
    } catch (e) {
      setState((s) => ({
        ...s,
        creating: false,
        error:
          (e instanceof Error ? e.message : String(e)) ||
          "Failed to create agent",
      }));
    }
  };

  // Auto-scroll refs (must be declared unconditionally before any return)
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const autoScrollRef = useRef(true);

  // Derive active agent & messages (memoized to avoid effect churn)
  const activeAgent = useMemo(
    () =>
      state.currentAgentId ? state.agents[state.currentAgentId] : undefined,
    [state.currentAgentId, state.agents]
  );
  const activeMessages = useMemo(
    () =>
      state.currentAgentId
        ? state.messagesByAgent[state.currentAgentId] || []
        : [],
    [state.currentAgentId, state.messagesByAgent]
  );

  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const handleScroll = () => {
      const distanceFromBottom =
        el.scrollHeight - el.scrollTop - el.clientHeight;
      autoScrollRef.current = distanceFromBottom < 40; // re-enable when near bottom
    };
    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, [state.currentAgentId]);

  useEffect(() => {
    if (!autoScrollRef.current) return;
    const el = messagesContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [activeMessages, state.currentAgentId]);

  const onStop = async () => {
    const current = state.currentAgentId && state.agents[state.currentAgentId];
    if (!current) return;
    if (apiMode === "real") {
      await realApi.stopAgentReal(current.agentId);
    } else {
      mockStopAgent(current.agentId);
    }
  };

  if (!state.currentAgentId) {
    return (
      <div className="app-container">
        <h1>
          BDI Agent Prototype ({apiMode === "real" ? "Real API" : "Mock"})
        </h1>
        <p>
          Enter a brief describing what you want the agent to pursue. It will
          extract desires & intentions.
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
          {apiMode === "real" && (
            <button
              style={{ marginLeft: ".5rem" }}
              onClick={() => void refreshList()}
              disabled={state.loadingList}
            >
              Refresh
            </button>
          )}
        </div>
        {state.creating && <p>Creating agent...</p>}
        {state.error && <p className="error">{state.error}</p>}
        {apiMode === "real" && (
          <section style={{ marginTop: "1.5rem" }}>
            <h2 style={{ margin: "0 0 .5rem" }}>Existing Agents</h2>
            {state.loadingList && <p>Loading…</p>}
            {!state.loadingList && state.agentList.length === 0 && (
              <p style={{ fontSize: ".85rem", opacity: 0.7 }}>No agents yet.</p>
            )}
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: ".5rem",
              }}
            >
              {state.agentList.map((a) => (
                <li
                  key={a.agent_id}
                  style={{
                    background: "#1b1f27",
                    border: "1px solid #2d3341",
                    borderRadius: 6,
                    padding: ".6rem .75rem",
                    display: "flex",
                    flexDirection: "column",
                    gap: ".35rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "1rem",
                    }}
                  >
                    <strong style={{ fontSize: ".85rem" }}>
                      #{a.agent_id}
                    </strong>
                    <span
                      className={`status-pill status-${a.status}`}
                      style={{ fontSize: ".55rem" }}
                    >
                      {a.status}
                    </span>
                  </div>
                  <div style={{ fontSize: ".7rem", lineHeight: 1.3 }}>
                    {shorten(a.brief, 120)}
                  </div>
                  <div style={{ display: "flex", gap: ".5rem" }}>
                    <button onClick={() => void openExisting(a.agent_id)}>
                      Open
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    );
  }

  if (!activeAgent) return null;

  return (
    <div className="app-container">
      <header className="agent-header">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            flexWrap: "wrap",
          }}
        >
          <button
            onClick={() =>
              setState((s) => ({ ...s, currentAgentId: undefined }))
            }
            style={{ background: "#334155" }}
          >
            ← Back
          </button>
          <h1 style={{ margin: 0 }}>Agent #{activeAgent.agentId}</h1>
          <button
            onClick={onStop}
            disabled={activeAgent.status !== "running"}
            style={{ background: "#b91c1c" }}
          >
            Stop
          </button>
        </div>
        <div className="status-line">
          <span className={`status-pill status-${activeAgent.status}`}>
            {activeAgent.status}
          </span>
          <span>Cycles: {activeAgent.cycleCount}</span>
          {activeAgent.activeIntentionId && (
            <span>
              Active intention:{" "}
              {shorten(
                activeAgent.intentions.find(
                  (i) => i.id === activeAgent.activeIntentionId
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
            <div
              className={`messages ${
                autoScrollRef.current ? "autoscroll" : ""
              }`}
              ref={messagesContainerRef}
            >
              {activeMessages.map((m) => (
                <div key={m.id} className={`msg sender-${m.sender}`}>
                  <span className="sender">{m.sender}</span>
                  <span className="content">{m.content}</span>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <ChatInput
              onSend={(content) =>
                setState((s) => {
                  if (!s.currentAgentId) return s;
                  const id = s.currentAgentId;
                  const msgs = s.messagesByAgent[id] || [];
                  return {
                    ...s,
                    messagesByAgent: {
                      ...s.messagesByAgent,
                      [id]: [...msgs, createUserMessage(content)],
                    },
                  };
                })
              }
            />
          </section>
        </div>
        <div className="right-col">
          <section className="panel desires">
            <h2>Desires</h2>
            <ul>
              {activeAgent.desires.map((d) => (
                <li key={d.id} className={`desire desire-${d.status}`}>
                  {d.text} <em>({d.status.replace("_", " ")})</em>
                </li>
              ))}
            </ul>
          </section>
          <section className="panel intentions">
            <h2>Intentions</h2>
            <ul>
              {activeAgent.intentions.map((it) => (
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

function handleEvent(
  prev: LocalState,
  agentId: string,
  evt: AgentEvent
): LocalState {
  const agent = prev.agents[agentId];
  if (!agent) return prev; // unknown agent (might race with load)
  let updatedAgent = agent;
  switch (evt.type) {
    case "cycle.started":
      updatedAgent = { ...agent, cycleCount: evt.cycle };
      break;
    case "cycle.completed":
      updatedAgent = {
        ...agent,
        cycleCount: evt.cycle,
        lastProgressAt: evt.at,
      };
      break;
    case "desire.updated": {
      const desires = agent.desires.map((d) =>
        d.id === evt.desire.id ? evt.desire : d
      );
      updatedAgent = { ...agent, desires };
      break;
    }
    case "intention.updated": {
      const intentions = agent.intentions.map((i) =>
        i.id === evt.intention.id ? evt.intention : i
      );
      updatedAgent = {
        ...agent,
        intentions,
        activeIntentionId: evt.intention.active
          ? evt.intention.id
          : agent.activeIntentionId,
      };
      break;
    }
    case "agent.status":
      updatedAgent = { ...agent, ...evt.state };
      break;
    case "chat.message": {
      const msgs = prev.messagesByAgent[agentId] || [];
      return {
        ...prev,
        agents: { ...prev.agents, [agentId]: updatedAgent },
        messagesByAgent: {
          ...prev.messagesByAgent,
          [agentId]: [...msgs, evt.message],
        },
      };
    }
    case "error": {
      const msgs = prev.messagesByAgent[agentId] || [];
      return {
        ...prev,
        messagesByAgent: {
          ...prev.messagesByAgent,
          [agentId]: [
            ...msgs,
            {
              id: crypto.randomUUID(),
              at: evt.at,
              sender: "error",
              content: evt.error,
            },
          ],
        },
      };
    }
    default:
      return prev;
  }
  return { ...prev, agents: { ...prev.agents, [agentId]: updatedAgent } };
}

function shorten(text: string, max = 60) {
  return text.length <= max ? text : text.slice(0, max - 1) + "…";
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
