import { create } from "zustand";
import { api, Scope } from "../lib/api";
import {
  fsSupported, pickDirectory, queryPerm, requestPerm, walk, readBuf, writeLocal,
  sha256, isTextFile, mergeLines,
} from "../lib/fsAccess";
import { listMappings, saveMapping, deleteMapping, SyncMapping } from "../lib/syncDb";
import { useSettings } from "./settings";

export type MappingStatus = "syncing" | "idle" | "resume" | "conflict" | "error";

export interface Conflict {
  rel: string;
  localText: string;
  webText: string;
}

export interface MappingState {
  id: string;
  handle: any;
  scope: Scope;
  path: string;
  localName: string;
  uploaded: string[];
  status: MappingStatus;
  conflicts: Conflict[];
  stats: { up: number; down: number } | null;
  error: string | null;
}

interface SyncState {
  supported: boolean;
  userId: string | null;
  mappings: MappingState[];
  init: (userId: string) => Promise<void>;
  addMapping: (scope: Scope, path: string) => Promise<void>;
  syncOne: (id: string) => Promise<void>;
  resumeOne: (id: string) => Promise<void>;
  resolveConflict: (id: string, rel: string, choice: "local" | "web" | "merge") => Promise<void>;
  disconnect: (id: string, deleteUploaded: boolean) => Promise<void>;
}

const enc = (s: string): ArrayBuffer => new TextEncoder().encode(s).buffer as ArrayBuffer;
const dec = (b: ArrayBuffer): string => new TextDecoder().decode(b);
const joinPath = (base: string, rel: string) => (base ? `${base}/${rel}` : rel);

async function fetchWebBuf(scope: Scope, path: string, rel: string): Promise<ArrayBuffer> {
  const res = await fetch(api.syncDownloadUrl(scope, path, rel), { credentials: "include" });
  if (!res.ok) throw new Error(`다운로드 실패: ${rel}`);
  return res.arrayBuffer();
}

const toState = (m: SyncMapping): MappingState => ({
  id: m.id,
  handle: m.handle,
  scope: m.scope,
  path: m.path,
  localName: m.handle?.name ?? "",
  uploaded: m.uploaded ?? [],
  status: "resume",
  conflicts: [],
  stats: null,
  error: null,
});

export const useSync = create<SyncState>((set, get) => {
  const patch = (id: string, p: Partial<MappingState>) =>
    set((s) => ({ mappings: s.mappings.map((m) => (m.id === id ? { ...m, ...p } : m)) }));

  const persist = async (m: MappingState) => {
    await saveMapping({
      id: m.id, userId: get().userId!, handle: m.handle,
      scope: m.scope as any, path: m.path, uploaded: m.uploaded,
    }).catch(() => {});
  };

  const runSync = async (id: string) => {
    const m = get().mappings.find((x) => x.id === id);
    if (!m) return;
    patch(id, { status: "syncing", error: null, conflicts: [] });
    const sy = useSettings.getState().settings?.sync;
    const textPolicy = sy?.text_conflict ?? "ask";
    const binaryPolicy = sy?.binary_policy ?? "local";
    const uploaded = new Set(m.uploaded);
    const markUp = (rel: string) => uploaded.add(rel);
    try {
      const localFiles = await walk(m.handle);
      const localMap = new Map<string, { hash: string; buf: ArrayBuffer }>();
      for (const f of localFiles) {
        const buf = await readBuf(f.handle);
        localMap.set(f.rel, { hash: await sha256(buf), buf });
      }
      const manifest = await api.syncManifest(m.scope, m.path);
      const webMap = new Map(manifest.files.map((f) => [f.rel, f.hash]));

      const conflicts: Conflict[] = [];
      let up = 0, down = 0;

      for (const [rel, lf] of localMap) {
        const wh = webMap.get(rel);
        if (wh === undefined) {
          await api.syncUpload(m.scope, m.path, rel, lf.buf);
          markUp(rel); up++;
        } else if (wh === lf.hash) {
          markUp(rel); // 동일 파일도 우리가 올린 것으로 간주(추적)
        } else if (isTextFile(rel)) {
          const localText = dec(lf.buf);
          const webText = dec(await fetchWebBuf(m.scope, m.path, rel));
          if (textPolicy === "local") { await api.syncUpload(m.scope, m.path, rel, lf.buf); markUp(rel); up++; }
          else if (textPolicy === "web") { await writeLocal(m.handle, rel, enc(webText)); down++; }
          else if (textPolicy === "merge") {
            const merged = mergeLines(localText, webText);
            await api.syncUpload(m.scope, m.path, rel, enc(merged));
            await writeLocal(m.handle, rel, enc(merged)); markUp(rel); up++;
          } else conflicts.push({ rel, localText, webText });
        } else {
          if (binaryPolicy === "web") { await writeLocal(m.handle, rel, await fetchWebBuf(m.scope, m.path, rel)); down++; }
          else { await api.syncUpload(m.scope, m.path, rel, lf.buf); markUp(rel); up++; }
        }
      }
      for (const f of manifest.files) {
        if (!localMap.has(f.rel)) {
          await writeLocal(m.handle, f.rel, await fetchWebBuf(m.scope, m.path, f.rel));
          down++;
        }
      }

      const upList = [...uploaded];
      patch(id, { uploaded: upList, stats: { up, down }, conflicts, status: conflicts.length ? "conflict" : "idle" });
      await persist({ ...m, uploaded: upList });
    } catch (e) {
      patch(id, { status: "error", error: e instanceof Error ? e.message : "동기화 실패" });
    }
  };

  return {
    supported: fsSupported(),
    userId: null,
    mappings: [],

    init: async (userId) => {
      if (!fsSupported()) { set({ supported: false, userId }); return; }
      set({ userId });
      const stored = await listMappings(userId).catch(() => []);
      set({ mappings: stored.map(toState) });
      for (const m of get().mappings) {
        const perm = await queryPerm(m.handle);
        if (perm === "granted") await runSync(m.id);
        else patch(m.id, { status: "resume" });
      }
    },

    addMapping: async (scope, path) => {
      const userId = get().userId;
      if (!userId) return;
      const handle = await pickDirectory(); // 사용자 제스처
      // crypto.randomUUID는 브라우저 표준
      const id = (crypto as any).randomUUID ? (crypto as any).randomUUID() : String(handle.name) + ":" + path + ":" + performance.now();
      const rec: SyncMapping = { id, userId, handle, scope: scope as any, path, uploaded: [] };
      await saveMapping(rec);
      set((s) => ({ mappings: [...s.mappings, toState(rec)] }));
      await runSync(id);
    },

    syncOne: async (id) => { await runSync(id); },

    resumeOne: async (id) => {
      const m = get().mappings.find((x) => x.id === id);
      if (!m) return;
      const ok = await requestPerm(m.handle); // 사용자 제스처 내에서 호출
      if (!ok) { patch(id, { status: "resume", error: "폴더 접근 권한이 거부되었습니다." }); return; }
      await runSync(id);
    },

    resolveConflict: async (id, rel, choice) => {
      const m = get().mappings.find((x) => x.id === id);
      if (!m) return;
      const c = m.conflicts.find((x) => x.rel === rel);
      if (!c) return;
      try {
        if (choice === "local") { await api.syncUpload(m.scope, m.path, rel, enc(c.localText)); }
        else if (choice === "web") { await writeLocal(m.handle, rel, enc(c.webText)); }
        else {
          const merged = mergeLines(c.localText, c.webText);
          await api.syncUpload(m.scope, m.path, rel, enc(merged));
          await writeLocal(m.handle, rel, enc(merged));
        }
        const uploaded = choice === "web" ? m.uploaded : [...new Set([...m.uploaded, rel])];
        const rest = m.conflicts.filter((x) => x.rel !== rel);
        patch(id, { conflicts: rest, uploaded, status: rest.length ? "conflict" : "idle" });
        await persist({ ...m, uploaded });
      } catch (e) {
        patch(id, { error: e instanceof Error ? e.message : "충돌 처리 실패" });
      }
    },

    disconnect: async (id, deleteUploaded) => {
      const m = get().mappings.find((x) => x.id === id);
      if (deleteUploaded && m) {
        // 업로드했던 파일들을 웹에서 휴지통으로 이동 (파일 삭제 API = 휴지통 경유)
        for (const rel of m.uploaded) {
          await api.remove(m.scope, joinPath(m.path, rel)).catch(() => {});
        }
      }
      await deleteMapping(id).catch(() => {});
      set((s) => ({ mappings: s.mappings.filter((x) => x.id !== id) }));
    },
  };
});
