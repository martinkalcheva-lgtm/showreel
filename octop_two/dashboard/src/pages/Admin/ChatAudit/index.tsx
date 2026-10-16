import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Avatar, Drawer, Empty, List, Select, Spin, Tag, Typography } from "antd";
import { MessageSquareText, User as UserIcon } from "lucide-react";
import { message } from "@/utils/antdMessage";
import {
  octopThreadsApi,
  type OctopThread,
  type OctopThreadHistory,
} from "../../../api/modules/octopThreads";
import { request } from "../../../api/request";
import { apiErrorMessage } from "../../../utils/apiError";
import { useIsMobile } from "../../../hooks/useIsMobile";
import styles from "./index.module.less";

interface AuditUser {
  id: number;
  username: string;
  role?: string;
}

interface AuditAgent {
  agent_id: string;
  name?: string | null;
  user_id: number | null;
}

interface AuditThread {
  agentId: string;
  agentName: string;
  thread: OctopThread;
}

function contentText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const row = item as { type?: unknown; text?: unknown };
          if (row.type === "text" && typeof row.text === "string") {
            return row.text;
          }
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (content && typeof content === "object") {
    const row = content as { text?: unknown };
    if (typeof row.text === "string") return row.text;
  }
  return "";
}

function formatTime(seconds: number | undefined): string {
  if (!seconds) return "";
  try {
    return new Date(seconds * 1000).toLocaleString();
  } catch {
    return "";
  }
}

export default function ChatAuditPage() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();
  const [users, setUsers] = useState<AuditUser[]>([]);
  const [agents, setAgents] = useState<AuditAgent[]>([]);
  const [loadingBase, setLoadingBase] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const [threads, setThreads] = useState<AuditThread[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(false);

  const [drawerThread, setDrawerThread] = useState<AuditThread | null>(null);
  const [history, setHistory] = useState<OctopThreadHistory | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [userRows, agentRows] = await Promise.all([
          request<AuditUser[]>("/users"),
          request<AuditAgent[]>("/agents?scope=all"),
        ]);
        if (cancelled) return;
        setUsers(userRows);
        setAgents(agentRows);
      } catch (error) {
        if (!cancelled) {
          void message.error(
            apiErrorMessage(error, t("chatAudit.loadFailed"), t),
          );
        }
      } finally {
        if (!cancelled) setLoadingBase(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const agentsOfUser = useCallback(
    (uid: number) => agents.filter((agent) => agent.user_id === uid),
    [agents],
  );

  useEffect(() => {
    if (selectedUserId == null) {
      setThreads([]);
      return;
    }
    const owned = agentsOfUser(selectedUserId);
    if (owned.length === 0) {
      setThreads([]);
      return;
    }
    let cancelled = false;
    setLoadingThreads(true);
    (async () => {
      const collected: AuditThread[] = [];
      for (const agent of owned) {
        try {
          const rows = await octopThreadsApi.list(
            agent.agent_id,
            100,
            selectedUserId,
          );
          for (const thread of rows) {
            collected.push({
              agentId: agent.agent_id,
              agentName: agent.name || agent.agent_id,
              thread,
            });
          }
        } catch (error) {
          if (!cancelled) {
            void message.error(
            apiErrorMessage(error, t("chatAudit.loadFailed"), t),
          );
          }
        }
      }
      collected.sort(
        (a, b) => (b.thread.last_active || 0) - (a.thread.last_active || 0),
      );
      if (!cancelled) {
        setThreads(collected);
        setLoadingThreads(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedUserId, agentsOfUser]);

  const openThread = async (item: AuditThread) => {
    setDrawerThread(item);
    setHistory(null);
    setLoadingHistory(true);
    try {
      const rows = await octopThreadsApi.history(
        item.agentId,
        item.thread.thread_id,
        { limit: 50 },
        selectedUserId ?? undefined,
      );
      setHistory(rows);
    } catch (error) {
      void message.error(apiErrorMessage(error, t("chatAudit.loadFailed"), t));
    } finally {
      setLoadingHistory(false);
    }
  };

  const selectedUser = users.find((user) => user.id === selectedUserId);
  const ownedAgentCount =
    selectedUserId != null ? agentsOfUser(selectedUserId).length : 0;

  const messages = (history?.messages ?? []).filter((item) => {
    const role = String(item.role || "").toLowerCase();
    return role === "user" || role === "assistant" || role === "human" || role === "ai";
  });

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Typography.Title level={4} className={styles.title}>
          {t("chatAudit.title")}
        </Typography.Title>
        <Typography.Text type="secondary">
          {t("chatAudit.subtitle")}
        </Typography.Text>
      </div>

      <div className={styles.selectorRow}>
        <span className={styles.selectorLabel}>
          {t("chatAudit.selectUser")}
        </span>
        <Select
          className={styles.selector}
          placeholder={t("chatAudit.selectUserPlaceholder")}
          value={selectedUserId ?? undefined}
          loading={loadingBase}
          showSearch
          optionFilterProp="label"
          onChange={(value) => setSelectedUserId(value ?? null)}
          options={users.map((user) => ({
            value: user.id,
            label: `${user.username}${user.role === "admin" ? " (admin)" : ""}`,
          }))}
          allowClear
        />
      </div>

      {selectedUserId == null ? (
        <div className={styles.placeholder}>
          <Empty description={t("chatAudit.selectUserFirst")} />
        </div>
      ) : loadingThreads ? (
        <div className={styles.placeholder}>
          <Spin />
        </div>
      ) : ownedAgentCount === 0 ? (
        <div className={styles.placeholder}>
          <Empty description={t("chatAudit.noAgent")} />
        </div>
      ) : threads.length === 0 ? (
        <div className={styles.placeholder}>
          <Empty description={t("chatAudit.noThreads")} />
        </div>
      ) : (
        <List
          className={styles.threadList}
          dataSource={threads}
          renderItem={(item) => (
            <List.Item
              className={styles.threadItem}
              onClick={() => void openThread(item)}
            >
              <div className={styles.threadIcon}>
                <MessageSquareText size={16} strokeWidth={1.8} />
              </div>
              <div className={styles.threadMain}>
                <div className={styles.threadTitle}>
                  {item.thread.title || t("chatAudit.untitled")}
                </div>
                <div className={styles.threadMeta}>
                  <Tag>{item.agentName}</Tag>
                  <span>
                    {t("chatAudit.lastActive")}
                    {formatTime(item.thread.last_active)}
                  </span>
                </div>
              </div>
            </List.Item>
          )}
        />
      )}

      <Drawer
        open={drawerThread != null}
        onClose={() => setDrawerThread(null)}
        width={isMobile ? "100%" : 640}
        title={
          drawerThread?.thread.title || t("chatAudit.untitled")
        }
      >
        {loadingHistory ? (
          <div className={styles.placeholder}>
            <Spin />
          </div>
        ) : messages.length === 0 ? (
          <Empty description={t("chatAudit.noMessages")} />
        ) : (
          <div className={styles.messages}>
            {messages.map((item, index) => {
              const role = String(item.role || "").toLowerCase();
              const isUser = role === "user" || role === "human";
              return (
                <div
                  key={item.id || index}
                  className={`${styles.messageRow} ${
                    isUser ? styles.userRow : styles.assistantRow
                  }`}
                >
                  <div className={styles.avatar}>
                    <Avatar
                      size={28}
                      icon={<UserIcon size={14} strokeWidth={1.8} />}
                    />
                  </div>
                  <div
                    className={`${styles.bubble} ${
                      isUser ? styles.userBubble : styles.assistantBubble
                    }`}
                  >
                    <div className={styles.bubbleRole}>
                      {isUser
                        ? selectedUser?.username || t("chatAudit.roleUser")
                        : t("chatAudit.roleAssistant")}
                      {item.timestamp ? (
                        <span className={styles.bubbleTime}>
                          {" · "}
                          {formatTime(item.timestamp)}
                        </span>
                      ) : null}
                    </div>
                    <div className={styles.bubbleText}>
                      {contentText(item.content) || "—"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Drawer>
    </div>
  );
}
