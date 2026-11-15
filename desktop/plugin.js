/**
 * Capy Plus — desktop half. Comic-book speech bubbles over the core pet while
 * Capy Plus is the active pet: a "POW!" when a turn finishes, "WAAAH!" when a
 * tool fails, "ZZZ…" after a quiet stretch, plus a ⌘K "Pet the capybara".
 * Also: throttled remarks on the tool being run ("sniff sniff 🔍"), a daily
 * turn tally with snack milestones, a bath after 3 failed tools in a row, a
 * morning coffee joke and a late-night "go to bed". On hosts with pointer
 * interactions (ctx.pet.onInteract): "SQUEAK!" on a poke, "Wheee?!" when picked
 * up, "Oof!" on landing; grumpy lines instead when the host says it was asleep (cb(kind, { asleep })).
 *
 * The bubble is the host's own (ctx.pet.say); this plugin only restyles ITS
 * bubble (scoped to data-pet-plugin="capy-plus") with an injected <style>
 * that is removed on dispose. ⌘K → "Capy Plus: toggle comic bubbles" turns it off.
 *
 * Plain ESM, loaded uncompiled. Only @hermes/plugin-sdk / react resolve.
 */

import { host, PALETTE_AREA } from '@hermes/plugin-sdk'

const ID = 'capy-plus'
const SLUG = 'capy-plus'
// A beat after pet.json's sleep.afterSeconds (300), so the snoring starts once the sprite is asleep.
const NAP_AFTER_MS = (300 + 5) * 1000
const SNORE_EVERY_MS = 25 * 1000
const STYLE_ID = 'capy-plus-comic-bubble'

const HAPPY = ['POW! Nailed it!', 'KA-CHING!', 'BOOM! Done!', 'WHEEE! ✨', 'SQUEAK SQUEAK!', 'TA-DAAA!', 'Cache hit! 💥']
const SAD = ['WAAAH! 😭', '*BONK* ouch…', 'NOOO! 💧', 'Sniff… it broke…', 'KRAK! 💢']
const SLEEPY = ['ZZZ…', 'zzzZZZ… 💤', '*SNORE*', 'Mmm… oranges… 🍊']
const PETTED = ['PURRR! 🧡', 'More scratches!', 'HEHEHE!', 'You are my favourite human!', '*happy wiggle*']
const SNACKS = ['snack time? 🍉', 'watermelon break? 🍉', 'orange o\'clock? 🍊', 'grass buffet? 🌿', 'pumpkin party? 🎃', 'corn on the cob? 🌽']
const BATH = ['I need a bath… 🛁', 'Three bonks in a row… 🛁', 'Hot spring, please… ♨️']
const COFFEE = ['Coffee first? ☕', 'Morning! Is that coffee? ☕', '*yawn* …coffee? ☕']
const POKED = ['SQUEAK!', 'SQUEAK!', ...PETTED]
const INTERACT_LINES = { poke: POKED, pickup: ['Wheee?!', 'Put me down!'], land: ['Oof!', '*dizzy*'] }
const WOKEN_LINES = { // woken from the onsen nap (hosts that pass { asleep })
  poke: ['Five more minutes… 😾', 'Hey! I was napping!', '*grumbles in yuzu*'],
  pickup: ['Wha—? Put me back in the bath!', 'Hey! My bath! ♨️']
}
const INTERACT_EVERY_MS = 1500 // a flurry of clicks/drags gets one bubble, not a flicker
const LATE = ["It's late, go to bed 🌙", 'Past midnight… bedtime? 🌙', 'Even capybaras sleep… 💤🌙']
const TOOL_LINES = [
  [/^(web_|browser)/, ['sniff sniff 🔍', '*nose twitch* 🔍', 'Ooh, the internet!', 'Fetching! 🐾']],
  [/^(terminal|execute_code)$/, ['*tap tap*', 'clackety-clack ⌨️', 'beep boop…']],
  [/^(write_file|patch)$/, ['scribble…', '*scribble scribble* ✏️', 'Writing it down!']],
  [/^(read_file|search_files)$/, ['reading… 📖', '*page flip* 📖', 'hmm, let me look… 👀']],
  [/^delegate_task$/, ['calling my friends!', 'Squad, assemble! 🦫🦫', 'Backup is coming!']]
]
const MILESTONES = [10, 25, 50, 100]
const TOOL_EVERY_MS = 45 * 1000
const MOOD_QUIET_MS = 8 * 1000 // longer than any mood ttl, so a tool remark never lands on a mood bubble

const pick = list => list[Math.floor(Math.random() * list.length)]
const toolLines = name => (TOOL_LINES.find(([re]) => re.test(name || '')) || [])[1]
const pad = n => String(n).padStart(2, '0')
const dayKey = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const bumpTally = (tally, day) => ({ day, turns: tally && tally.day === day ? tally.turns + 1 : 1 })
const isMilestone = n => MILESTONES.includes(n)
const turnLine = (turns, hour) =>
  isMilestone(turns) ? `That's ${turns} tasks today, ${pick(SNACKS)}`
  : turns === 1 && hour >= 6 && hour < 11 ? pick(COFFEE)
  : null

// Comic look for this plugin's bubble only. Colours are deliberately ink-on-paper
// (a comic panel), not theme colours, so it reads the same in light and dark.
const B = `[data-slot="pet-plugin-bubble"][data-pet-plugin="${ID}"]`
const R = `[style*="right: 0"] > ${B}` // pet parked on the right half → bubble right-aligned
const COMIC_CSS = `
${B} {
  position: relative;
  background: #fffdf4 !important;
  color: #141414 !important;
  border: 2.5px solid #141414 !important;
  border-radius: 16px !important;
  box-shadow: 3px 3px 0 #141414 !important;
  padding: 6px 11px 7px !important;
  font-family: "Comic Sans MS", "Chalkboard SE", "Comic Neue", "Marker Felt", cursive !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  letter-spacing: 0.3px;
  transform-origin: 20px 100%;
  animation: capy-plus-pop 360ms cubic-bezier(.2, 1.6, .4, 1) both, capy-plus-bob 2.4s ease-in-out 360ms infinite;
}
${B} > span:first-child, ${B} svg { display: none; }
${B}::before, ${B}::after { content: ""; position: absolute; width: 0; height: 0; border-style: solid; }
${B}::before { bottom: -13px; left: 18px; border-width: 13px 9px 0 3px; border-color: #141414 transparent transparent transparent; }
${B}::after { bottom: -8.5px; left: 20.5px; border-width: 9px 6px 0 2px; border-color: #fffdf4 transparent transparent transparent; }
${R} { transform-origin: calc(100% - 20px) 100%; }
${R}::before { left: auto; right: 18px; border-width: 13px 3px 0 9px; }
${R}::after { left: auto; right: 20.5px; border-width: 9px 2px 0 6px; }
@keyframes capy-plus-pop {
  0% { transform: scale(.3) rotate(-8deg); opacity: 0; }
  100% { transform: scale(1) rotate(-2deg); opacity: 1; }
}
@keyframes capy-plus-bob {
  0%, 100% { transform: rotate(-2deg) translateY(0); }
  50% { transform: rotate(1.5deg) translateY(-2px); }
}
@media (prefers-reduced-motion: reduce) { ${B} { animation: none; transform: rotate(-2deg); } }
`

export default {
  id: ID,
  name: 'Capy Plus',
  register(ctx) {
    let active = false
    let cancelNap = () => undefined
    let cancelSnore = () => undefined
    let moodAt = 0
    let toolAt = 0
    let failStreak = 0
    let lateHour = ''

    // --- comic style (on by default, remembered per device) ---
    const applyStyle = on => {
      document.getElementById(STYLE_ID)?.remove()
      if (!on) return
      const el = document.createElement('style')
      el.id = STYLE_ID
      el.textContent = COMIC_CSS
      document.head.appendChild(el)
    }
    applyStyle(ctx.storage.get('comic', true))
    ctx.onDispose(() => applyStyle(false))

    // Only talk while Capy Plus is the pet on screen — never over someone else's mascot.
    const refreshActive = () =>
      host
        .request('pet.info.meta', {})
        .then(meta => {
          active = Boolean(meta && meta.enabled && meta.slug === SLUG)
          if (!active) ctx.pet.clear()
        })
        .catch(() => {
          active = false
        })

    const say = (text, opts = {}) => {
      if (active && ctx.pet.visible.get()) ctx.pet.say(text, opts)
    }

    const mood = (text, opts = {}) => {
      moodAt = Date.now()
      ctx.pet.clear('tool')
      say(text, { id: 'mood', ttlMs: 5000, ...opts })
    }

    const stopNap = () => {
      cancelNap()
      cancelSnore()
      ctx.pet.clear('sleep')
    }

    const armNap = () => {
      stopNap()
      cancelNap = ctx.setTimeout(() => {
        const snore = () => {
          moodAt = Date.now()
          say(pick(SLEEPY), { id: 'sleep', ttlMs: 20000 })
        }
        snore()
        cancelSnore = ctx.setInterval(snore, SNORE_EVERY_MS)
      }, NAP_AFTER_MS)
    }

    // Any activity wakes the capybara and restarts the nap countdown.
    const unsubBusy = host.state.busy.subscribe(busy => (busy ? stopNap() : armNap()))
    ctx.onDispose(() => {
      stopNap()
      if (typeof unsubBusy === 'function') unsubBusy()
    })

    ctx.onEvent('message.complete', ({ replayed } = {}) => {
      armNap()
      if (replayed) return
      failStreak = 0
      const now = new Date()
      const tally = bumpTally(ctx.storage.get('tally', null), dayKey(now))
      ctx.storage.set('tally', tally)
      const hour = now.getHours()
      const hourKey = `${tally.day}T${hour}`
      let line = turnLine(tally.turns, hour)
      if (!line && hour < 5 && lateHour !== hourKey) {
        lateHour = hourKey
        line = pick(LATE)
      }
      mood(line || pick(HAPPY))
    })

    // Named on tool.start already, so the remark lands while the tool is still running.
    ctx.onEvent('tool.start', ({ payload, replayed } = {}) => {
      const lines = !replayed && toolLines(payload && payload.name)
      const now = Date.now()
      if (!lines || now - toolAt < TOOL_EVERY_MS || now - moodAt < MOOD_QUIET_MS) return
      toolAt = now
      say(pick(lines), { id: 'tool', ttlMs: 3500 })
    })

    ctx.onEvent('tool.complete', ({ payload, replayed } = {}) => {
      if (replayed) return
      if (!(payload && payload.error)) return void (failStreak = 0)
      failStreak += 1
      if (failStreak === 3) mood(pick(BATH), { tone: 'error', ttlMs: 6000 })
      else mood(pick(SAD), { tone: 'error', ttlMs: 6000 })
    })

    // Pointer interactions (newer hosts only; 'drop' stays quiet, 'land' follows it).
    let interactAt = 0
    if (typeof ctx.pet.onInteract === 'function') {
      const unsubInteract = ctx.pet.onInteract((kind, info) => {
        const lines = (info?.asleep && WOKEN_LINES[kind]) || INTERACT_LINES[kind]
        const now = Date.now()
        if (!lines || now - interactAt < INTERACT_EVERY_MS) return
        interactAt = now
        if (!host.state.busy.get?.()) armNap() // wakes it up; no nap countdown mid-run
        mood(pick(lines), { ttlMs: 3000 })
      })
      if (typeof unsubInteract === 'function') ctx.onDispose(unsubInteract)
    }

    ctx.onEvent('pet.changed', refreshActive)
    ctx.onEvent('gateway.ready', refreshActive)
    refreshActive()
    ctx.setInterval(refreshActive, 60000)

    ctx.register({
      id: 'pet',
      area: PALETTE_AREA,
      data: {
        id: 'capy-plus.pet',
        label: 'Pet the capybara',
        keywords: ['capy', 'capybara', 'pet', 'scratch'],
        run: () => {
          armNap()
          if (active) mood(pick(PETTED))
          else host.notify({ kind: 'info', message: 'Capy Plus is not your active pet — run `hermes capy select`.' })
        }
      }
    })

    ctx.register({
      id: 'comic',
      area: PALETTE_AREA,
      data: {
        id: 'capy-plus.comic',
        label: 'Capy Plus: toggle comic bubbles',
        keywords: ['capy', 'comic', 'bubble', 'style'],
        run: () => {
          const next = !ctx.storage.get('comic', true)
          ctx.storage.set('comic', next)
          applyStyle(next)
          mood(next ? 'KAPOW! Comic mode!' : 'back to normal…', { ttlMs: 4000 })
        }
      }
    })
  }
}
