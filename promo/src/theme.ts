// 宣传片的颜色、字体和时间。颜色取自桌面界面的深色主题。

export const C = {
  bg: "#0d0d0c",
  panel: "#161615",
  line: "#2c2c2a",
  faint: "#46453f",
  muted: "#8f8d86",
  ink2: "#c3c2b7",
  ink: "#f0efec",
  accent: "#5b8cff",
  good: "#4fd04f",
  goodBg: "rgba(79, 208, 79, 0.12)",
  bad: "#f07070",
  badBg: "rgba(240, 112, 112, 0.14)",
  warn: "#fab219",
} as const;

// 用的是 macOS 自带的字体；换到别的系统渲染，字形会不一样
export const F = {
  sans: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif',
  mono: '"SF Mono", Menlo, Monaco, monospace',
} as const;

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// 场与场之间淡入淡出的长度
export const TRANSITION = 15;

// 配乐一小节 2 秒（见 music/compose.mjs），每一场占整数个小节，换场正好落在小节线上
const BAR = 2 * FPS;
const bars = (n: number, last = false) => n * BAR + (last ? 0 : TRANSITION);

// 每一场的长度（帧）。除了最后一场，都多出一段和下一场叠着淡入淡出
export const SCENES = {
  hook: bars(3),
  turn: bars(2),
  identity: bars(2),
  sandbox: bars(7),
  loop: bars(4),
  permission: bars(3),
  end: bars(3, true),
} as const;

const total = Object.values(SCENES).reduce((sum, n) => sum + n, 0);
export const DURATION = total - TRANSITION * (Object.keys(SCENES).length - 1);
