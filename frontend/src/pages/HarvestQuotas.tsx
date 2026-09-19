import { createSignal, onMount } from 'solid-js'
import { For } from 'solid-js'
import { useSearchParams } from '@solidjs/router'
import { api } from '../api/client'
import type { HarvestGrade, HarvestQuotaDay, Room } from '../types'

const grades: HarvestGrade[] = ['A', 'B', 'C']

// 与后端日切口径一致：东八区自然日，不依赖浏览器本地时区
function todayCn() {
  return new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10)
}

export default function HarvestQuotas() {
  const [searchParams] = useSearchParams()
  const initialRoomId = typeof searchParams.roomId === 'string' ? searchParams.roomId : ''

  const [rows, setRows] = createSignal<HarvestQuotaDay[]>([])
  const [rooms, setRooms] = createSignal<Room[]>([])
  const [filterRoomId, setFilterRoomId] = createSignal(initialRoomId)
  const [filterDate, setFilterDate] = createSignal('')
  const [form, setForm] = createSignal({
    roomId: initialRoomId,
    workDate: todayCn(),
    grade: 'A' as HarvestGrade,
    capKg: '',
  })
  const [error, setError] = createSignal('')

  async function load() {
    const params = new URLSearchParams()
    if (filterRoomId()) params.set('roomId', filterRoomId())
    if (filterDate()) params.set('workDate', filterDate())
    const qs = params.toString()
    const [quotas, roomList] = await Promise.all([
      api<HarvestQuotaDay[]>(`/api/harvest-quota-days${qs ? `?${qs}` : ''}`),
      api<Room[]>('/api/rooms'),
    ])
    setRows(quotas)
    setRooms(roomList)
  }

  onMount(() => {
    load().catch((e) => setError(e.message))
  })

  async function onSubmit(e: Event) {
    e.preventDefault()
    setError('')
    try {
      await api('/api/harvest-quota-days', {
        method: 'POST',
        body: JSON.stringify({
          roomId: Number(form().roomId),
          workDate: form().workDate,
          grade: form().grade,
          capKg: Number(form().capKg),
        }),
      })
      setForm({ ...form(), capKg: '' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  async function remove(id: number) {
    if (!confirm('确认删除该配额？删除后当日该等级采收将被拒绝。')) return
    try {
      await api(`/api/harvest-quota-days/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  function roomLabel(roomId: number) {
    const r = rooms().find((x) => x.id === roomId)
    return r ? `${r.roomCode} · ${r.species}` : `#${roomId}`
  }

  return (
    <div>
      <header class="page-header">
        <h1>采收配额</h1>
        <p class="muted">
          按出菇室 · 东八区自然日 · 等级设定当日可采上限；未设配额的日级组合将被拒绝采收（409）
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
              {(r) => (
                <option value={String(r.id)}>
                  {r.roomCode} · {r.species}
                </option>
              )}
            </For>
          </select>
        </label>
        <label>
          工作日（东八区）
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
          上限 (kg)
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

      <div class="panel form-grid">
        <label>
          按出菇室筛选
          <select
            value={filterRoomId()}
            onChange={(e) => {
              setFilterRoomId(e.currentTarget.value)
              load().catch((err) => setError(err.message))
            }}
          >
            <option value="">全部</option>
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
          按工作日筛选
          <input
            type="date"
            value={filterDate()}
            onInput={(e) => {
              setFilterDate(e.currentTarget.value)
              load().catch((err) => setError(err.message))
            }}
          />
        </label>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>出菇室</th>
              <th>工作日（东八区）</th>
              <th>等级</th>
              <th>上限 (kg)</th>
              <th>已采 (kg)</th>
              <th>剩余 (kg)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <For each={rows()}>
              {(r) => (
                <tr>
                  <td>{r.id}</td>
                  <td>{roomLabel(r.roomId)}</td>
                  <td>{r.workDate}</td>
                  <td>
                    <span class={`badge grade-${r.grade.toLowerCase()}`}>{r.grade}</span>
                  </td>
                  <td>{r.capKg}</td>
                  <td>{r.usedKg}</td>
                  <td>
                    <span class={r.remainingKg > 0 ? 'badge fruiting' : 'badge sanitize'}>
                      {r.remainingKg}
                    </span>
                  </td>
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
