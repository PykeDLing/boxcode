// 第 7 场：收尾。名字、一句话、怎么拿到它。

import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../theme";
import { Mark, Rise, Stage, prog } from "../ui";

export function End() {
  const frame = useCurrentFrame();
  return (
    <Stage brand={false}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <Mark size={120} draw={prog(frame, 0, 26)} />
          <Rise at={8} style={{ fontSize: 124, fontWeight: 700, letterSpacing: -4, lineHeight: 1 }}>
            BoxCode
          </Rise>
        </div>
        <Rise at={24} style={{ marginTop: 50, fontSize: 64, fontWeight: 650, letterSpacing: -1 }}>
          把 Agent 的命令，关进盒子里。
        </Rise>
        <Rise
          at={44}
          style={{
            marginTop: 64,
            padding: "20px 34px",
            borderRadius: 14,
            border: `2px solid ${C.faint}`,
            backgroundColor: C.panel,
            fontFamily: F.mono,
            fontSize: 32,
          }}
        >
          <span style={{ color: C.muted }}>$ </span>git clone https://github.com/PykeDLing/boxcode.git
        </Rise>
        <Rise at={58} style={{ marginTop: 34, fontFamily: F.mono, fontSize: 25, color: C.muted }}>
          开源 · MIT 许可 · macOS · Python 3.12
        </Rise>
      </AbsoluteFill>
    </Stage>
  );
}
