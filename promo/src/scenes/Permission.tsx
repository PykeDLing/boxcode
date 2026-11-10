// 第 6 场：权限策略。高风险的命令先问人。

import { interpolate, useCurrentFrame } from "remotion";
import { C, F } from "../theme";
import { Column, Rise, Stage, prog } from "../ui";

const MODES: [string, string][] = [
  ["read-only", "每条命令都问"],
  ["workspace-write", "默认 · 高风险的先问"],
  ["full-auto", "全部放行"],
];
const PRESS = 60;

export function Permission() {
  const frame = useCurrentFrame();
  const pressed = frame >= PRESS;
  const press = interpolate(frame, [PRESS, PRESS + 4, PRESS + 10], [1, 0.95, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const allowed = prog(frame, PRESS + 8, 10);

  return (
    <Stage chapter="03 / 03 · 权限策略">
      <Column eyebrow="03 · 权限策略" title={["高风险的事，", "先拿给你看"]}>
        <Rise at={16} style={{ marginTop: 40, fontSize: 34, lineHeight: 1.6, color: C.ink2 }}>
          联网、git push、装依赖、
          <br />
          递归删除、提权：先问，再执行。
        </Rise>
      </Column>

      <Rise
        at={8}
        style={{
          position: "absolute",
          left: 850,
          top: 216,
          width: 930,
          padding: "30px 36px 34px",
          backgroundColor: C.panel,
          border: `3px solid ${pressed ? C.faint : C.warn}`,
          borderRadius: 18,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 26, color: pressed ? C.muted : C.warn }}>
          <span style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: pressed ? C.muted : C.warn }} />
          需要确认
        </div>
        <div style={{ marginTop: 22, fontFamily: F.mono, fontSize: 36, color: C.ink }}>
          <span style={{ color: C.muted }}>$ </span>git push origin main
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 34 }}>
          <div
            style={{
              padding: "14px 30px",
              borderRadius: 12,
              backgroundColor: C.ink,
              color: C.bg,
              fontSize: 28,
              fontWeight: 650,
              transform: `scale(${press})`,
            }}
          >
            放行这一次
          </div>
          <div style={{ padding: "12px 30px", borderRadius: 12, border: `2px solid ${C.faint}`, fontSize: 28, color: C.ink2 }}>
            拒绝
          </div>
          <div style={{ marginLeft: 12, fontSize: 26, color: C.good, opacity: allowed }}>✓ 已放行，记进执行轨迹</div>
        </div>
      </Rise>

      <div style={{ position: "absolute", left: 850, top: 560, width: 930 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {MODES.map(([name, note], i) => (
            <Rise
              key={name}
              at={120 + i * 7}
              y={12}
              style={{
                padding: "20px 22px 22px",
                borderRadius: 14,
                border: `2px solid ${i === 1 ? C.ink2 : C.faint}`,
              }}
            >
              <div style={{ fontFamily: F.mono, fontSize: 26, color: C.ink }}>{name}</div>
              <div style={{ marginTop: 8, fontSize: 23, color: C.muted }}>{note}</div>
            </Rise>
          ))}
        </div>
        <Rise at={150} style={{ marginTop: 34, fontSize: 30, color: C.ink }}>
          不管哪种模式，命令都在沙盒里执行。
        </Rise>
      </div>
    </Stage>
  );
}
