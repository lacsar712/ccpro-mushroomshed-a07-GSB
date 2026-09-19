import { useSearchParams } from '@solidjs/router'
import { createSignal, For, onMount } from 'solid-js'
import { api } from '../api/client'
import type { HarvestGrade, HarvestQuotaDay, Room } from '../types'

const grades: HarvestGrade[] = ['A', 'B', 'C']

function cnToday(): string {
  // 东八区自然日，不用本地/UTC 零点
  const now = new Date()
  const cn = new Date(now.getTime() + 8 * 3600_000 + now.getTimezoneOffset() * 60_000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${cn.getFullYear()}-${pad(cn.getMonth() + 1)}-${pad(cn.getDate())}`
}

const empty = {
  roomId: '',
  workDate: cnToday(),
  grade: 'A' as HarvestGrade,
  capKg: '',
}

export default function HarvestQuotas() {
  const [rows, setRows] = createSignal<HarvestQuotaDay[]>([])
  const [rooms, setRooms] = createSignal<Room[]>([])
  const [form, setForm] = createSignal({ ...empty })
  const [error, setError] = createSignal('')
  const [searchParams] = useSearchParams()

  function roomLabel(id: number) {
    const r = rooms().find((x) => x.id === id)
    return r ? `${r.roomCode} · ${r.species}` : `#${id}`
  }

  async function load() {
    const roomId = searchParams.roomId
    const [quotas, roomList] = await Promise.all([
      api<HarvestQuotaDay[]>(roomId ? `/api/harvest-quotas?roomId=${roomId}` : '/api/harvest-quotas'),
      api<Room[]>('/api/rooms'),
    ])
    setRows(quotas)
    setRooms(roomList)
  }

  onMount(() => {
    if (searchParams.roomId) {
      setForm({ ...form(), roomId: String(searchParams.roomId) })
    }
    load().catch((e) => setError(e.message))
  })

  async function onSubmit(e: Event) {
    e.preventDefault()
    setError('')
    try {
      await api('/api/harvest-quotas', {
        method: 'POST',
        body: JSON.stringify({
          roomId: Number(form().roomId),
          workDate: form().workDate,
          grade: form().grade,
          capKg: Number(form().capKg),
        }),
      })
      setForm({ ...empty, roomId: form().roomId })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该日配额？')) return
    try {
      await api(`/api/harvest-quotas/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  return (
    <div>
      <header class="page-header">
        <h1>采收配额</h1>
        <p class="muted">
          按东八区（UTC+8）自然日切日，同出菇室同日同等级唯一；无配额行默认拒绝采收
        </p>
      </header>
      {error() && <div class="error">{error()}</div>}

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
              {(r) => <option value={String(r.id)}>{r.roomCode} · {r.species}</option>}
            </For>
          </select>
        </label>
        <label>
          工作日（东八区自然日）
          <input
            type="date"
            value={form().workDate}
            onInput={(e) => setForm({ ...form(), workDate: e.currentTarget.value })}
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
          配额上限 (kg)
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={form().capKg}
            onInput={(e) => setForm({ ...form(), capKg: e.currentTarget.value })}
            required
          />
        </label>
        <button type="submit" class="btn primary">
          新增配额
        </button>
      </form>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>出菇室</th>
              <th>工作日</th>
              <th>等级</th>
              <th>上限 (kg)</th>
              <th>当日累计 (kg)</th>
              <th>剩余 (kg)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <For each={rows()}>
              {(q) => {
                const used = q.usedKg ?? 0
                const full = used + 1e-9 >= q.capKg
                return (
                  <tr>
                    <td>{q.id}</td>
                    <td>{roomLabel(q.roomId)}</td>
                    <td>{q.workDate}</td>
                    <td>
                      <span class={`badge grade-${q.grade.toLowerCase()}`}>{q.grade}</span>
                    </td>
                    <td>{q.capKg}</td>
                    <td class={full ? 'quota-full' : ''}>{used}</td>
                    <td>{q.remainingKg ?? Math.max(q.capKg - used, 0)}</td>
                    <td>
                      <button type="button" class="btn ghost" onClick={() => remove(q.id)}>
                        删除
                      </button>
                    </td>
                  </tr>
                )
              }}
            </For>
          </tbody>
        </table>
      </div>
    </div>
  )
}
