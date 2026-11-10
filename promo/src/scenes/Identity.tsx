// 第 3 场：名字和一句话介绍。

import { AbsoluteFill, useCurrentFrame } from "remotion";
import { C, F } from "../theme";
import { Mark, Rise, Stage, prog } from "../ui";

const PILLS = ["Python 3.12", "macOS Seatbelt", "MIT 许可", "451 个测试"];

export function Identity() {
  const frame = useCurrentFrame();
  return (
    <Stage brand={false}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
          <Mark size={170} draw={prog(frame, 2, 34)} />
          <Rise at={14} style={{ fontSize: 168, fontWeight: 700, letterSpacing: -5, lineHeight: 1 }}>
            BoxCode
          </Rise>
        </div>
        <Rise at={36} style={{ marginTop: 54, fontSize: 42, color: C.ink2 }}>
          一个命令行编程 Agent：读代码、改代码、跑测试，失败了自己修。
        </Rise>
        <div style={{ display: "flex", gap: 16, marginTop: 52 }}>
          {PILLS.map((label, i) => (
            <Rise
              key={label}
              at={58 + i * 7}
              y={12}
              style={{
                padding: "10px 24px",
                border: `2px solid ${C.faint}`,
                borderRadius: 999,
                fontFamily: F.mono,
                fontSize: 25,
                color: C.ink2,
              }}
            >
              {label}
            </Rise>
          ))}
        </div>
      </AbsoluteFill>
    </Stage>
  );
}
