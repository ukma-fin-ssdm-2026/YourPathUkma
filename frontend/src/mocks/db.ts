// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
import type { DeaneryDocument, Me, ModerationItem, Preferences, SyncJob } from "../api/types";
import { emptyMe, seedModerationItems, seedSyncJobs } from "./fixtures";

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
  };
} = {
  signedIn: false,
  me: emptyMe(),
  documents: [],
  docPolls: {},
  nextDocId: 1,
  preferences: {},
  admin: { syncJobs: seedSyncJobs(), syncPolls: {}, moderationItems: seedModerationItems() },
};

export function resetMockDb(): void {
  db.signedIn = false;
  db.me = emptyMe();
  db.documents = [];
  db.docPolls = {};
  db.nextDocId = 1;
  db.preferences = {};
  db.admin = { syncJobs: seedSyncJobs(), syncPolls: {}, moderationItems: seedModerationItems() };
}
