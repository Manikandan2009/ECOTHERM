export type JsonApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; detail: string }

type RequestOptions = {
  signal?: AbortSignal
  ttlMs: number
}

type CacheEntry = {
  expiresAt: number
  estimatedBytes: number
  result: JsonApiResult<unknown>
}

const MAX_CACHE_ENTRIES = 24
const MAX_CACHE_BYTES = 4 * 1024 * 1024
const responseCache = new Map<string, CacheEntry>()
const inFlightRequests = new Map<string, Promise<JsonApiResult<unknown>>>()
let cachedBytes = 0

export function requestJson<T>(
  url: string,
  { signal, ttlMs }: RequestOptions,
): Promise<JsonApiResult<T>> {
  if (signal?.aborted) return Promise.reject(abortError())

  const cached = responseCache.get(url)
  if (cached && cached.expiresAt > Date.now()) {
    responseCache.delete(url)
    responseCache.set(url, cached)
    return withAbort(Promise.resolve(cached.result as JsonApiResult<T>), signal)
  }
  if (cached) removeCached(url)

  let pending = inFlightRequests.get(url)
  if (!pending) {
    pending = fetch(url, { headers: { Accept: 'application/json' } })
      .then(async (response): Promise<JsonApiResult<unknown>> => {
        if (!response.ok) {
          return {
            ok: false,
            status: response.status,
            detail: await response.text(),
          }
        }
        return {
          ok: true,
          status: response.status,
          data: await response.json(),
        }
      })
      .then((result) => {
        if (result.ok && ttlMs > 0) cacheResult(url, result, ttlMs)
        return result
      })
    inFlightRequests.set(url, pending)
    void pending.then(
      () => {
        if (inFlightRequests.get(url) === pending) inFlightRequests.delete(url)
      },
      () => {
        if (inFlightRequests.get(url) === pending) inFlightRequests.delete(url)
      },
    )
  }

  return withAbort(pending as Promise<JsonApiResult<T>>, signal)
}

function cacheResult(
  url: string,
  result: JsonApiResult<unknown>,
  ttlMs: number,
): void {
  const estimatedBytes = JSON.stringify(result).length * 2
  if (estimatedBytes > MAX_CACHE_BYTES) return

  removeCached(url)
  responseCache.set(url, {
    expiresAt: Date.now() + ttlMs,
    estimatedBytes,
    result,
  })
  cachedBytes += estimatedBytes

  while (
    responseCache.size > MAX_CACHE_ENTRIES
    || cachedBytes > MAX_CACHE_BYTES
  ) {
    const oldestUrl = responseCache.keys().next().value
    if (oldestUrl === undefined) break
    removeCached(oldestUrl)
  }
}

function removeCached(url: string): void {
  const entry = responseCache.get(url)
  if (!entry) return
  cachedBytes -= entry.estimatedBytes
  responseCache.delete(url)
}

function withAbort<T>(
  promise: Promise<T>,
  signal?: AbortSignal,
): Promise<T> {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(abortError())

  return new Promise<T>((resolve, reject) => {
    const onAbort = () => {
      signal.removeEventListener('abort', onAbort)
      reject(abortError())
    }
    signal.addEventListener('abort', onAbort, { once: true })
    promise.then(
      (value) => {
        signal.removeEventListener('abort', onAbort)
        if (signal.aborted) reject(abortError())
        else resolve(value)
      },
      (error: unknown) => {
        signal.removeEventListener('abort', onAbort)
        reject(error)
      },
    )
  })
}

function abortError(): DOMException {
  return new DOMException('The request was aborted.', 'AbortError')
}
