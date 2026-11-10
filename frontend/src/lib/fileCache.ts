// Keeps the last uploaded CSV (and its mapping) in IndexedDB for this browser, so the
// app can quietly re-send it if the serverless API restarted. Nothing leaves the browser
// except to this app's own API.
const DB = 'prognova', STORE = 'upload', KEY = 'last'

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export interface CachedUpload { id: string; file: File; mapping?: unknown; options?: unknown }

export async function saveUpload(v: CachedUpload): Promise<void> {
  try {
    const db = await open()
    await new Promise<void>((res, rej) => { const tx = db.transaction(STORE, 'readwrite'); tx.objectStore(STORE).put(v, KEY); tx.oncomplete = () => res(); tx.onerror = () => rej(tx.error) })
  } catch { /* storage blocked: recovery just won't be available after a reload */ }
}

export async function loadUpload(): Promise<CachedUpload | null> {
  try {
    const db = await open()
    return await new Promise((res) => { const r = db.transaction(STORE).objectStore(STORE).get(KEY); r.onsuccess = () => res((r.result as CachedUpload) || null); r.onerror = () => res(null) })
  } catch { return null }
}

export async function clearUpload(): Promise<void> {
  try { const db = await open(); db.transaction(STORE, 'readwrite').objectStore(STORE).delete(KEY) } catch { /* ignore */ }
}
