// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
import type {
  AdminUser,
  AuditLogEntry,
  DeaneryDocument,
  Direction,
  Me,
  ModerationItem,
  Preferences,
  SyncJob,
} from "../api/types";
import {
  emptyMe,
  seedAdminUsers,
  seedAuditLog,
  seedDirections,
  seedModerationItems,
  seedSyncJobs,
} from "./fixtures";

const initialAdminState = () => ({
  syncJobs: seedSyncJobs(),
  syncPolls: {} as Record<number, number>,
  moderationItems: seedModerationItems(),
  users: seedAdminUsers(),
  directions: seedDirections(),
  auditLog: seedAuditLog(),
});

/** Стан моків у пам'яті; у тестах скидається після кожного тесту. */
export const db: {
  signedIn: boolean;
  me: Me;
  documents: DeaneryDocument[];
  docPolls: Record<number, number>;
  nextDocId: number;
  preferences: Record<number, Preferences>;
  admin: {
    syncJobs: SyncJob[];
    syncPolls: Record<number, number>;
    moderationItems: ModerationItem[];
    users: AdminUser[];
    directions: Direction[];
    auditLog: AuditLogEntry[];
  };
} = {
  signedIn: false,
  me: emptyMe(),
  documents: [],
  docPolls: {},
  nextDocId: 1,
  preferences: {},
  admin: initialAdminState(),
};

export function resetMockDb(): void {
  db.signedIn = false;
  db.me = emptyMe();
  db.documents = [];
  db.docPolls = {};
  db.nextDocId = 1;
  db.preferences = {};
  db.admin = initialAdminState();
}
