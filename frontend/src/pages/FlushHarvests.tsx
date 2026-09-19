import { createSignal, onMount } from 'solid-js'
import { For } from 'solid-js'
import { ApiError, api } from '../api/client'
import type { FlushHarvest, HarvestGrade, Room } from '../types'

interface QuotaConflict {
  reason?: string
  roomId?: number
  workDate?: string
  grade?: string
  capKg?: number
  usedKg?: number
  incomingKg?: number
  projectedKg?: number
  remainingKg?: number
}

const grades: HarvestGrade[] = ['A', 'B', 'C']

function toLocalInput(iso?: string) {
  const d = iso ? new Date(iso) : new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const empty = {
  roomId: '',
  harvestedAt: toLocalInput(),
  flushNo: '1',
  weightKg: '',
  grade: 'A' as HarvestGrade,
  operatorName: '',
}

export default function FlushHarvests() {
  const [rows, setRows] = createSignal<FlushHarvest[]>([])
  const [rooms, setRooms] = createSignal<Room[]>([])
  const [form, setForm] = createSignal({ ...empty })
  const [error, setError] = createSignal('')
  const [conflict, setConflict] = createSignal<QuotaConflict | null>(null)

  async function load() {
    const [harvests, roomList] = await Promise.all([
      api<FlushHarvest[]>('/api/flush-harvests'),
      api<Room[]>('/api/rooms'),
    ])
    setRows(harvests)
    setRooms(roomList)
  }

  onMount(() => {
    load().catch((e) => setError(e.message))
  })

  async function onSubmit(e: Event) {
    e.preventDefault()
    setError('')
    setConflict(null)
    try {
      await api('/api/flush-harvests', {
        method: 'POST',
        body: JSON.stringify({
          roomId: Number(form().roomId),
          harvestedAt: new Date(form().harvestedAt).toISOString(),
          flushNo: Number(form().flushNo),
          weightKg: Number(form().weightKg),
          grade: form().grade,
          operatorName: form().operatorName,
        }),
      })
      setForm({ ...empty, harvestedAt: toLocalInput() })
      await load()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict((err.data ?? null) as QuotaConflict | null)
      }
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该采收记录？')) return
    try {
      await api(`/api/flush-harvests/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  return (
    <div>
      <header class="page-header">
        <h1>采收记录</h1>
        <p class="muted">
          潮次、等级与重量；weightKg 须 &gt; 0；按东八区自然日受当日等级配额约束
        </p>
      </header>
      {error() && <div class="error">{error()}</div>}
      {conflict() && (
        <div class="panel quota-conflict">
          <div class="quota-conflict-title">
            {conflict()?.reason === 'quota_missing' ? '当日无配额行' : '超出当日采收配额'}
          </div>
          <div class="muted">
            {conflict()?.reason === 'quota_missing'
              ? '默认策略为拒绝采收：请先在「采收配额」页为该出菇室当日该等级配置配额。'
              : '按东八区（UTC+8）自然日累计，本次入库将超过 capKg，已拒绝。'}
          </div>
          {conflict()?.reason === 'quota_exceeded' && (
            <table class="quota-echo">
              <tbody>
                <tr><th>工作日</th><td>{conflict()?.workDate}</td></tr>
                <tr><th>等级</th><td>{conflict()?.grade}</td></tr>
                <tr><th>当日累计</th><td>{conflict()?.usedKg} kg</td></tr>
                <tr><th>本次重量</th><td>{conflict()?.incomingKg} kg</td></tr>
                <tr><th>预计合计</th><td>{conflict()?.projectedKg} kg</td></tr>
                <tr><th>配额上限</th><td>{conflict()?.capKg} kg</td></tr>
                <tr><th>剩余额度</th><td>{conflict()?.remainingKg} kg</td></tr>
              </tbody>
            </table>
          )}
          <a class="btn ghost" href={`/harvest-quotas?roomId=${conflict()?.roomId ?? ''}`}>
            前往配置/查看配额
          </a>
        </div>
      )}

      <form class="panel form-grid" onSubmit={onSubmit}>
        <label>
          出菇室
          <select
            value={form().roomId}
            onChange={(e) => setForm({ ...form(), roomId: e.currentTarget.value })}
            required
          >
            <option value="">选择出菇室</option>
            <For each={rooms()}>
              {(r) => (
                <option value={String(r.id)}>
                  {r.roomCode} · {r.species}
                </option>
              )}
            </For>
          </select>
        </label>
        <label>
          采收时间
          <input
            type="datetime-local"
            value={form().harvestedAt}
            onInput={(e) => setForm({ ...form(), harvestedAt: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          潮次
          <input
            type="number"
            min="1"
            value={form().flushNo}
            onInput={(e) => setForm({ ...form(), flushNo: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          重量 (kg)
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={form().weightKg}
            onInput={(e) => setForm({ ...form(), weightKg: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          等级
          <select
            value={form().grade}
            onChange={(e) =>
              setForm({ ...form(), grade: e.currentTarget.value as HarvestGrade })
            }
          >
            <For each={grades}>{(g) => <option value={g}>{g}</option>}</For>
          </select>
        </label>
        <label>
          操作人
          <input
            value={form().operatorName}
            onInput={(e) => setForm({ ...form(), operatorName: e.currentTarget.value })}
            required
          />
        </label>
        <button type="submit" class="btn primary">
          新增采收
        </button>
      </form>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>室 ID</th>
              <th>时间</th>
              <th>潮次</th>
              <th>重量</th>
              <th>等级</th>
              <th>操作人</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <For each={rows()}>
              {(r) => (
                <tr>
                  <td>{r.id}</td>
                  <td>{r.roomId}</td>
                  <td>{new Date(r.harvestedAt).toLocaleString()}</td>
                  <td>{r.flushNo}</td>
                  <td>{r.weightKg}</td>
                  <td>
                    <span class={`badge grade-${r.grade.toLowerCase()}`}>{r.grade}</span>
                  </td>
                  <td>{r.operatorName}</td>
                  <td>
                    <button type="button" class="btn ghost" onClick={() => remove(r.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
    </div>
  )
}
