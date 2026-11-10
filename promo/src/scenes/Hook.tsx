// 第 1 场：Agent 在读 README，里面藏着一段页面上看不见的注释。

import { interpolate, useCurrentFrame } from "remotion";
import { C, F } from "../theme";
import { Panel, Rise, Stage, prog } from "../ui";

// null 表示藏着指令的那三行（内容用色块盖住，不照抄）
const LINES: (string | null)[] = [
  "# config-loader",
  "",
  "Loads `key=value` config files.",
  "",
  null,
  null,
  null,
  "",
  "## Usage",
];
const BARS = [430, 560, 330];
const LINE_H = 58;

export function Hook() {
  const frame = useCurrentFrame();
  const scanY = interpolate(frame, [18, 72], [0, LINE_H * LINES.length], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scanOn = frame >= 18 && frame < 76;
  const alarm = prog(frame, 60, 14);
  let hidden = -1;

  return (
    <Stage>
      <Rise at={0} y={0}>
        <Panel
          title="README.md"
          aside={frame < 76 ? "Agent 正在读…" : "读完了"}
          style={{ left: 140, top: 236, width: 800 }}
        >
          <div style={{ position: "relative", padding: "22px 0 26px", fontFamily: F.mono, fontSize: 29 }}>
            {LINES.map((text, i) => {
              const shown = prog(frame, 8 + i * 3, 10);
              if (text === null) hidden += 1;
              return (
                <div
                  key={i}
                  style={{
                    height: LINE_H,
                    display: "flex",
                    alignItems: "center",
                    opacity: shown,
                    backgroundColor: text === null ? `rgba(240, 112, 112, ${0.16 * alarm})` : "transparent",
                  }}
                >
                  <span style={{ width: 84, paddingRight: 28, textAlign: "right", color: C.faint }}>{i + 1}</span>
                  {text === null ? (
                    <span style={{ display: "flex", alignItems: "center", gap: 16, color: alarm > 0.5 ? C.bad : C.muted }}>
                      {hidden === 0 ? "<!--" : null}
                      <span
                        style={{
                          display: "inline-block",
                          width: BARS[hidden],
                          height: 22,
                          marginLeft: hidden === 0 ? 0 : 86,
                          borderRadius: 4,
                          backgroundColor: alarm > 0.5 ? C.bad : C.faint,
                          opacity: 0.75,
                        }}
                      />
                      {hidden === 2 ? "-->" : null}
                    </span>
                  ) : (
                    <span style={{ color: C.ink2 }}>{text}</span>
                  )}
                </div>
              );
            })}
            {scanOn ? (
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                  top: 22 + scanY,
                  height: 3,
                  backgroundColor: C.accent,
                  boxShadow: `0 0 24px 4px ${C.accent}`,
                }}
              />
            ) : null}
          </div>
        </Panel>
      </Rise>

      <Rise
        at={72}
        style={{
          position: "absolute",
          left: 140,
          top: 898,
          fontFamily: F.mono,
          fontSize: 25,
          color: C.bad,
        }}
      >
        ↑ 页面上看不见的 HTML 注释，模型读得到
      </Rise>

      <div style={{ position: "absolute", left: 1030, top: 330, width: 760 }}>
        <Rise at={58} style={{ fontSize: 78, fontWeight: 700, lineHeight: 1.25, letterSpacing: -1.5 }}>
          它读到的每个文件，
        </Rise>
        <Rise at={76} style={{ fontSize: 78, fontWeight: 700, lineHeight: 1.25, letterSpacing: -1.5 }}>
          都可能藏着<span style={{ color: C.bad }}>指令</span>。
        </Rise>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 56 }}>
          {["README 里一段注释", "依赖的报错信息", "测试的输出"].map((label, i) => (
            <Rise
              key={label}
              at={108 + i * 9}
              y={12}
              style={{
                padding: "10px 22px",
                border: `2px solid ${C.faint}`,
                borderRadius: 999,
                fontSize: 27,
                color: C.ink2,
              }}
            >
              {label}
            </Rise>
          ))}
        </div>
      </div>
    </Stage>
  );
}
