// 各场共用的零件：背景和边角、渐显、打字、图标、左侧文字栏。

import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { C, F } from "./theme";

const ease = Easing.bezier(0.16, 1, 0.3, 1);

/** 从 start 开始、持续 dur 帧的 0→1 进度，两头截住。 */
export function prog(frame: number, start: number, dur = 18): number {
  return interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });
}

/** 渐显并上移一小段。 */
export function Rise(props: {
  at: number;
  dur?: number;
  y?: number;
  style?: CSSProperties;
  children: ReactNode;
}) {
  const frame = useCurrentFrame();
  const p = prog(frame, props.at, props.dur ?? 18);
  return (
    <div
      style={{
        opacity: p,
        transform: `translateY(${(1 - p) * (props.y ?? 24)}px)`,
        ...props.style,
      }}
    >
      {props.children}
    </div>
  );
}

/** 打字效果：从 at 开始，每帧打 speed 个字。 */
export function Type(props: { text: string; at: number; speed?: number; cursor?: boolean }) {
  const frame = useCurrentFrame();
  const speed = props.speed ?? 1.6;
  const count = Math.max(0, Math.min(props.text.length, Math.floor((frame - props.at) * speed)));
  const typing = frame >= props.at && count < props.text.length;
  return (
    <span>
      {props.text.slice(0, count)}
      {props.cursor !== false && typing ? <span style={{ color: C.accent }}>▍</span> : null}
    </span>
  );
}

/** 图标：一个盒子，里面是命令提示符。draw 是 0→1 的描边进度。 */
export function Mark(props: { size: number; draw?: number; color?: string }) {
  const draw = props.draw ?? 1;
  const color = props.color ?? C.ink;
  const perimeter = 104;
  return (
    <svg width={props.size} height={props.size} viewBox="0 0 32 32">
      <rect
        x="3"
        y="3"
        width="26"
        height="26"
        rx="5"
        fill="none"
        stroke={color}
        strokeWidth="2.4"
        strokeDasharray={perimeter}
        strokeDashoffset={perimeter * (1 - draw)}
      />
      <path
        d="M10 12l5 4-5 4"
        fill="none"
        stroke={color}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={draw > 0.6 ? (draw - 0.6) / 0.4 : 0}
      />
      <path
        d="M17.5 21h5"
        stroke={C.accent}
        strokeWidth="2.4"
        strokeLinecap="round"
        opacity={draw > 0.8 ? (draw - 0.8) / 0.2 : 0}
      />
    </svg>
  );
}

function Corner(props: { style: CSSProperties }) {
  return (
    <div
      style={{
        position: "absolute",
        width: 28,
        height: 28,
        borderColor: C.faint,
        borderStyle: "solid",
        borderWidth: 0,
        ...props.style,
      }}
    />
  );
}

/** 每一场的底：深色背景、细网格、四个边角；chapter 写在右上角。 */
export function Stage(props: { chapter?: string; brand?: boolean; children: ReactNode }) {
  const inset = 48;
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, color: C.ink, fontFamily: F.sans }}>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${C.line} 1px, transparent 1px), linear-gradient(90deg, ${C.line} 1px, transparent 1px)`,
          backgroundSize: "96px 96px",
          backgroundPosition: "center",
          opacity: 0.5,
        }}
      />
      <Corner style={{ left: inset, top: inset, borderLeftWidth: 2, borderTopWidth: 2 }} />
      <Corner style={{ right: inset, top: inset, borderRightWidth: 2, borderTopWidth: 2 }} />
      <Corner style={{ left: inset, bottom: inset, borderLeftWidth: 2, borderBottomWidth: 2 }} />
      <Corner style={{ right: inset, bottom: inset, borderRightWidth: 2, borderBottomWidth: 2 }} />
      {props.brand !== false ? (
        <div
          style={{
            position: "absolute",
            left: 96,
            top: 74,
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontSize: 26,
            fontWeight: 650,
            color: C.ink2,
          }}
        >
          <Mark size={30} color={C.ink2} />
          BoxCode
        </div>
      ) : null}
      {props.chapter ? (
        <div
          style={{
            position: "absolute",
            right: 96,
            top: 78,
            fontFamily: F.mono,
            fontSize: 22,
            letterSpacing: 2,
            color: C.muted,
          }}
        >
          {props.chapter}
        </div>
      ) : null}
      {props.children}
    </AbsoluteFill>
  );
}

/** 功能场左边的文字栏：编号、两行标题、一段说明。 */
export function Column(props: {
  eyebrow: string;
  title: [string, string];
  children?: ReactNode;
  width?: number;
}) {
  return (
    <div style={{ position: "absolute", left: 140, top: 216, width: props.width ?? 640 }}>
      <Rise at={0} style={{ fontFamily: F.mono, fontSize: 26, letterSpacing: 2, color: C.accent }}>
        {props.eyebrow}
      </Rise>
      <Rise at={5} style={{ marginTop: 22, fontSize: 76, fontWeight: 700, lineHeight: 1.2, letterSpacing: -1.5 }}>
        {props.title[0]}
        <br />
        {props.title[1]}
      </Rise>
      {props.children}
    </div>
  );
}

/** 深色面板，带一行标题栏。 */
export function Panel(props: {
  title: string;
  aside?: string;
  style?: CSSProperties;
  borderColor?: string;
  children: ReactNode;
}) {
  return (
    <div
      style={{
        position: "absolute",
        backgroundColor: C.panel,
        border: `3px solid ${props.borderColor ?? C.faint}`,
        borderRadius: 18,
        overflow: "hidden",
        ...props.style,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "16px 26px",
          borderBottom: `1px solid ${C.line}`,
          fontFamily: F.mono,
          fontSize: 21,
          color: C.muted,
        }}
      >
        <span style={{ color: C.ink2 }}>{props.title}</span>
        <span>{props.aside}</span>
      </div>
      {props.children}
    </div>
  );
}
