// 第 2 场：提示词不够，所以把命令关进盒子里。盒子绕着这句话画出来。

import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { C } from "../theme";
import { Rise, Stage, prog } from "../ui";

const BOX_W = 1320;
const BOX_H = 260;
const PERIMETER = 2 * (BOX_W + BOX_H);

export function Turn() {
  const frame = useCurrentFrame();
  const firstOut = interpolate(frame, [48, 58], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const draw = prog(frame, 66, 34);

  return (
    <Stage>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: firstOut }}>
        <Rise at={4} style={{ fontSize: 80, fontWeight: 650, color: C.ink2, letterSpacing: -1 }}>
          只靠提示词让模型别上当，
        </Rise>
        <Rise at={22} style={{ marginTop: 18, fontSize: 80, fontWeight: 700, letterSpacing: -1 }}>
          是不够的。
        </Rise>
      </AbsoluteFill>

      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <svg
          width={BOX_W + 12}
          height={BOX_H + 12}
          viewBox={`-6 -6 ${BOX_W + 12} ${BOX_H + 12}`}
          style={{ position: "absolute" }}
        >
          <rect
            width={BOX_W}
            height={BOX_H}
            rx={24}
            fill="none"
            stroke={C.ink}
            strokeWidth={5}
            strokeDasharray={PERIMETER}
            strokeDashoffset={PERIMETER * (1 - draw)}
          />
        </svg>
        <Rise at={60} style={{ fontSize: 96, fontWeight: 700, letterSpacing: -2 }}>
          所以，把命令<span style={{ color: C.accent }}>关进盒子里</span>。
        </Rise>
      </AbsoluteFill>
    </Stage>
  );
}
