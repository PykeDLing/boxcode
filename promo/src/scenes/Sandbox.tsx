// 第 4 场：沙盒。命令一条条在盒子里执行，想够外面的东西都被挡住。

import { interpolate, useCurrentFrame } from "remotion";
import { C, F } from "../theme";
import { Column, Panel, Rise, Stage, Type, prog } from "../ui";

const RULES = ["只能写工作区", "读不到凭证", "默认断网", "借不了别的程序的手", "环境变量只传白名单"];
const TARGETS: [string, string][] = [
  [".git", "hook · 配置"],
  ["凭证", "SSH · AWS · 钥匙串"],
  ["网络", "IP · 域名解析 · 代理"],
  ["其他程序", "open · Apple 事件"],
  ["环境变量", "模型的 key"],
];

// rule 是这条命令对应第几条规则（也是外面第几个目标）；没有 rule 的是放行的命令。
// 每条命令的结果都在小节线上出来（60 帧一小节），和配乐换和弦是同一刻
const STEPS: { at: number; cmd: string; verdict: string; rule?: number }[] = [
  { at: 38, cmd: "python -m pytest -q", verdict: "放行 · 在工作区里" },
  { at: 98, cmd: "echo … > .git/hooks/pre-commit", verdict: "挡住 · .git 只读", rule: 0 },
  { at: 158, cmd: "cat ~/.ssh/id_rsa", verdict: "挡住 · 读不到凭证", rule: 1 },
  { at: 218, cmd: "curl https://example.com/upload", verdict: "挡住 · 默认断网", rule: 2 },
  { at: 278, cmd: "open -a Terminal", verdict: "挡住 · 启动不了别的程序", rule: 3 },
  { at: 338, cmd: "echo $ANTHROPIC_API_KEY", verdict: "空的 · 只传白名单里的变量", rule: 4 },
];
const VERDICT_DELAY = 22;

export function Sandbox() {
  const frame = useCurrentFrame();

  // 盒子边框：有命令被挡住时闪一下红
  let flash = 0;
  for (const step of STEPS) {
    if (step.rule === undefined) continue;
    const t = step.at + VERDICT_DELAY;
    flash = Math.max(
      flash,
      interpolate(frame, [t, t + 5, t + 28], [0, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    );
  }
  const border = flash > 0.05 ? C.bad : C.ink2;
  const blocked = (rule: number) => {
    const step = STEPS.find((s) => s.rule === rule);
    return step !== undefined && frame >= step.at + VERDICT_DELAY;
  };
  const active = (rule: number) => {
    const step = STEPS.find((s) => s.rule === rule);
    return step !== undefined && frame >= step.at;
  };

  return (
    <Stage chapter="01 / 03 · 沙盒">
      <Column eyebrow="01 · 沙盒" title={["每条命令，", "都关在沙盒里"]}>
        <div style={{ marginTop: 46, display: "grid", gap: 20 }}>
          {RULES.map((rule, i) => {
            const on = active(i);
            const done = blocked(i);
            return (
              <Rise key={rule} at={14 + i * 4} y={10} style={{ display: "flex", alignItems: "center", gap: 20 }}>
                <span
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    display: "grid",
                    placeItems: "center",
                    fontFamily: F.mono,
                    fontSize: 21,
                    border: `2px solid ${done ? C.good : on ? C.ink : C.faint}`,
                    color: done ? C.good : on ? C.ink : C.muted,
                    backgroundColor: done ? C.goodBg : "transparent",
                  }}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span style={{ fontSize: 36, fontWeight: on ? 650 : 400, color: on ? C.ink : C.muted }}>{rule}</span>
              </Rise>
            );
          })}
        </div>
        <Rise at={376} style={{ marginTop: 44, fontSize: 26, color: C.ink2 }}>
          每一条都有测试，测试会真实启动沙盒去验证。
        </Rise>
      </Column>

      <Rise at={6} y={0}>
        <Panel
          title="沙盒 · sandbox-exec"
          aside="工作区 ~/dev/my-repo"
          borderColor={border}
          style={{
            left: 850,
            top: 200,
            width: 680,
            height: 680,
            boxShadow: flash > 0.05 ? `0 0 0 ${10 * flash}px ${C.badBg}` : "none",
          }}
        >
          <div style={{ padding: "18px 26px", fontFamily: F.mono }}>
            {STEPS.map((step) => {
              if (frame < step.at) return null;
              const ok = step.rule === undefined;
              const verdict = prog(frame, step.at + VERDICT_DELAY, 8);
              return (
                <div key={step.cmd + step.at} style={{ height: 94 }}>
                  <div style={{ fontSize: 27, color: C.ink, whiteSpace: "nowrap" }}>
                    <span style={{ color: C.muted }}>$ </span>
                    <Type text={step.cmd} at={step.at} speed={2.2} />
                  </div>
                  <div style={{ marginTop: 6, paddingLeft: 32, fontSize: 23, color: ok ? C.good : C.bad, opacity: verdict }}>
                    {ok ? "✓ " : "✕ "}
                    {step.verdict}
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </Rise>

      <div style={{ position: "absolute", left: 1570, top: 200, width: 240 }}>
        <Rise at={10} style={{ fontFamily: F.mono, fontSize: 21, color: C.muted, height: 52 }}>
          盒子外面
        </Rise>
        <div style={{ display: "grid", gap: 15 }}>
          {TARGETS.map(([name, detail], i) => {
            const hit = blocked(i);
            return (
              <Rise
                key={name}
                at={16 + i * 4}
                y={10}
                style={{
                  height: 110,
                  padding: "0 20px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  borderRadius: 14,
                  border: hit ? `2px solid ${C.good}` : `2px dashed ${C.faint}`,
                  backgroundColor: hit ? C.goodBg : "transparent",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 29, fontWeight: 650 }}>
                  {name}
                  {hit ? <span style={{ fontSize: 22, fontWeight: 400, color: C.good }}>没碰到</span> : null}
                </div>
                <div style={{ marginTop: 4, fontSize: 19, color: C.muted }}>{detail}</div>
              </Rise>
            );
          })}
        </div>
      </div>
    </Stage>
  );
}
