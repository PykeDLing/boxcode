// 第 5 场：自检没通过，把输出交回模型继续修。右边是一份示意的执行轨迹。

import { useCurrentFrame } from "remotion";
import { C, F } from "../theme";
import { Column, Panel, Rise, Stage, Type, prog } from "../ui";

type Row = { kind: string; text: string; tone?: "good" | "bad" };
const ROWS: Row[] = [
  { kind: "run_start", text: "修好 tests/test_stats.py" },
  { kind: "llm_call", text: "→ 2 个工具调用" },
  { kind: "tool_call", text: "read_file  tests/test_stats.py" },
  { kind: "tool_call", text: "edit_file  stats.py" },
  { kind: "verify", text: "✕ 1 failed, 4 passed  → 交回模型继续修", tone: "bad" },
  { kind: "llm_call", text: "→ 1 个工具调用" },
  { kind: "tool_call", text: "edit_file  stats.py" },
  { kind: "verify", text: "✓ 5 passed", tone: "good" },
  { kind: "run_end", text: "完成" },
];
// 每一行出现在第几帧：自检失败落在第 3 小节开头（120），通过落在第 4 小节开头（180）
const ROW_AT = [60, 75, 90, 105, 120, 142, 160, 180, 198];

export function Loop() {
  const frame = useCurrentFrame();
  return (
    <Stage chapter="02 / 03 · 反思纠错">
      <Column eyebrow="02 · 反思纠错" title={["失败了，", "自己修"]}>
        <Rise at={16} style={{ marginTop: 40, fontSize: 34, lineHeight: 1.6, color: C.ink2 }}>
          模型说做完了，就跑你给的自检命令。
          <br />
          没通过，把输出交回去继续修。
        </Rise>
        <Rise at={206} style={{ marginTop: 44, fontSize: 26, color: C.muted }}>
          每一步写一行执行轨迹，事后可以回看。
        </Rise>
      </Column>

      <Rise at={6} y={0}>
        <Panel title="终端" aside="示意轨迹" style={{ left: 850, top: 200, width: 930, height: 690 }}>
          <div style={{ padding: "22px 28px", fontFamily: F.mono, fontSize: 25, lineHeight: 1.5 }}>
            <div style={{ color: C.ink, whiteSpace: "pre" }}>
              <span style={{ color: C.muted }}>$ </span>
              <Type text={'boxcode run "修好 tests/test_stats.py" \\'} at={12} speed={2} />
            </div>
            <div style={{ color: C.ink, whiteSpace: "pre", height: 38 }}>
              <Type text={'    --verify "python -m pytest -q"'} at={34} speed={2} />
            </div>
            <div style={{ height: 1, margin: "18px 0 16px", backgroundColor: C.line }} />
            {ROWS.map((row, i) => {
              const at = ROW_AT[i];
              const p = prog(frame, at, 8);
              const color = row.tone === "bad" ? C.bad : row.tone === "good" ? C.good : C.ink2;
              return (
                <div key={i} style={{ display: "flex", height: 52, alignItems: "center", opacity: p }}>
                  <span style={{ width: 190, color: row.tone ? color : C.muted }}>{row.kind}</span>
                  <span style={{ color, whiteSpace: "pre" }}>{row.text}</span>
                </div>
              );
            })}
          </div>
        </Panel>
      </Rise>
    </Stage>
  );
}
