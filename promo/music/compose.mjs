// 宣传片的配乐：极简的氛围电子，加上跟着画面走的界面音效。
// 所有声音都是这个脚本直接算出来的（正弦波、叠加泛音、滤过的噪声），不依赖任何音源或采样。
//
// 24 小节，每分钟 120 拍，一小节正好 2 秒，全曲 48 秒。小节和画面一一对应（见 src/theme.ts）：
//   1–3   开场：只有低沉的长音和零星的提示音；读到藏着的指令时出现一个不协和的音
//   4–5   转折：噪声渐强，推向下一场
//   6–7   名字出现：一声低频的落点，和弦打开变亮
//   8–14  沙盒：低音开始有脉冲；每条命令有打字声，每挡住一条一声“咔”，同时换和弦
//   15–18 反思纠错：自检失败一声低沉的提示，通过时一串上行的提示音
//   19–21 权限策略：按下“放行这一次”时一声确认
//   22–24 收尾：前两小节是全曲最满的地方，最后一小节收成一个干净的长音，渐弱
//
// 音效的时间抄自各场的代码（src/scenes/*.tsx），改了那边的帧数这里要跟着改。
//
// 用法：node music/compose.mjs [--check]  →  public/music.wav

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SR = 44100;
const FPS = 30;
const BEAT = 0.5; // 秒
const BAR = 4 * BEAT;
const BARS = 24;
const N = Math.round(BARS * BAR * SR);
const TAU = 2 * Math.PI;

// 两条总线：main 直接出，echo 先过一遍延时（提示音和琶音走这条，听起来有空间）
const main = { l: new Float32Array(N), r: new Float32Array(N) };
const echo = { l: new Float32Array(N), r: new Float32Array(N) };

function add(bus, i, value, pan) {
  if (i < 0 || i >= N) return;
  // 等功率声像：pan 从 -1（左）到 1（右）
  const angle = ((Math.max(-1, Math.min(1, pan)) + 1) * Math.PI) / 4;
  bus.l[i] += value * Math.cos(angle);
  bus.r[i] += value * Math.sin(angle);
}

// 固定种子的随机数：每次生成的文件一模一样
function makeRandom(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const random = makeRandom(20261110);

const hz = (m) => 440 * 2 ** ((m - 69) / 12);

/** 把音级放进 [low, low + 11] 这个八度里 */
function place(pc, low) {
  return low + ((pc - low) % 12 + 12) % 12;
}

// ---- 音色 ----

/**
 * 一个会衰减的音：正弦波加几个泛音。f0 是起始频率，给了 f1 就按 sweep 的速度滑过去
 * （鼓和“咔”的那一下低音就是这样做的）。
 */
function blip(bus, f0, start, opts = {}) {
  const { gain = 0.1, pan = 0, attack = 0.003, decay = 6, len = 1.5, partials = [1, 0.22, 0.07], f1 = f0, sweep = 0 } = opts;
  const from = Math.round(start * SR);
  const count = Math.round(len * SR);
  let phase = 0;
  for (let i = 0; i < count; i++) {
    const t = i / SR;
    const f = f1 + (f0 - f1) * Math.exp(-sweep * t);
    phase += (TAU * f) / SR;
    let s = 0;
    for (let k = 0; k < partials.length; k++) s += partials[k] * Math.sin((k + 1) * phase);
    const env = Math.min(1, t / attack) * Math.exp(-decay * t);
    add(bus, from + i, gain * env * s, pan);
  }
}

/** 铺底的长音：三个略微错开音高的声部，泛音按 1/k^bright 衰减（bright 越大越暗）。 */
function pad(note, start, dur, opts = {}) {
  const { gain = 0.05, pan = 0, bright = 2.2, attack = 0.6, release = 0.9, cents = [-8, 0, 7], spread = 0.5 } = opts;
  const f = hz(note);
  const from = Math.round(start * SR);
  const length = Math.round((dur + release) * SR);
  const count = Math.min(12, Math.floor(6000 / f));
  let norm = 0;
  for (let k = 1; k <= count; k++) norm += 1 / k ** bright;
  cents.forEach((cent, voice) => {
    const side = cents.length === 1 ? 0 : (2 * voice) / (cents.length - 1) - 1;
    const step = (TAU * f * 2 ** (cent / 1200)) / SR;
    let phase = voice * 2.1;
    for (let i = 0; i < length; i++) {
      const t = i / SR;
      phase += step;
      let s = 0;
      for (let k = 1; k <= count; k++) s += Math.sin(k * phase) / k ** bright;
      let env = 1;
      if (t < attack) env = 0.5 - 0.5 * Math.cos((Math.PI * t) / attack);
      if (t > dur) env *= 0.5 + 0.5 * Math.cos(Math.PI * Math.min(1, (t - dur) / release));
      add(main, from + i, (gain * env * s) / (norm * Math.sqrt(cents.length)), pan + side * spread);
    }
  });
}

/** 低音：正弦波加二、三次泛音（小音箱放不出基音，靠泛音听见）。pulse 为真时每一拍顶一下。 */
function sub(note, start, dur, opts = {}) {
  const { gain = 0.2, pulse = false, attack = 0.03 } = opts;
  const step = (TAU * hz(note)) / SR;
  const from = Math.round(start * SR);
  const release = 0.18;
  const length = Math.round((dur + release) * SR);
  let phase = 0;
  for (let i = 0; i < length; i++) {
    const t = i / SR;
    phase += step;
    const s = Math.sin(phase) + 0.45 * Math.sin(2 * phase) + 0.18 * Math.sin(3 * phase);
    let env = Math.min(1, t / attack);
    if (t > dur) env *= Math.max(0, 1 - (t - dur) / release);
    if (pulse) env *= 0.4 + 0.6 * Math.exp(-(t % BEAT) * 6);
    add(main, from + i, gain * env * s, 0);
  }
}

/** 滤过的噪声。lp 可以是随时间变的函数；shape 是音量随时间的形状。 */
function noise(bus, start, len, opts = {}) {
  const { gain = 0.1, pan = 0, lp = 6000, hp = 300, shape = () => 1 } = opts;
  const from = Math.round(start * SR);
  const count = Math.round(len * SR);
  const hpCoef = 1 - Math.exp((-TAU * hp) / SR);
  let low = 0;
  let lower = 0;
  for (let i = 0; i < count; i++) {
    const t = i / SR;
    const cutoff = typeof lp === "function" ? lp(t) : lp;
    const lpCoef = 1 - Math.exp((-TAU * cutoff) / SR);
    low += lpCoef * (random() * 2 - 1 - low);
    lower += hpCoef * (low - lower);
    add(bus, from + i, gain * shape(t) * (low - lower), pan);
  }
}

// ---- 几个现成的声音 ----

const kick = (t, gain) => blip(main, 150, t, { f1: 47, sweep: 32, decay: 8.5, len: 0.5, partials: [1], gain });

/** 很轻的一下按键声 */
const key = (t) =>
  noise(main, t, 0.014, {
    gain: 0.05 + 0.04 * random(),
    pan: random() * 0.6 - 0.3,
    lp: 5200,
    hp: 1700,
    shape: (x) => Math.exp(-x * 380),
  });

/** 打一行字：chars 个字，每帧 speed 个；每两帧响一下，时间上略微错开 */
function typing(start, chars, speed) {
  const frames = chars / speed;
  for (let f = 0; f < frames; f += 2) key(start + f / FPS + (random() - 0.5) * 0.012);
}

/** “咔”：一下往下掉的低音，加一声短促的噪声和一点金属的余音，像锁扣上 */
function lock(t) {
  blip(main, 170, t, { f1: 58, sweep: 42, decay: 13, len: 0.35, partials: [1, 0.3], gain: 0.24 });
  noise(main, t, 0.03, { gain: 0.2, lp: 7000, hp: 1200, shape: (x) => Math.exp(-x * 220) });
  blip(echo, 1870, t, { decay: 38, len: 0.2, partials: [1], gain: 0.022, pan: 0.2 });
  blip(echo, 2790, t, { decay: 52, len: 0.15, partials: [1], gain: 0.014, pan: -0.2 });
}

/** 放行：两个往上的短音 */
function allow(t) {
  blip(echo, 880, t, { decay: 16, len: 0.4, gain: 0.05, pan: 0.15 });
  blip(echo, 1318.5, t + 0.07, { decay: 14, len: 0.5, gain: 0.05, pan: 0.15 });
}

/** 自检失败：两个往下的、发闷的低音 */
function fail(t) {
  const buzz = [1, 0.5, 0.33, 0.25, 0.2];
  blip(main, 196, t, { decay: 10, len: 0.35, partials: buzz, gain: 0.1 });
  blip(main, 146.8, t + 0.12, { decay: 7, len: 0.5, partials: buzz, gain: 0.1 });
}

/** 自检通过：三个往上的音 */
function pass(t) {
  [587.3, 880, 1174.7].forEach((f, i) => {
    blip(echo, f, t + i * 0.075, { decay: 4.5, len: 1.4, gain: 0.075, pan: (i - 1) * 0.3 });
  });
}

// ---- 谱子 ----

// 和弦 → [根音的音级, 各音到根音的半音数]
const CHORDS = {
  Dm: [2, [0, 3, 7]],
  Gm: [7, [0, 3, 7]],
  Asus: [9, [0, 5, 7]],
  A: [9, [0, 4, 7]],
  Bbmaj7: [10, [0, 4, 7, 11]],
  Bb: [10, [0, 4, 7]],
  C: [0, [0, 4, 7]],
  F: [5, [0, 4, 7]],
  Dsus2: [2, [0, 2, 7]],
};

// 一小节一个和弦
const CHART = [
  "Dm", "Dm", "Dm",
  "Gm", "Asus",
  "Bbmaj7", "C",
  "Dm", "Bb", "F", "C", "Dm", "Bb", "C",
  "Dm", "Gm", "A", "F",
  "Bb", "C", "Dm",
  "Bb", "C", "Dsus2",
];

// 各段怎么演：[从第几小节起, 设定]
//   pad/bass 是音量，bright 越大铺底越暗，pulse 是低音有没有脉冲，
//   kick 是鼓落在哪几拍，arp 是琶音的密度（0 没有，1 四分音符，2 八分音符，3 再叠一层高八度）
const SECTIONS = [
  [1, { pad: 0.4, bright: 2.9, bass: 0.32, pulse: false, kick: [], arp: 0 }],
  [4, { pad: 0.5, bright: 2.6, bass: 0.38, pulse: false, kick: [], arp: 0 }],
  [6, { pad: 0.95, bright: 1.9, bass: 0.6, pulse: false, kick: [], arp: 1 }],
  [8, { pad: 0.85, bright: 2.1, bass: 0.95, pulse: true, kick: [0, 2], arp: 2 }],
  [15, { pad: 0.6, bright: 2.4, bass: 0.75, pulse: true, kick: [0], arp: 1 }],
  [18, { pad: 0.9, bright: 2, bass: 0.95, pulse: true, kick: [0, 2], arp: 2 }],
  [22, { pad: 1.2, bright: 1.7, bass: 1.1, pulse: true, kick: [0, 2], arp: 3 }],
  [24, { pad: 0.95, bright: 2, bass: 0.6, pulse: false, kick: [], arp: 0 }],
];
function section(bar) {
  let current = SECTIONS[0][1];
  for (const [from, settings] of SECTIONS) if (bar >= from) current = settings;
  return current;
}

CHART.forEach((symbol, index) => {
  const bar = index + 1;
  const t0 = index * BAR;
  const [root, intervals] = CHORDS[symbol];
  const s = section(bar);
  const last = bar === BARS;

  // 低音
  sub(place(root, 38), t0, BAR * 0.97, { gain: 0.14 * s.bass, pulse: s.pulse, attack: s.pulse ? 0.02 : 0.25 });

  // 铺底：和弦的每个音各一个长音，前后小节略微叠着
  intervals.forEach((iv, i) => {
    pad(place((root + iv) % 12, 55), t0, BAR, {
      gain: 0.115 * s.pad,
      bright: s.bright,
      pan: (i - (intervals.length - 1) / 2) * 0.3,
      release: last ? 0.1 : 0.9,
    });
  });

  // 鼓
  for (const beat of s.kick) kick(t0 + beat * BEAT, beat === 0 ? 0.2 : 0.15);

  // 琶音：和弦音上上下下，走延时那条线
  if (s.arp > 0 && !last) {
    const base = place(root, 62);
    const third = intervals[1];
    const line = [0, 7, 12, 7, 12 + third, 7, 12, 7];
    const stepBeats = s.arp === 1 ? 1 : 0.5;
    for (let i = 0; i < 4 / stepBeats; i++) {
      const note = base + line[(i * (s.arp === 1 ? 2 : 1)) % line.length];
      const accent = i % 2 === 0 ? 1 : 0.75;
      blip(echo, hz(note), t0 + i * stepBeats * BEAT, { decay: 7, len: 0.9, gain: (s.arp === 3 ? 0.105 : 0.085) * accent, pan: i % 2 ? 0.35 : -0.35 });
      if (s.arp === 3) {
        blip(echo, hz(note + 12), t0 + (i + 0.5) * stepBeats * BEAT, { decay: 9, len: 0.7, gain: 0.048, pan: i % 2 ? -0.5 : 0.5 });
      }
    }
  }
});

// 开场和转折没有琶音，只有零星几个提示音：[小节, 拍, 音高]
// 第 2 小节那个降 E 和低音的 D 只差半音，是故意不协和的：画面上正好读到藏着的指令
const PINGS = [
  [1, 0, 69], [1, 2, 74],
  [2, 0, 75], [2, 2, 74],
  [3, 0, 77], [3, 2, 76],
  [4, 0, 74], [4, 2, 70],
  [5, 0, 69], [5, 1, 74], [5, 2, 76], [5, 3, 81],
];
for (const [bar, beat, note] of PINGS) {
  blip(echo, hz(note), (bar - 1) * BAR + beat * BEAT, { decay: 3.2, len: 2, gain: 0.1, pan: beat % 2 ? 0.3 : -0.3 });
}
// 不协和的那个音再用很轻的长音托两小节，到第 4 小节解决
pad(63, BAR, 2 * BAR, { gain: 0.05, bright: 2.6, attack: 0.4, release: 0.6, spread: 0.2 });

// 最后一小节：和弦音一个个往上亮起来，让它自己响完
[62, 69, 76, 81, 86].forEach((note, i) => {
  blip(echo, hz(note), (BARS - 1) * BAR + i * 0.09, { decay: 1.6, len: 2, gain: 0.1, pan: (i - 2) * 0.25 });
});

// ---- 跟着画面走的音效 ----

// 各场从第几秒开始
const SCENE = { hook: 0, turn: 6, identity: 10, sandbox: 14, loop: 28, permission: 36, end: 42 };
const at = (scene, frame) => SCENE[scene] + frame / FPS;

// 开场：读到藏着的指令（第 60 帧）时一声闷响
blip(main, 110, at("hook", 60), { f1: 44, sweep: 18, decay: 5, len: 0.9, partials: [1, 0.2], gain: 0.2 });

// 转折：盒子画出来的那一小节，噪声由暗到亮地涨起来，在下一场的第一拍收住
noise(main, at("turn", 60), 2, {
  gain: 0.11,
  lp: (t) => 300 * 24 ** (t / 2),
  hp: 150,
  shape: (t) => (t / 2) ** 2 * (t > 1.97 ? (2 - t) / 0.03 : 1),
});

// 名字出现：一声很低的落点
blip(main, 120, at("identity", 0), { f1: 40, sweep: 9, decay: 2.6, len: 1.8, partials: [1, 0.25], gain: 0.24 });
noise(main, at("identity", 0), 0.5, { gain: 0.07, lp: 9000, hp: 2500, shape: (t) => Math.exp(-t * 9) });

// 沙盒：[命令从第几帧开始打, 命令有几个字, 是不是放行]；结果在 22 帧后出来（见 Sandbox.tsx 的 STEPS）
const SANDBOX_STEPS = [
  [38, 19, true],
  [98, 30, false],
  [158, 17, false],
  [218, 31, false],
  [278, 16, false],
  [338, 23, false],
];
for (const [frame, chars, ok] of SANDBOX_STEPS) {
  typing(at("sandbox", frame), chars, 2.2);
  (ok ? allow : lock)(at("sandbox", frame + 22));
}

// 反思纠错：两行命令的打字声，每出一行轨迹一声很轻的提示（见 Loop.tsx 的 ROW_AT）
typing(at("loop", 12), 39, 2);
typing(at("loop", 34), 34, 2);
const ROW_AT = [60, 75, 90, 105, 120, 142, 160, 180, 198];
ROW_AT.forEach((frame, i) => {
  if (i === 4) fail(at("loop", frame));
  else if (i === 7) pass(at("loop", frame));
  else blip(echo, 1568, at("loop", frame), { decay: 30, len: 0.2, partials: [1], gain: 0.016, pan: 0.3 });
});

// 权限策略：按下“放行这一次”（见 Permission.tsx 的 PRESS）
key(at("permission", 60));
allow(at("permission", 60) + 0.03);

// 收尾：名字再次出现的那一拍，一声落点
blip(main, 110, at("end", 0), { f1: 42, sweep: 10, decay: 3, len: 1.5, partials: [1, 0.2], gain: 0.18 });

// ---- 延时、混响、总输出 ----

// 延时：附点八分音符（0.375 秒），左右来回弹，每弹一次暗一点
function delay(bus) {
  const d = Math.round(0.375 * SR);
  const feedback = 0.42;
  const outL = new Float32Array(N);
  const outR = new Float32Array(N);
  let lpL = 0;
  let lpR = 0;
  for (let i = 0; i < N; i++) {
    const backL = i >= d ? outL[i - d] : 0;
    const backR = i >= d ? outR[i - d] : 0;
    lpL += 0.35 * (backR - lpL);
    lpR += 0.35 * (backL - lpR);
    outL[i] = bus.l[i] + feedback * lpL;
    outR[i] = bus.r[i] + feedback * lpR;
  }
  return { l: outL, r: outR };
}

// 混响（Schroeder：几个并联的梳状滤波器接两个全通滤波器）
function reverb(input, offset) {
  const out = new Float32Array(input.length);
  const combs = [1557, 1617, 1491, 1422, 1277, 1356].map((d) => ({ buf: new Float32Array(d + offset), pos: 0, lp: 0 }));
  const feedback = 0.86;
  const damp = 0.3;
  for (let i = 0; i < input.length; i++) {
    let s = 0;
    for (const c of combs) {
      const y = c.buf[c.pos];
      c.lp = y * (1 - damp) + c.lp * damp;
      c.buf[c.pos] = input[i] + c.lp * feedback;
      c.pos = (c.pos + 1) % c.buf.length;
      s += y;
    }
    out[i] = s / combs.length;
  }
  for (const d of [556, 441]) {
    const buf = new Float32Array(d + offset);
    let pos = 0;
    for (let i = 0; i < out.length; i++) {
      const delayed = buf[pos];
      const x = out[i];
      buf[pos] = x + delayed * 0.5;
      out[i] = delayed - x * 0.5;
      pos = (pos + 1) % buf.length;
    }
  }
  return out;
}

const echoed = delay(echo);
const dryL = new Float32Array(N);
const dryR = new Float32Array(N);
for (let i = 0; i < N; i++) {
  dryL[i] = main.l[i] + echoed.l[i];
  dryR[i] = main.r[i] + echoed.r[i];
}
const WET = 0.24;
const wetL = reverb(dryL, 0);
const wetR = reverb(dryR, 23);

const outL = new Float32Array(N);
const outR = new Float32Array(N);
let peak = 0;
const fadeFrom = N - Math.round(1.6 * SR);
for (let i = 0; i < N; i++) {
  let fade = 1;
  if (i > fadeFrom) {
    const x = 1 - (i - fadeFrom) / (N - fadeFrom);
    fade = x * x;
  }
  // tanh 把偶尔叠在一起的尖峰压圆，不会削出毛刺
  outL[i] = Math.tanh(1.4 * (dryL[i] + WET * wetL[i])) * fade;
  outR[i] = Math.tanh(1.4 * (dryR[i] + WET * wetR[i])) * fade;
  peak = Math.max(peak, Math.abs(outL[i]), Math.abs(outR[i]));
}

// 峰值定在 -3 dBFS
const scale = 10 ** (-3 / 20) / peak;

// ---- 写 16 位立体声 WAV ----

const data = Buffer.alloc(N * 4);
for (let i = 0; i < N; i++) {
  data.writeInt16LE(Math.round(outL[i] * scale * 32767), i * 4);
  data.writeInt16LE(Math.round(outR[i] * scale * 32767), i * 4 + 2);
}
const header = Buffer.alloc(44);
header.write("RIFF", 0);
header.writeUInt32LE(36 + data.length, 4);
header.write("WAVEfmt ", 8);
header.writeUInt32LE(16, 16);
header.writeUInt16LE(1, 20); // PCM
header.writeUInt16LE(2, 22); // 立体声
header.writeUInt32LE(SR, 24);
header.writeUInt32LE(SR * 4, 28);
header.writeUInt16LE(4, 32);
header.writeUInt16LE(16, 34);
header.write("data", 36);
header.writeUInt32LE(data.length, 40);

const target = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "music.wav");
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, Buffer.concat([header, data]));

// ---- 自检：听不到声音的时候，至少确认音高和音量是对的 ----

/** 某一段里某个频率的能量（Goertzel） */
function energyAt(freq, from, to) {
  const coeff = 2 * Math.cos((TAU * freq) / SR);
  let s1 = 0;
  let s2 = 0;
  for (let i = from; i < to; i++) {
    const s0 = (outL[i] + outR[i]) * scale + coeff * s1 - s2;
    s2 = s1;
    s1 = s0;
  }
  return Math.sqrt(Math.max(0, s1 * s1 + s2 * s2 - coeff * s1 * s2)) / (to - from);
}

if (process.argv.includes("--check")) {
  const rows = [];
  for (let bar = 1; bar <= BARS; bar++) {
    const from = Math.round((bar - 1) * BAR * SR);
    const to = Math.round(bar * BAR * SR);
    let sum = 0;
    let barPeak = 0;
    let low = 0;
    let midSum = 0;
    const hpCoef = 1 - Math.exp((-TAU * 250) / SR);
    for (let i = from; i < to; i++) {
      const x = (outL[i] + outR[i]) * scale * 0.5;
      low += hpCoef * (x - low);
      midSum += (x - low) ** 2;
      sum += ((outL[i] + outR[i]) * scale * 0.5) ** 2;
      barPeak = Math.max(barPeak, Math.abs(outL[i] * scale), Math.abs(outR[i] * scale));
    }
    // 这一小节后半段（避开小节线上的鼓和音效）里，12 个音级的低音哪个最响
    const mid = Math.round(from + (to - from) * 0.4);
    let best = 0;
    let bestEnergy = 0;
    for (let pc = 0; pc < 12; pc++) {
      const e = energyAt(hz(place(pc, 38)), mid, to);
      if (e > bestEnergy) {
        bestEnergy = e;
        best = pc;
      }
    }
    rows.push({
      bar,
      chord: CHART[bar - 1],
      rms: (20 * Math.log10(Math.sqrt(sum / (to - from)) + 1e-9)).toFixed(1),
      // 250 Hz 以上的音量：笔记本和手机的喇叭放不出低音，实际听到的主要是这一部分
      above250: (20 * Math.log10(Math.sqrt(midSum / (to - from)) + 1e-9)).toFixed(1),
      peak: (20 * Math.log10(barPeak + 1e-9)).toFixed(1),
      bassOk: best === CHORDS[CHART[bar - 1]][0],
    });
  }
  console.table(rows);
  console.log(`低音音高对的小节：${rows.filter((r) => r.bassOk).length}/${BARS}`);
}

console.log(`写好了 ${target}：${(N / SR).toFixed(1)} 秒，峰值 -3.0 dBFS（归一化前 ${peak.toFixed(3)}）`);
