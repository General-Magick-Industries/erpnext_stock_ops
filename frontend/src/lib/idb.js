// Penyimpanan foto offline sebagai Blob di IndexedDB.
// localStorage tidak cocok untuk biner/besar; IndexedDB menampung Blob langsung.

const DB_NAME = 'stockops-idb'
const STORE = 'photos'
let _db = null

function open() {
  if (_db) return Promise.resolve(_db)
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const s = db.createObjectStore(STORE, { keyPath: 'id' })
        s.createIndex('localId', 'localId', { unique: false })
      }
    }
    req.onsuccess = () => {
      _db = req.result
      resolve(_db)
    }
    req.onerror = () => reject(req.error)
  })
}

async function store(mode) {
  const db = await open()
  return db.transaction(STORE, mode).objectStore(STORE)
}

function p(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

// rec = { id, localId, blob, name }
export async function putPhoto(rec) {
  return p((await store('readwrite')).put(rec))
}

export async function getPhoto(id) {
  return p((await store('readonly')).get(id))
}

export async function getPhotosByLocalId(localId) {
  const idx = (await store('readonly')).index('localId')
  return new Promise((resolve, reject) => {
    const out = []
    const req = idx.openCursor(IDBKeyRange.only(localId))
    req.onsuccess = () => {
      const c = req.result
      if (c) {
        out.push(c.value)
        c.continue()
      } else resolve(out)
    }
    req.onerror = () => reject(req.error)
  })
}

export async function deletePhoto(id) {
  return p((await store('readwrite')).delete(id))
}

export async function deletePhotosByLocalId(localId) {
  const recs = await getPhotosByLocalId(localId)
  await Promise.all(recs.map((r) => deletePhoto(r.id)))
}
